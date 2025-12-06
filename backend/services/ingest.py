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
