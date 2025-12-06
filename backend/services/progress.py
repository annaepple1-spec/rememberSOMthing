"""Service for calculating user progress on documents."""
from sqlalchemy.orm import Session
from backend.models import Card, UserCardState
from backend.models import MicroTopic, MacroTopic


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


def macro_progress(db: Session, document_id: str, user_id: str):
    """Aggregate progress per macro topic for a document."""
    macros = db.query(MacroTopic).filter(MacroTopic.document_id == document_id).all()
    result = []
    for macro in macros:
        micro_ids = [m.id for m in db.query(MicroTopic.id).filter(MicroTopic.macro_topic_id == macro.id).all()]
        if not micro_ids:
            result.append({"macro_topic_id": macro.id, "name": macro.name, "total_cards": 0, "reviewed_cards": 0, "accuracy": 0.0, "last_reviewed_at": None})
            continue
        cards = db.query(Card).filter(Card.micro_topic_id.in_(micro_ids)).all()
        total = len(cards)
        card_ids = [c.id for c in cards]
        states = db.query(UserCardState).filter(UserCardState.user_id == user_id, UserCardState.card_id.in_(card_ids)).all()
        reviewed = len([s for s in states if s.repetitions and s.repetitions > 0])
        accuracy = sum((s.last_score or 0) for s in states) / (3 * reviewed) if reviewed else 0.0
        last_reviewed = max((s.last_review_at for s in states if s.last_review_at), default=None)
        result.append({"macro_topic_id": macro.id, "name": macro.name, "total_cards": total, "reviewed_cards": reviewed, "accuracy": round(accuracy * 100, 1), "last_reviewed_at": last_reviewed})
    return result


def micro_progress(db: Session, macro_topic_id: int, user_id: str):
    """Aggregate progress per micro topic for a macro topic."""
    micros = db.query(MicroTopic).filter(MicroTopic.macro_topic_id == macro_topic_id).all()
    result = []
    for micro in micros:
        cards = db.query(Card).filter(Card.micro_topic_id == micro.id).all()
        total = len(cards)
        card_ids = [c.id for c in cards]
        states = db.query(UserCardState).filter(UserCardState.user_id == user_id, UserCardState.card_id.in_(card_ids)).all()
        reviewed = len([s for s in states if s.repetitions and s.repetitions > 0])
        accuracy = sum((s.last_score or 0) for s in states) / (3 * reviewed) if reviewed else 0.0
        last_reviewed = max((s.last_review_at for s in states if s.last_review_at), default=None)
        result.append({"micro_topic_id": micro.id, "name": micro.name, "total_cards": total, "reviewed_cards": reviewed, "accuracy": round(accuracy * 100, 1), "last_reviewed_at": last_reviewed})
    return result
