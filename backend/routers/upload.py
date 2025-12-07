"""Router for PDF upload and card generation."""
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
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
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")
    
    try:
        document, cards_created = process_pdf(file, db)
        
        return {
            "document_id": document.id,
            "title": document.title,
            "cards_created": cards_created
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[UPLOAD ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")
