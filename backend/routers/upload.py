"""Router for PDF upload and card generation."""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.ingest import process_pdf

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/pdf")
def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a PDF file and automatically generate flashcards from its content.
    
    Returns:
        JSON with document_id, title, and number of cards created
    """
    document, cards_created = process_pdf(file, db)
    
    return {
        "document_id": document.id,
        "title": document.title,
        "cards_created": cards_created
    }
