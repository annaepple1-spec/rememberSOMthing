"""Topic mastery calculation and management for adaptive learning."""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models import UserTopicState, UserCardState, Card, Review


def calculate_topic_knowledge_score(
    db: Session,
    user_id: str,
    micro_topic_id: int
) -> float:
    """
    Calculate knowledge score (0-100%) for a topic using weighted formula.
    
    Uses Option B: Weight by card.base_difficulty.
    Higher difficulty cards contribute more to the knowledge score.
    
    Formula: 
    knowledge_score = (sum(mastery * difficulty) / sum(difficulty)) * 100
    
    Args:
        db: Database session
        user_id: User identifier
        micro_topic_id: Micro topic ID
        
    Returns:
        Knowledge score percentage (0-100)
    """
    # Get all cards for this topic with their user states
    cards_query = db.query(
        Card.base_difficulty,
        UserCardState.mastery
    ).join(
        UserCardState,
        (Card.id == UserCardState.card_id) & (UserCardState.user_id == user_id)
    ).filter(
        Card.micro_topic_id == micro_topic_id
    )
    
    card_data = cards_query.all()
    
    if not card_data:
        return 0.0
    
    # Weighted calculation
    weighted_sum = sum(mastery * difficulty for difficulty, mastery in card_data)
    total_weight = sum(difficulty for difficulty, mastery in card_data)
    
    if total_weight == 0:
        return 0.0
    
    knowledge_score = (weighted_sum / total_weight) * 100
    return min(100.0, max(0.0, knowledge_score))  # Clamp to 0-100


def calculate_struggle_weight(
    db: Session,
    user_id: str,
    micro_topic_id: int,
    knowledge_score: float
) -> float:
    """
    Calculate struggle weight for prioritizing struggling topics.
    
    Base weight: 1.0
    +0.5 if knowledge_score < 50%
    +0.3 if avg_card_score < 2.0
    +0.4 if > 60% recent failures (score < 2)
    
    Args:
        db: Database session
        user_id: User identifier
        micro_topic_id: Micro topic ID
        knowledge_score: Current knowledge score (0-100)
        
    Returns:
        Struggle weight (1.0+)
    """
    weight = 1.0
    
    # Bonus for low knowledge score
    if knowledge_score < 50.0:
        weight += 0.5
    
    # Get recent reviews for this topic (last 10 reviews)
    recent_reviews = db.query(Review.score).join(
        Card,
        Card.id == Review.card_id
    ).filter(
        Card.micro_topic_id == micro_topic_id,
        Review.user_id == user_id
    ).order_by(
        Review.timestamp.desc()
    ).limit(10).all()
    
    if recent_reviews:
        scores = [r.score for r in recent_reviews]
        avg_score = sum(scores) / len(scores)
        
        # Bonus for low average score
        if avg_score < 2.0:
            weight += 0.3
        
        # Bonus for high failure rate
        failure_rate = sum(1 for s in scores if s < 2) / len(scores)
        if failure_rate > 0.6:
            weight += 0.4
    
    return weight


def update_topic_state(
    db: Session,
    user_id: str,
    micro_topic_id: int
) -> Optional[UserTopicState]:
    """
    Update or create UserTopicState after a card review.
    
    Recalculates knowledge_score, struggle_weight, and statistics.
    
    Args:
        db: Database session
        user_id: User identifier
        micro_topic_id: Micro topic ID
        
    Returns:
        Updated UserTopicState or None if topic has no cards
    """
    # Calculate knowledge score
    knowledge_score = calculate_topic_knowledge_score(db, user_id, micro_topic_id)
    
    # Calculate struggle weight
    struggle_weight = calculate_struggle_weight(db, user_id, micro_topic_id, knowledge_score)
    
    # Count cards seen (cards with at least one review)
    cards_seen = db.query(func.count(func.distinct(Card.id))).join(
        UserCardState,
        (Card.id == UserCardState.card_id) & (UserCardState.user_id == user_id)
    ).filter(
        Card.micro_topic_id == micro_topic_id,
        UserCardState.last_review_at.isnot(None)
    ).scalar() or 0
    
    # Count mastered cards (mastery >= 0.8)
    cards_mastered = db.query(func.count(Card.id)).join(
        UserCardState,
        (Card.id == UserCardState.card_id) & (UserCardState.user_id == user_id)
    ).filter(
        Card.micro_topic_id == micro_topic_id,
        UserCardState.mastery >= 0.8
    ).scalar() or 0
    
    # Calculate average card score from recent reviews
    avg_score_result = db.query(func.avg(Review.score)).join(
        Card,
        Card.id == Review.card_id
    ).filter(
        Card.micro_topic_id == micro_topic_id,
        Review.user_id == user_id
    ).scalar()
    
    avg_card_score = float(avg_score_result) if avg_score_result else 0.0
    
    # Count total reviews
    total_reviews = db.query(func.count(Review.id)).join(
        Card,
        Card.id == Review.card_id
    ).filter(
        Card.micro_topic_id == micro_topic_id,
        Review.user_id == user_id
    ).scalar() or 0
    
    # Get or create UserTopicState
    topic_state = db.query(UserTopicState).filter(
        UserTopicState.user_id == user_id,
        UserTopicState.micro_topic_id == micro_topic_id
    ).first()
    
    if topic_state is None:
        topic_state = UserTopicState(
            user_id=user_id,
            micro_topic_id=micro_topic_id
        )
        db.add(topic_state)
    
    # Update all fields
    topic_state.knowledge_score = knowledge_score
    topic_state.struggle_weight = struggle_weight
    topic_state.cards_seen = cards_seen
    topic_state.cards_mastered = cards_mastered
    topic_state.avg_card_score = avg_card_score
    topic_state.total_reviews = total_reviews
    topic_state.last_practice_at = datetime.utcnow()
    
    db.commit()
    db.refresh(topic_state)
    
    return topic_state
