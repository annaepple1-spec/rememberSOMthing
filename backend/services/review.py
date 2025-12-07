import uuid
from datetime import datetime
from typing import Optional, Union
from sqlalchemy.orm import Session
import Levenshtein

from backend.models import Card, UserCardState, Review, CardType
from backend.services.llm import grade_answer
from backend.services.scheduler import update_card_state
from backend.services.topic_mastery import update_topic_state

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


def grade_answer_by_type(
    card: Card,
    user_answer: Union[str, int]
) -> dict:
    """
    Grade answer based on card type (Option A: card-type-specific grading).
    
    - MCQ: exact match on option index (0-3)
    - Cloze: fuzzy text matching with Levenshtein distance
    - Definition/Application: self-reported score (0-3)
    
    Args:
        card: The card being answered
        user_answer: For MCQ: int (option index), Cloze: str (text), Definition/Application: int (self-grade)
        
    Returns:
        dict with score (0-3) and explanation
    """
    if card.type == CardType.mcq:
        # MCQ: Check if selected option matches correct_option_index
        if not isinstance(user_answer, int):
            return {"score": 0, "explanation": "Invalid MCQ answer format"}
        
        if user_answer == card.correct_option_index:
            return {"score": 3, "explanation": "Correct!"}
        else:
            return {"score": 0, "explanation": f"Incorrect. The correct answer is option {chr(65 + card.correct_option_index)}."}
    
    elif card.type == CardType.cloze:
        # Cloze: Fuzzy matching with Levenshtein distance
        if not isinstance(user_answer, str):
            return {"score": 0, "explanation": "Invalid cloze answer format"}
        
        # Normalize strings for comparison
        user_text = user_answer.strip().lower()
        correct_text = card.back.strip().lower()
        
        # Calculate edit distance
        distance = Levenshtein.distance(user_text, correct_text)
        
        # Score based on distance thresholds
        if distance <= 2:
            score = 3
            explanation = "Perfect! Your answer is correct."
        elif distance <= 4:
            score = 2
            explanation = f"Close! Minor differences detected. Expected: '{card.back}'"
        elif distance <= 6:
            score = 1
            explanation = f"Partially correct. Expected: '{card.back}'"
        else:
            score = 0
            explanation = f"Incorrect. The correct answer is: '{card.back}'"
        
        return {"score": score, "explanation": explanation}
    
    elif card.type in (CardType.definition, CardType.application, CardType.connection):
        # Self-grading: Accept user-reported score (0-3)
        if not isinstance(user_answer, int) or user_answer not in (0, 1, 2, 3):
            return {"score": 0, "explanation": "Invalid self-grade score"}
        
        return {"score": user_answer, "explanation": f"Self-graded as {user_answer}/3"}
    
    else:
        # Fallback to LLM grading for unknown types
        if isinstance(user_answer, str):
            return grade_answer(card.front, card.back, user_answer)
        else:
            return {"score": 0, "explanation": "Unknown card type"}


def handle_answer(
    db: Session, 
    card_id: str, 
    user_answer: Union[str, int], 
    latency_ms: int
) -> dict:
    """
    Handle a user's answer to a card with card-type-specific grading.
    
    Steps:
    1. Load the card
    2. Grade the answer based on card type
    3. Update or create UserCardState
    4. Update topic mastery state
    5. Create Review record
    6. Commit and return grading result
    
    Args:
        db: Database session
        card_id: ID of the card being answered
        user_answer: For MCQ: int (0-3), Cloze: str, Definition/Application: int (0-3)
        latency_ms: Time taken to answer in milliseconds
        
    Returns:
        dict with score and explanation
    """
    # Load the card
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise ValueError(f"Card {card_id} not found")
    
    # Grade the answer using card-type-specific logic
    grading_result = grade_answer_by_type(card, user_answer)
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
    
    # Commit review and card state first
    db.commit()
    
    # Update topic mastery state (if card has micro_topic_id)
    if card.micro_topic_id:
        update_topic_state(db, DEMO_USER_ID, card.micro_topic_id)
    
    return {
        "score": score,
        "explanation": explanation
    }
