"""Adaptive card selection for personalized learning paths."""

import random
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta

from backend.models import Card, UserCardState, UserTopicState, MicroTopic


def get_allowed_difficulties(knowledge_score: float) -> List[str]:
    """
    Determine which difficulty levels are unlocked based on topic knowledge.

    - < 40%: Only "easy" cards
    - 40-60%: "easy" and "medium" cards
    - > 60%: All difficulties ("easy", "medium", "hard")

    Args:
        knowledge_score: Topic knowledge score (0-100%)

    Returns:
        List of allowed difficulty strings
    """
    if knowledge_score < 40.0:
        return ["easy"]
    elif knowledge_score < 60.0:
        return ["easy", "medium"]
    else:
        return ["easy", "medium", "hard"]


def _map_difficulty_to_range(difficulty: str) -> tuple:
    """Map difficulty string to base_difficulty range."""
    difficulty_ranges = {
        "easy": (0.0, 0.4),
        "medium": (0.4, 0.7),
        "hard": (0.7, 1.0)
    }
    return difficulty_ranges.get(difficulty, (0.0, 1.0))


def get_next_card_adaptive(
    db: Session,
    user_id: str,
    document_id: str
) -> Optional[Card]:
    """
    Select next card using adaptive algorithm with 80/20 struggling topic prioritization.

    Algorithm:
    1. Get all topics for document with their struggle weights
    2. 80% chance: Select from struggling topics (weighted by struggle_weight)
    3. 20% chance: Select from any topic (random)
    4. Filter cards by allowed difficulty based on topic knowledge_score
    5. Prioritize due cards over new cards
    6. Within priority group, select randomly

    Args:
        db: Database session
        user_id: User identifier
        document_id: Document ID to select cards from

    Returns:
        Selected Card or None if no cards available
    """
    # Get all micro topics for this document with their states
    topic_states = db.query(
        UserTopicState,
        MicroTopic
    ).join(
        MicroTopic,
        MicroTopic.id == UserTopicState.micro_topic_id
    ).filter(
        MicroTopic.document_id == document_id,
        UserTopicState.user_id == user_id
    ).all()

    # If no topic states exist yet, initialize them for all topics
    if not topic_states:
        from backend.services.topic_mastery import update_topic_state

        all_topics = db.query(MicroTopic).filter(
            MicroTopic.document_id == document_id
        ).all()

        for topic in all_topics:
            # This will create initial state for topics with cards
            update_topic_state(db, user_id, topic.id)

        # Re-query after initialization
        topic_states = db.query(
            UserTopicState,
            MicroTopic
        ).join(
            MicroTopic,
            MicroTopic.id == UserTopicState.micro_topic_id
        ).filter(
            MicroTopic.document_id == document_id,
            UserTopicState.user_id == user_id
        ).all()

    if not topic_states:
        # Fallback: No topics with cards, return None
        return None

    # Decide: 50% struggling topics, 50% random (more balanced for better topic diversity)
    use_struggling = random.random() < 0.5

    if use_struggling and len(topic_states) > 1:
        # Sort by struggle_weight descending and pick from top struggling topics
        struggling_topics = sorted(
            topic_states,
            key=lambda x: x[0].struggle_weight,
            reverse=True
        )

        # Take top 50% as "struggling" pool (minimum 2 topics for better variety)
        pool_size = max(2, int(len(struggling_topics) * 0.5))
        topic_pool = struggling_topics[:pool_size]

        # Weighted random selection from struggling pool
        weights = [state.struggle_weight for state, _ in topic_pool]
        selected_state, selected_topic = random.choices(
            topic_pool,
            weights=weights,
            k=1
        )[0]
    else:
        # Random topic selection (50% path or only 1 topic)
        selected_state, selected_topic = random.choice(topic_states)

    # Get allowed difficulties for selected topic
    allowed_difficulties = get_allowed_difficulties(selected_state.knowledge_score)

    # Build difficulty filter conditions
    difficulty_conditions = []
    for diff in allowed_difficulties:
        min_diff, max_diff = _map_difficulty_to_range(diff)
        difficulty_conditions.append(
            and_(
                Card.base_difficulty >= min_diff,
                Card.base_difficulty < max_diff
            )
        )

    # Query cards for this topic with difficulty filter
    # Exclude cards reviewed in the last 5 minutes to prevent immediate repetition
    recently_reviewed_threshold = datetime.utcnow() - timedelta(minutes=5)

    base_query = db.query(Card).outerjoin(
        UserCardState,
        and_(
            Card.id == UserCardState.card_id,
            UserCardState.user_id == user_id
        )
    ).filter(
        Card.micro_topic_id == selected_topic.id,
        or_(*difficulty_conditions) if difficulty_conditions else True,
        or_(
            UserCardState.last_review_at.is_(None),
            UserCardState.last_review_at <= recently_reviewed_threshold
        )
    )

    # Priority 1: Due cards (next_due_at <= now)
    # Prioritize by lowest mastery (failed cards first)
    due_cards = base_query.filter(
        UserCardState.next_due_at.isnot(None),
        UserCardState.next_due_at <= datetime.utcnow()
    ).order_by(
        UserCardState.mastery.asc(),  # Lowest mastery first (failed cards)
        UserCardState.interval_days.asc()  # Then shortest intervals (most urgent)
    ).all()

    if due_cards:
        # If there are failed cards (mastery < 0.3), strongly prioritize them
        failed_cards = [c for c in due_cards[:10] if db.query(UserCardState).filter(
            UserCardState.card_id == c.id,
            UserCardState.user_id == user_id,
            UserCardState.mastery < 0.3
        ).first()]

        if failed_cards:
            return random.choice(failed_cards[:3])  # Random from top 3 failed cards

        return random.choice(due_cards[:5])  # Random from top 5 due cards

    # Priority 2: New cards (never reviewed)
    new_cards = base_query.filter(
        or_(
            UserCardState.card_id.is_(None),
            UserCardState.last_review_at.is_(None)
        )
    ).limit(10).all()

    if new_cards:
        return random.choice(new_cards)

    # Priority 3: Recently reviewed cards (if no due/new cards available)
    # Return cards that are closest to being due (for continuous practice)
    # Still exclude cards from last 5 minutes
    recent_cards = base_query.filter(
        UserCardState.card_id.isnot(None)
    ).order_by(
        UserCardState.next_due_at.asc()  # Cards closest to being due first
    ).limit(10).all()

    if recent_cards:
        return random.choice(recent_cards[:3])  # Random from top 3 closest to due

    # Priority 4: If no cards available (all shown recently), return any card from this topic
    # This is a final fallback to ensure continuous practice
    fallback_query = db.query(Card).filter(
        Card.micro_topic_id == selected_topic.id,
        or_(*difficulty_conditions) if difficulty_conditions else True
    ).limit(10).all()

    if fallback_query:
        return random.choice(fallback_query)

    # Priority 5: No cards available with current difficulty restrictions
    return None
