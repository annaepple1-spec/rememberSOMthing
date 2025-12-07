"""Service for ingesting PDFs and generating flashcards via multi-agent pipeline."""
import uuid
import fitz  # PyMuPDF
import json
from typing import List, Tuple

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.models import Document, Card, CardType

# Try to import agent pipeline, but gracefully handle failures
try:
    from backend.agents.flashcard_crew import run_flashcard_agent_pipeline
    AGENT_AVAILABLE = True
except Exception as e:
    print(f"[INGEST] Agent pipeline not available: {e}")
    AGENT_AVAILABLE = False

# Try to import LLM service for AI-powered card generation
try:
    from backend.services.llm import generate_qa_cards_from_text
    LLM_AVAILABLE = True
except Exception as e:
    print(f"[INGEST] LLM service not available: {e}")
    LLM_AVAILABLE = False


def _fallback_generate_cards_from_text(full_text: str, document_id: str) -> List[Card]:
    """
    AI-powered fallback card generation using LLM to identify key concepts.
    Falls back to simple extraction if LLM unavailable.
    """
    text = full_text.strip()
    cards: List[Card] = []
    
    if not text:
        return cards

    # Try to use LLM to generate Q&A cards
    if LLM_AVAILABLE:
        try:
            print(f"[INGEST] Attempting AI-powered card generation for {len(text)} chars")
            qa_cards = generate_qa_cards_from_text(text, max_cards=10)
            
            if qa_cards:
                print(f"[INGEST] Generated {len(qa_cards)} AI cards")
                for qa_card in qa_cards:
                    # Convert difficulty string to base_difficulty float
                    difficulty = qa_card.get('difficulty', 'medium').lower()
                    if difficulty == 'easy':
                        base_diff = 0.3
                    elif difficulty == 'hard':
                        base_diff = 0.7
                    else:
                        base_diff = 0.5
                    
                    cards.append(Card(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        topic=qa_card.get('topic', 'Key Concept'),
                        type=CardType.definition,  # Q&A format is definition type
                        front=qa_card.get('question', 'Question'),
                        back=qa_card.get('answer', 'Answer'),
                        base_difficulty=base_diff,
                    ))
                return cards
        except Exception as e:
            print(f"[INGEST] AI card generation failed: {e}, falling back to simple extraction")

    # Fallback: Simple sentence-based card extraction
    print(f"[INGEST] Using fallback sentence extraction")
    sentences = [s.strip() for s in text.replace('\n', ' ').split('.') if len(s.strip()) > 20]
    
    if not sentences:
        # If no good sentences, create a summary card
        truncated = text[:400] + "..." if len(text) > 400 else text
        cards.append(Card(
            id=str(uuid.uuid4()),
            document_id=document_id,
            topic="Document Overview",
            type=CardType.definition,
            front="What is the main topic of this document?",
            back=truncated,
            base_difficulty=0.3,
        ))
        return cards

    # Create Q&A cards from sentences
    for i, sentence in enumerate(sentences[:10]):  # Limit to first 10 sentences
        if len(sentence) < 30:
            continue
        
        # Convert sentence to Q&A format
        words = sentence.split()
        if len(words) > 3:
            # Create a question from the sentence
            question = "Which of the following best describes this concept?\n" + sentence[:80] + ("..." if len(sentence) > 80 else "")
            
            cards.append(Card(
                id=str(uuid.uuid4()),
                document_id=document_id,
                topic=f"Key Concept {(i // 3) + 1}",
                type=CardType.definition,
                front=question,
                back=sentence,
                base_difficulty=0.5,
            ))

    return cards


def _deck_to_cards(deck: dict, document_id: str) -> List[Card]:
    """
    Transform the multi-agent deck structure into a list of Card ORM objects.
    Prefers macros/micros structure; falls back to legacy topics/concepts.
    """
    def _map_fc_to_card(fc: dict, topic_label: str) -> Card:
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

    # Run multi-agent pipeline if available
    deck = None
    if AGENT_AVAILABLE:
        try:
            print(f"[INGEST] Running agent pipeline for: {filename}")
            deck = run_flashcard_agent_pipeline(document_text=full_text, title=filename)
            print(f"[INGEST] Agent pipeline completed. Macros: {len(deck.get('macros', []))} | Topics: {len(deck.get('topics', []))}")
            print(f"[INGEST] Deck type: {type(deck)}, keys: {list(deck.keys())}")
        except Exception as e:
            print(f"[INGEST ERROR] Agent pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            deck = None
    else:
        print(f"[INGEST] Agent pipeline not available, using fallback")
    
    # If deck is empty or failed, use fallback
    if not deck:
        deck = {
            "document_title": filename,
            "topics": [],
            "raw_text": full_text,
        }

    # Turn deck into Card objects
    cards = _deck_to_cards(deck, document_id=doc_id)

    for card in cards:
        db.add(card)

    db.commit()
    db.refresh(document)

    return document, len(cards)
