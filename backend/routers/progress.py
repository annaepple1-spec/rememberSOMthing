"""Router for tracking user progress on documents."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Document, Card
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


@router.get("/browse")
def browse_all_cards(db: Session = Depends(get_db)):
    """
    Browse all documents and their cards organized by topics.
    
    Returns all documents with their cards grouped by topic metadata.
    Useful for students to review what cards exist before studying.
    
    Returns:
        List of documents, each containing topics with their cards
    """
    documents = db.query(Document).all()
    
    result = []
    for doc in documents:
        # Get all cards for this document
        cards = db.query(Card).filter(Card.document_id == doc.id).order_by(Card.id).all()
        
        # Group cards by topic
        topics_map = {}
        for card in cards:
            topic_name = card.topic or "Uncategorized"
            if topic_name not in topics_map:
                topics_map[topic_name] = []
            
            # Map card type enum to string for frontend
            type_str = str(card.type.value) if hasattr(card.type, 'value') else str(card.type)
            # Map base_difficulty numeric to label
            if card.base_difficulty is None:
                diff_label = "medium"
            elif card.base_difficulty <= 0.33:
                diff_label = "easy"
            elif card.base_difficulty >= 0.67:
                diff_label = "hard"
            else:
                diff_label = "medium"

            topics_map[topic_name].append({
                "id": card.id,
                "type": type_str,
                "front": card.front,
                "back": card.back,
                "difficulty": diff_label
            })
        
        # Convert to list format
        topics_list = [
            {
                "name": topic_name,
                "cards": card_list
            }
            for topic_name, card_list in topics_map.items()
        ]
        
        result.append({
            "document_id": doc.id,
            "title": doc.title,
            "total_cards": len(cards),
            "topics": topics_list
        })
    
    return {"documents": result}
