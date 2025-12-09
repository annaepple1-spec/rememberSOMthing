"""Router for PDF upload and card generation."""
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.ingest import process_pdf
from backend.models import Document, Card, UserCardState, Review, MacroTopic, MicroTopic

router = APIRouter(prefix="/upload", tags=["upload"])


def cleanup_old_documents(db: Session, max_documents: int = 5):
    """
    Keep only the most recent N documents, delete older ones with all related data.

    Args:
        db: Database session
        max_documents: Maximum number of documents to keep (default 5)
    """
    # Get all documents ordered by creation date (newest first)
    all_docs = db.query(Document).order_by(Document.created_at.desc()).all()

    if len(all_docs) <= max_documents:
        return  # Nothing to clean up

    # Documents to delete (older than the max_documents limit)
    docs_to_delete = all_docs[max_documents:]
    doc_ids_to_delete = [doc.id for doc in docs_to_delete]

    print(f"[CLEANUP] Deleting {len(docs_to_delete)} old documents: {[doc.title for doc in docs_to_delete]}")

    # Get card IDs for these documents
    card_ids = [card.id for doc_id in doc_ids_to_delete
                for card in db.query(Card).filter(Card.document_id == doc_id).all()]

    # Delete related data in correct order (foreign key constraints)
    if card_ids:
        # Delete reviews
        db.query(Review).filter(Review.card_id.in_(card_ids)).delete(synchronize_session=False)
        # Delete user card states
        db.query(UserCardState).filter(UserCardState.card_id.in_(card_ids)).delete(synchronize_session=False)

    # Get micro topic IDs for these documents
    micro_topic_ids = [mt.id for doc_id in doc_ids_to_delete
                       for mt in db.query(MicroTopic).filter(MicroTopic.macro_topic.has(document_id=doc_id)).all()]

    # Delete cards
    db.query(Card).filter(Card.document_id.in_(doc_ids_to_delete)).delete(synchronize_session=False)

    # Delete micro topics
    if micro_topic_ids:
        db.query(MicroTopic).filter(MicroTopic.id.in_(micro_topic_ids)).delete(synchronize_session=False)

    # Delete macro topics
    db.query(MacroTopic).filter(MacroTopic.document_id.in_(doc_ids_to_delete)).delete(synchronize_session=False)

    # Delete documents
    db.query(Document).filter(Document.id.in_(doc_ids_to_delete)).delete(synchronize_session=False)

    db.commit()
    print(f"[CLEANUP] Cleanup complete")


@router.post("/pdf")
def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a PDF file and automatically generate flashcards from its content.
    Keeps only the 5 most recent uploads.

    Returns:
        JSON with document_id, title, and number of cards created
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    try:
        document, cards_created, chunks_created, rag_success = process_pdf(file, db)

        # Clean up old documents after successful upload
        cleanup_old_documents(db, max_documents=5)

        return {
            "document_id": document.id,
            "title": document.title,
            "cards_created": cards_created,
            "chatbot_enabled": rag_success,
            "chunks_created": chunks_created
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[UPLOAD ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")
