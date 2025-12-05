"""Router for tracking user progress on documents."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Document
from backend.services.progress import document_progress

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/document/{doc_id}")
def get_document_progress(doc_id: str, db: Session = Depends(get_db)):
    """
    Get the user's mastery progress for a specific document.
    
    Returns mastery percentage (0-100) based on:
    - Average mastery of reviewed cards
    - Coverage (proportion of cards reviewed)
    
    Args:
        doc_id: Document ID to check progress for
        
    Returns:
        JSON with document_id, title, and mastery_percent
    """
    # Fetch the document
    document = db.query(Document).filter(Document.id == doc_id).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Calculate progress
    mastery_percent = document_progress(db, doc_id, user_id="demo-user")
    
    return {
        "document_id": document.id,
        "title": document.title,
        "mastery_percent": mastery_percent
    }
