"""Service for calculating user progress on documents."""
from sqlalchemy.orm import Session
from backend.models import Card, UserCardState


def document_progress(db: Session, document_id: str, user_id: str = "demo-user") -> float:
    """
    Compute mastery percentage (0-100) for a given document and user.
    
    Formula:
    - seen_mastery = average mastery over cards reviewed at least once
    - coverage = number of reviewed cards / total cards
    - document_mastery = seen_mastery * coverage
    - mastery_percent = document_mastery * 100.0
    
    Args:
        db: Database session
        document_id: ID of the document to check progress for
        user_id: User ID (defaults to "demo-user")
        
    Returns:
        Mastery percentage from 0.0 to 100.0
    """
    # Get all cards for this document
    all_cards = db.query(Card).filter(Card.document_id == document_id).all()
    
    if not all_cards:
        return 0.0
    
    total_cards = len(all_cards)
    card_ids = [card.id for card in all_cards]
    
    # Get UserCardState for these cards and this user
    states = db.query(UserCardState).filter(
        UserCardState.user_id == user_id,
        UserCardState.card_id.in_(card_ids)
    ).all()
    
    # Filter to only cards that have been reviewed (repetitions > 0)
    seen_states = [state for state in states if state.repetitions > 0]
    
    if not seen_states:
        return 0.0
    
    # Calculate seen_mastery: average mastery over reviewed cards
    seen_mastery = sum(state.mastery for state in seen_states) / len(seen_states)
    
    # Calculate coverage: proportion of cards reviewed
    coverage = len(seen_states) / total_cards
    
    # Calculate final mastery percentage
    document_mastery = seen_mastery * coverage
    mastery_percent = document_mastery * 100.0
    
    return mastery_percent
