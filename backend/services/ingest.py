"""Service for ingesting PDFs and generating flashcards via multi-agent pipeline."""
import uuid
import fitz  # PyMuPDF
from typing import List, Tuple

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.models import Document, Card, CardType
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
            macros = deck.get("macros") or []
            # If macros are missing, fall back to legacy 'topics'
            if not macros:
                return _legacy_topics_to_cards(deck, document_id)
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
    """
    cards: List[Card] = []
    topics = deck.get("topics", [])

    if not topics:
        return _fallback_generate_cards_from_text(deck.get("raw_text", ""), document_id)

    for topic in topics:
        topic_name = topic.get("name", "Untitled Topic")
        for concept in topic.get("concepts", []):
            concept_name = concept.get("name", "Untitled Concept")
            flashcards = concept.get("flashcards", [])
            combined_topic = f"{topic_name} - {concept_name}"

            for fc in flashcards:
                fc_type_str = (fc.get("type") or "definition").lower()

                if fc_type_str == "definition":
                    card_type = CardType.definition
                elif fc_type_str == "cloze" and hasattr(CardType, "cloze"):
                    card_type = CardType.cloze
                elif fc_type_str == "application" and hasattr(CardType, "application"):
                    card_type = CardType.application
                else:
                    # For 'mcq' and any unknown type, fall back to application/definition
                    card_type = getattr(CardType, "application", CardType.definition)

                front = fc.get("front", "").strip()
                back = fc.get("back", "").strip()

                # Map QA difficulty label to a numeric base_difficulty for storage
                # Default to 0.5 (medium) if not provided
                difficulty_label = (fc.get("difficulty") or "medium").lower()
                if difficulty_label == "easy":
                    base_diff = 0.2
                elif difficulty_label == "hard":
                    base_diff = 0.8
                else:
                    base_diff = 0.5

                # If MCQ: render options into front, keep correct answer in back
                if fc_type_str == "mcq":
                    options = fc.get("options", [])
                    correct_idx = fc.get("correct_option_index", 0)
                    if options:
                        labels = ["A", "B", "C", "D", "E", "F"]
                        opts_rendered = []
                        for i, opt in enumerate(options):
            # Simple exclusion keywords for non-flashcard project items
            EXCLUDE = ["student project", "project options", "assignment", "proposal", "deliverable"]

            # Upsert helpers (in-memory cache per document)
            macro_cache = {}
            micro_cache = {}

            def upsert_macro(name: str) -> MacroTopic:
                key = name.strip().lower()
                if key in macro_cache:
                    return macro_cache[key]
                mt = MacroTopic(name=name.strip(), document_id=document_id)
                macro_cache[key] = mt
                return mt

            def upsert_micro(macro: MacroTopic, name: str) -> MicroTopic:
                key = (macro.name.strip().lower(), name.strip().lower())
                if key in micro_cache:
                    return micro_cache[key]
                mct = MicroTopic(name=name.strip(), macro_topic_id=None, document_id=document_id)  # macro id linked on flush
                micro_cache[key] = mct
                return mct

            for macro in macros:
                macro_name = (macro.get("name") or "Uncategorized").strip()
                if any(k in macro_name.lower() for k in EXCLUDE):
                    continue
                mt = upsert_macro(macro_name)
                micros = macro.get("micros") or []
                for micro in micros:
                    micro_name = (micro.get("name") or "General").strip()
                    if any(k in micro_name.lower() for k in EXCLUDE):
                        continue
                    mct = upsert_micro(mt, micro_name)
                    concepts = micro.get("concepts") or []
                    for concept in concepts:
                        concept_name = concept.get("name") or "Concept"
                        flashcards = concept.get("flashcards") or []
                        for fc in flashcards:
                            fc_type = (fc.get("type") or "definition").lower()
                            try:
                                card_type = CardType(fc_type)
                            except Exception:
                                card_type = CardType.definition
                            front = fc.get("front") or ""
                            back = fc.get("back") or ""
                            diff_label = (fc.get("difficulty") or "medium").lower()
                            base_diff = 0.5 if diff_label == "medium" else 0.2 if diff_label == "easy" else 0.8
                            cards.append(
                                Card(
                                    id=str(uuid.uuid4()),
                                    document_id=document_id,
                                    topic=f"{macro_name} - {micro_name}",  # legacy trace
                                    micro_topic=mct,
                                    type=card_type,
                                    front=front,
                                    back=back,
                                    base_difficulty=base_diff,
                                )
                            )

            # Return macro/micro entities first so session can persist relationships alongside cards
            return list(macro_cache.values()) + list(micro_cache.values()) + cards


        def _legacy_topics_to_cards(deck: dict, document_id: str):
            """Legacy path when deck contains 'topics' only."""
            cards = []
            topics = deck.get("topics") or []
            if not topics:
                from uuid import uuid4
                return [
                    Card(
                        id=str(uuid4()),
                        document_id=document_id,
                        topic="Uncategorized - General",
                        type=CardType.definition,
                        front=f"What is the main idea of '{deck.get('document_title', 'Untitled')}'?",
                        back="A study document to learn SCM/Operations concepts.",
                        base_difficulty=0.5,
                    )
                ]
            for topic in topics:
                topic_name = topic.get("name") or "Uncategorized"
                concepts = topic.get("concepts") or []
                for concept in concepts:
                    concept_name = concept.get("name") or "General"
                    flashcards = concept.get("flashcards") or []
                    for fc in flashcards:
                        fc_type = (fc.get("type") or "definition").lower()
                        try:
                            card_type = CardType(fc_type)
                        except Exception:
                            card_type = CardType.definition
                        front = fc.get("front") or ""
                        back = fc.get("back") or ""
                        diff_label = (fc.get("difficulty") or "medium").lower()
                        base_diff = 0.5 if diff_label == "medium" else 0.2 if diff_label == "easy" else 0.8
                        cards.append(
                            Card(
                                id=str(uuid.uuid4()),
                                document_id=document_id,
                                topic=f"{topic_name} - {concept_name}",
                                type=card_type,
                                front=front,
                                back=back,
                                base_difficulty=base_diff,
                            )
                        )
            return cards
                            label = labels[i] if i < len(labels) else str(i + 1)
                            opts_rendered.append(f"{label}) {opt}")
                        front = front + "\nOptions:\n" + "\n".join(opts_rendered)
                        if 0 <= correct_idx < len(options):
                            back = options[correct_idx]

                cards.append(Card(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    topic=combined_topic,
                    type=card_type,
                    front=front or "Question not specified.",
                    back=back or "Answer not specified.",
                    base_difficulty=base_diff,
                ))

    if not cards:
        return _fallback_generate_cards_from_text(deck.get("raw_text", ""), document_id)

    return cards


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
    pdf_bytes = file.file.read()
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

    full_text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]
        full_text += page.get_text()

    pdf_document.close()

    # Run multi-agent pipeline
    try:
        print(f"[INGEST] Running agent pipeline for: {filename}")
        deck = run_flashcard_agent_pipeline(document_text=full_text, title=filename)
        print(f"[INGEST] Agent pipeline completed. Topics: {len(deck.get('topics', []))}")
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

    # Turn deck into Card objects
    cards = _deck_to_cards(deck, document_id=doc_id)

    for card in cards:
        db.add(card)

    db.commit()
    db.refresh(document)

    return document, len(cards)
