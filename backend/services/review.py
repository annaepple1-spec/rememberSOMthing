import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from backend.models import Card, UserCardState, Review
from backend.services.llm import grade_answer
from backend.services.scheduler import update_card_state

# Demo user ID for testing (no authentication yet)
DEMO_USER_ID = "demo-user"


def get_next_card(db: Session, document_id: Optional[str] = None) -> Optional[Card]:
    """
    Get the next card for the user to review.
    
    Priority:
    1. Due cards (next_due_at <= now), ordered by lowest mastery first
    2. New cards (no UserCardState yet)
    
    Args:
        db: Database session
        document_id: Optional document ID to filter cards by specific document
        
    Returns:
        Card or None if no cards available
    """
    now = datetime.utcnow()
    
    # Look for due cards
    due_query = db.query(UserCardState).filter(
        UserCardState.user_id == DEMO_USER_ID,
        UserCardState.next_due_at <= now
    )
    
    # If document_id provided, filter by document
    if document_id:
        due_query = due_query.join(Card).filter(Card.document_id == document_id)
    
    due_state = due_query.order_by(UserCardState.mastery.asc()).first()
    
    if due_state:
        # Return the card associated with this state
        return db.query(Card).filter(Card.id == due_state.card_id).first()
    
    # Look for new cards (cards without a UserCardState for this user)
    existing_card_ids = db.query(UserCardState.card_id).filter(
        UserCardState.user_id == DEMO_USER_ID
    ).subquery()
    
    new_card_query = db.query(Card).filter(
        ~Card.id.in_(existing_card_ids)
    )
    
    # If document_id provided, filter by document
    if document_id:
        new_card_query = new_card_query.filter(Card.document_id == document_id)
    
    new_card = new_card_query.first()
    
    return new_card


def handle_answer(
    db: Session, 
    card_id: str, 
    user_answer: str, 
    latency_ms: int
) -> dict:
    """
    Handle a user's answer to a card.
    
    Steps:
    1. Load the card
    2. Grade the answer
    3. Update or create UserCardState
    4. Create Review record
    5. Commit and return grading result
    
    Args:
        db: Database session
        card_id: ID of the card being answered
        user_answer: The user's answer text
        latency_ms: Time taken to answer in milliseconds
        
    Returns:
        dict with score and explanation
    """
    # Load the card
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise ValueError(f"Card {card_id} not found")
    
    # Grade the answer
    grading_result = grade_answer(card.front, card.back, user_answer)
    score = grading_result["score"]
    explanation = grading_result["explanation"]
    
    # Get or create UserCardState
    state = db.query(UserCardState).filter(
        UserCardState.user_id == DEMO_USER_ID,
        UserCardState.card_id == card_id
    ).first()
    
    if not state:
        state = UserCardState(
            user_id=DEMO_USER_ID,
            card_id=card_id
        )
        db.add(state)
    
    # Update the card state
    now = datetime.utcnow()
    update_card_state(state, score, now)
    
    # Create a review record
    review = Review(
        id=str(uuid.uuid4()),
        user_id=DEMO_USER_ID,
        card_id=card_id,
        timestamp=now,
        score=score,
        latency_ms=latency_ms
    )
    db.add(review)
    
    # Commit the transaction
    db.commit()
    
    return {
        "score": score,
        "explanation": explanation
    }
