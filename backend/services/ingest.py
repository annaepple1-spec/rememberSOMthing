"""Service for ingesting PDFs and generating flashcards via multi-agent pipeline."""
import uuid
import fitz  # PyMuPDF
from typing import List, Tuple, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.models import Document, Card, CardType, MacroTopic, MicroTopic
from backend.agents.flashcard_crew import run_flashcard_agent_pipeline


def _fallback_generate_cards_from_text(full_text: str, document_id: str) -> List[Card]:
    """
    Fallback card generation when the agent pipeline output is empty or malformed.
    """
    text = full_text.strip()
    cards: List[Card] = []
    if not text:
        return cards

    truncated = text[:400] + "..." if len(text) > 400 else text

    cards.append(Card(
        id=str(uuid.uuid4()),
        document_id=document_id,
        topic="Document Summary",
        type=CardType.definition,
        front="Summarize the main ideas of this document.",
        back=truncated,
    ))
    cards.append(Card(
        id=str(uuid.uuid4()),
        document_id=document_id,
        topic="Key Concepts",
        type=CardType.application,
        front="What are the key concepts covered in this document?",
        back="Mention the main theories, definitions and relationships described in the text.",
    ))

    return cards


def _deck_to_cards(deck: dict, document_id: str) -> List[Card]:
    """
    Transform the multi-agent deck structure into a list of Card ORM objects.
    Prefers macros/micros structure; falls back to legacy topics/concepts.
    """
    def _map_fc_to_card(fc: dict, topic_label: str, micro_topic_id: Optional[int] = None) -> Card:
        fc_type_str = (fc.get("type") or "definition").lower()
        if fc_type_str == "definition":
            card_type = CardType.definition
        elif fc_type_str == "cloze" and hasattr(CardType, "cloze"):
            card_type = CardType.cloze
        elif fc_type_str == "application" and hasattr(CardType, "application"):
            card_type = CardType.application
        else:
            card_type = getattr(CardType, "application", CardType.definition)

        front = (fc.get("front") or "").strip()
        back = (fc.get("back") or "").strip()

        difficulty_label = (fc.get("difficulty") or "medium").lower()
        if difficulty_label == "easy":
            base_diff = 0.2
        elif difficulty_label == "hard":
            base_diff = 0.8
        else:
            base_diff = 0.5

        # Handle MCQ card type and options
        mcq_correct_idx = None
        if fc_type_str == "mcq":
            card_type = CardType.mcq  # Use MCQ enum value
            options = fc.get("options", [])
            correct_idx = fc.get("correct_option_index", 0)
            if options:
                labels = ["A", "B", "C", "D", "E", "F"]
                opts_rendered = []
                for i, opt in enumerate(options):
                    label = labels[i] if i < len(labels) else str(i + 1)
                    opts_rendered.append(f"{label}) {opt}")
                front = (front or "Choose the correct answer:") + "\nOptions:\n" + "\n".join(opts_rendered)
                if 0 <= correct_idx < len(options):
                    back = options[correct_idx]
                    mcq_correct_idx = correct_idx

        return Card(
            id=str(uuid.uuid4()),
            document_id=document_id,
            topic=topic_label,
            micro_topic_id=micro_topic_id,
            type=card_type,
            front=front,
            back=back,
            correct_option_index=mcq_correct_idx,
            base_difficulty=base_diff,
        )

    cards: List[Card] = []

    # Macros-first mapping
    macros = deck.get("macros") or []
    print(f"[DECK_TO_CARDS] Found {len(macros)} macros")
    if macros:
        for macro in macros:
            macro_name = macro.get("name") or "Untitled Macro"
            micros = macro.get("micros", [])
            print(f"[DECK_TO_CARDS] Macro '{macro_name}' has {len(micros)} micros")
            for micro in micros:
                micro_name = micro.get("name") or "Untitled Micro"
                concepts = micro.get("concepts") or []
                print(f"[DECK_TO_CARDS] Micro '{micro_name}' has {len(concepts)} concepts")
                for concept in concepts:
                    flashcards = concept.get("flashcards") or []
                    print(f"[DECK_TO_CARDS] Concept has {len(flashcards)} flashcards")
                    topic_label = f"{macro_name} - {micro_name}"
                    for fc in flashcards:
                        cards.append(_map_fc_to_card(fc, topic_label))
        print(f"[DECK_TO_CARDS] Total cards created from macros: {len(cards)}")
        if cards:
            return cards

    # Legacy topics mapping if macros absent or yielded no cards
    topics = deck.get("topics") or []
    if topics:
        for topic in topics:
            topic_name = topic.get("name") or "Uncategorized"
            for concept in topic.get("concepts", []):
                concept_name = concept.get("name") or "General"
                flashcards = concept.get("flashcards") or []
                topic_label = f"{topic_name} - {concept_name}"
                for fc in flashcards:
                    cards.append(_map_fc_to_card(fc, topic_label))
        if cards:
            return cards

    # Fallback to summary-based cards
    return _fallback_generate_cards_from_text(deck.get("raw_text", ""), document_id)


def _create_topics_and_cards(deck: dict, document: Document, db: Session) -> int:
    """
    Create MacroTopic, MicroTopic, and Card records from deck structure.
    Links cards to MicroTopics for adaptive learning.
    
    Returns:
        Total number of cards created
    """
    cards_created = 0
    
    # Process macros structure (preferred)
    macros = deck.get("macros") or []
    print(f"[CREATE_TOPICS] Processing {len(macros)} macros")
    
    if macros:
        for macro in macros:
            macro_name = (macro.get("name") or "Untitled Macro").strip()
            
            # Create or get MacroTopic
            macro_topic = db.query(MacroTopic).filter(
                MacroTopic.document_id == document.id,
                MacroTopic.name == macro_name
            ).first()
            
            if not macro_topic:
                macro_topic = MacroTopic(
                    name=macro_name,
                    document_id=document.id
                )
                db.add(macro_topic)
                db.flush()  # Get the ID
            
            print(f"[CREATE_TOPICS] MacroTopic '{macro_name}' (ID: {macro_topic.id})")
            
            # Process micros
            for micro in macro.get("micros", []):
                micro_name = (micro.get("name") or "Untitled Micro").strip()
                
                # Create or get MicroTopic
                micro_topic = db.query(MicroTopic).filter(
                    MicroTopic.macro_topic_id == macro_topic.id,
                    MicroTopic.name == micro_name
                ).first()
                
                if not micro_topic:
                    micro_topic = MicroTopic(
                        name=micro_name,
                        macro_topic_id=macro_topic.id,
                        document_id=document.id
                    )
                    db.add(micro_topic)
                    db.flush()  # Get the ID
                
                print(f"[CREATE_TOPICS]   MicroTopic '{micro_name}' (ID: {micro_topic.id})")
                
                # Process concepts and create cards
                concepts = micro.get("concepts") or []
                for concept in concepts:
                    flashcards = concept.get("flashcards") or []
                    topic_label = f"{macro_name} - {micro_name}"
                    
                    for fc in flashcards:
                        # Use helper function to map flashcard dict to Card
                        card = _map_fc_to_card_standalone(
                            fc=fc,
                            document_id=document.id,
                            topic_label=topic_label,
                            micro_topic_id=micro_topic.id
                        )
                        db.add(card)
                        cards_created += 1
                
                print(f"[CREATE_TOPICS]     Created {len(flashcards)} cards")
        
        if cards_created > 0:
            print(f"[CREATE_TOPICS] Total cards created: {cards_created}")
            return cards_created
    
    # Fallback: Legacy topics structure
    topics = deck.get("topics") or []
    if topics:
        print(f"[CREATE_TOPICS] Using legacy topics structure ({len(topics)} topics)")
        
        for topic in topics:
            topic_name = (topic.get("name") or "Uncategorized").strip()
            
            # Create MacroTopic for legacy topic
            macro_topic = MacroTopic(
                name=topic_name,
                document_id=document.id
            )
            db.add(macro_topic)
            db.flush()
            
            # Create single MicroTopic for the topic
            micro_topic = MicroTopic(
                name="General Concepts",
                macro_topic_id=macro_topic.id,
                document_id=document.id
            )
            db.add(micro_topic)
            db.flush()
            
            # Process concepts
            for concept in topic.get("concepts", []):
                concept_name = concept.get("name") or "General"
                flashcards = concept.get("flashcards") or []
                topic_label = f"{topic_name} - {concept_name}"
                
                for fc in flashcards:
                    card = _map_fc_to_card_standalone(
                        fc=fc,
                        document_id=document.id,
                        topic_label=topic_label,
                        micro_topic_id=micro_topic.id
                    )
                    db.add(card)
                    cards_created += 1
        
        if cards_created > 0:
            print(f"[CREATE_TOPICS] Total cards created from topics: {cards_created}")
            return cards_created
    
    # Final fallback: Generate simple cards
    print("[CREATE_TOPICS] No macros or topics found, using fallback")
    
    # Create a default topic structure for fallback cards
    macro_topic = MacroTopic(
        name="Document Summary",
        document_id=document.id
    )
    db.add(macro_topic)
    db.flush()
    
    micro_topic = MicroTopic(
        name="General Concepts",
        macro_topic_id=macro_topic.id,
        document_id=document.id
    )
    db.add(micro_topic)
    db.flush()
    
    # Generate fallback cards
    full_text = deck.get("raw_text", "")
    text = full_text.strip()
    
    if text:
        truncated = text[:400] + "..." if len(text) > 400 else text
        
        # Card 1: Document Summary
        card1 = Card(
            id=str(uuid.uuid4()),
            document_id=document.id,
            topic="Document Summary",
            micro_topic_id=micro_topic.id,
            type=CardType.definition,
            front="Summarize the main ideas of this document.",
            back=truncated,
            base_difficulty=0.5
        )
        db.add(card1)
        cards_created += 1
        
        # Card 2: Key Concepts
        card2 = Card(
            id=str(uuid.uuid4()),
            document_id=document.id,
            topic="Key Concepts",
            micro_topic_id=micro_topic.id,
            type=CardType.application,
            front="What are the key concepts covered in this document?",
            back="Mention the main theories, definitions and relationships described in the text.",
            base_difficulty=0.5
        )
        db.add(card2)
        cards_created += 1
    
    print(f"[CREATE_TOPICS] Created {cards_created} fallback cards")
    return cards_created


def _map_fc_to_card_standalone(fc: dict, document_id: str, topic_label: str, micro_topic_id: int) -> Card:
    """
    Standalone version of _map_fc_to_card for use in _create_topics_and_cards.
    Maps a flashcard dict to a Card ORM object with micro_topic_id.
    """
    fc_type_str = (fc.get("type") or "definition").lower()
    if fc_type_str == "definition":
        card_type = CardType.definition
    elif fc_type_str == "cloze" and hasattr(CardType, "cloze"):
        card_type = CardType.cloze
    elif fc_type_str == "application" and hasattr(CardType, "application"):
        card_type = CardType.application
    elif fc_type_str == "mcq" and hasattr(CardType, "mcq"):
        card_type = CardType.mcq
    else:
        card_type = getattr(CardType, "application", CardType.definition)

    front = (fc.get("front") or "").strip()
    back = (fc.get("back") or "").strip()

    difficulty_label = (fc.get("difficulty") or "medium").lower()
    if difficulty_label == "easy":
        base_diff = 0.2
    elif difficulty_label == "hard":
        base_diff = 0.8
    else:
        base_diff = 0.5

    # Handle MCQ card type and options
    mcq_correct_idx = None
    if fc_type_str == "mcq":
        options = fc.get("options", [])
        correct_idx = fc.get("correct_option_index", 0)
        if options:
            labels = ["A", "B", "C", "D", "E", "F"]
            opts_rendered = []
            for i, opt in enumerate(options):
                label = labels[i] if i < len(labels) else str(i + 1)
                opts_rendered.append(f"{label}) {opt}")
            front = (front or "Choose the correct answer:") + "\nOptions:\n" + "\n".join(opts_rendered)
            if 0 <= correct_idx < len(options):
                back = options[correct_idx]
                mcq_correct_idx = correct_idx

    return Card(
        id=str(uuid.uuid4()),
        document_id=document_id,
        topic=topic_label,
        micro_topic_id=micro_topic_id,
        type=card_type,
        front=front,
        back=back,
        correct_option_index=mcq_correct_idx,
        base_difficulty=base_diff,
    )


def process_pdf(file: UploadFile, db: Session) -> tuple[Document, int]:
    """
    Process a PDF file and generate flashcards from its content using the agent pipeline.
    """
    # Create document
    doc_id = str(uuid.uuid4())
    filename = file.filename or "Untitled Document"

    document = Document(id=doc_id, title=filename)
    db.add(document)

    # Read PDF content
    try:
        pdf_bytes = file.file.read()
        if not pdf_bytes:
            raise ValueError("Empty file uploaded")
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        print(f"[INGEST ERROR] Failed to open PDF: {e}")
        db.rollback()
        raise ValueError(f"Invalid PDF file: {str(e)}")

    full_text = ""
    try:
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            full_text += page.get_text()
    finally:
        pdf_document.close()

    # Run multi-agent pipeline
    try:
        print(f"[INGEST] Running agent pipeline for: {filename}")
        deck = run_flashcard_agent_pipeline(document_text=full_text, title=filename)
        print(f"[INGEST] Agent pipeline completed. Macros: {len(deck.get('macros', []))} | Topics: {len(deck.get('topics', []))}")
        print(f"[INGEST] Deck type: {type(deck)}, keys: {list(deck.keys())}")
    except Exception as e:
        # In case crew fails, fall back
        print(f"[INGEST ERROR] Agent pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        deck = {
            "document_title": filename,
            "topics": [],
            "raw_text": full_text,
            "error": str(e),
        }

    # Create topic hierarchy and cards with proper linking
    cards_created = _create_topics_and_cards(deck, document, db)

    db.commit()
    db.refresh(document)

    return document, cards_created
