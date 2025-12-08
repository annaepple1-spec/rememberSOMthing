from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas import CardOut, AnswerRequest, AnswerResponse
from backend.services.review import get_next_card, handle_answer, DEMO_USER_ID
from backend.services.adaptive_selection import get_next_card_adaptive

router = APIRouter(prefix="/session", tags=["session"])


@router.get("/next-card", response_model=Optional[CardOut])
def next_card(document_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get the next card for the user to review.
    
    Returns the next due card or a new card if no cards are due.
    Returns null if there are no cards available.
    
    Args:
        document_id: Optional document ID to filter cards by specific document
    """
    card = get_next_card(db, document_id=document_id)
    if card:
        return CardOut(
            id=card.id,
            front=card.front,
            back=card.back,
            type=card.type.value,
            topic=card.topic
        )
    return None


@router.get("/next-card-adaptive", response_model=Optional[CardOut])
def next_card_adaptive(document_id: str, db: Session = Depends(get_db)):
    """
    Get the next card using adaptive learning algorithm.
    
    Uses 80/20 struggling topic prioritization with difficulty progression:
    - <40% knowledge: only easy cards
    - 40-60% knowledge: easy and medium cards
    - >60% knowledge: all difficulties
    
    Args:
        document_id: Required document ID for adaptive selection
        
    Returns:
        CardOut or None if no cards available
    """
    if not document_id:
        raise HTTPException(status_code=400, detail="document_id is required for adaptive card selection")
    
    card = get_next_card_adaptive(db, DEMO_USER_ID, document_id)
    
    if card:
        return CardOut(
            id=card.id,
            front=card.front,
            back=card.back,
            type=card.type.value,
            topic=card.topic
        )
    return None


@router.post("/answer", response_model=AnswerResponse)
def answer(answer_request: AnswerRequest, db: Session = Depends(get_db)):
    """
    Submit an answer for a card and receive grading feedback.
    
    Updates the user's progress and schedules the next review.
    """
    result = handle_answer(
        db,
        answer_request.card_id,
        answer_request.user_answer,
        answer_request.latency_ms
    )
    
    return AnswerResponse(
        score=result["score"],
        explanation=result["explanation"]
    )
