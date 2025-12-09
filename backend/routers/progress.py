"""Router for tracking user progress on documents."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Document, Card, MacroTopic, MicroTopic, UserCardState, Review, DocumentChunk
from backend.services.progress import document_progress, macro_progress, micro_progress

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/overall")
def get_overall_stats(db: Session = Depends(get_db), user_id: str = "demo-user", document_id: Optional[str] = None):
    """
    Get overall study statistics across all documents or for a specific document.

    Args:
        document_id: Optional document ID to filter stats

    Returns:
        - total_cards: Total number of cards
        - cards_studied: Number of cards reviewed at least once
        - cards_never_seen: Number of cards never reviewed
        - percent_studied: Percentage of cards studied
    """
    # Get total cards (optionally filtered by document)
    cards_query = db.query(Card)
    if document_id:
        cards_query = cards_query.filter(Card.document_id == document_id)

    total_cards = cards_query.count()

    if total_cards == 0:
        return {
            "total_cards": 0,
            "cards_studied": 0,
            "cards_never_seen": 0,
            "percent_studied": 0.0
        }

    # Get all card IDs
    all_card_ids = [c.id for c in cards_query.with_entities(Card.id).all()]

    # Get user card states for studied cards (repetitions > 0)
    studied_states = db.query(UserCardState).filter(
        UserCardState.user_id == user_id,
        UserCardState.card_id.in_(all_card_ids),
        UserCardState.repetitions > 0
    ).all()

    cards_studied = len(studied_states)
    cards_never_seen = total_cards - cards_studied
    percent_studied = (cards_studied / total_cards * 100) if total_cards > 0 else 0.0

    return {
        "total_cards": total_cards,
        "cards_studied": cards_studied,
        "cards_never_seen": cards_never_seen,
        "percent_studied": round(percent_studied, 1)
    }


@router.get("/mastery-distribution")
def get_mastery_distribution(db: Session = Depends(get_db), user_id: str = "demo-user", document_id: Optional[str] = None):
    """
    Get distribution of cards across mastery levels (0-3).

    Args:
        document_id: Optional document ID to filter distribution

    Mastery level is determined by last_score:
    - 0: No idea / Complete blackout
    - 1: Barely remembered / Hesitant
    - 2: Good recall / Minor hesitation
    - 3: Perfect recall / Immediate

    Returns:
        - level_0: Count of cards with mastery 0
        - level_1: Count of cards with mastery 1
        - level_2: Count of cards with mastery 2
        - level_3: Count of cards with mastery 3
        - never_seen: Count of cards never studied
        - total_studied: Total cards with at least one review
    """
    # Get all card IDs (optionally filtered by document)
    cards_query = db.query(Card.id)
    if document_id:
        cards_query = cards_query.filter(Card.document_id == document_id)

    all_card_ids = [c.id for c in cards_query.all()]
    total_cards = len(all_card_ids)

    if total_cards == 0:
        return {
            "level_0": 0,
            "level_1": 0,
            "level_2": 0,
            "level_3": 0,
            "never_seen": 0,
            "total_studied": 0
        }

    # Get user card states for all cards
    states = db.query(UserCardState).filter(
        UserCardState.user_id == user_id,
        UserCardState.card_id.in_(all_card_ids)
    ).all()

    # Create a map of card_id -> state
    state_map = {state.card_id: state for state in states}

    # Count cards at each mastery level
    level_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    studied_cards = 0

    for card_id in all_card_ids:
        state = state_map.get(card_id)
        if state and state.repetitions and state.repetitions > 0:
            studied_cards += 1
            # Use last_score to determine mastery level
            score = state.last_score if state.last_score is not None else 0
            level_counts[score] = level_counts.get(score, 0) + 1

    never_seen = total_cards - studied_cards

    return {
        "level_0": level_counts[0],
        "level_1": level_counts[1],
        "level_2": level_counts[2],
        "level_3": level_counts[3],
        "never_seen": never_seen,
        "total_studied": studied_cards
    }


@router.get("/all-documents-progress")
def get_all_documents_progress(db: Session = Depends(get_db), user_id: str = "demo-user"):
    """
    Get progress for all documents.

    Returns a list of documents with their progress metrics:
    - document_id, title
    - total_cards: Number of cards in document
    - cards_studied: Number of cards reviewed at least once
    - mastery_percent: Overall mastery percentage (0-100)
    - last_studied: Most recent study date for any card in document

    Returns:
        List of document progress objects
    """
    from datetime import datetime

    # Get all documents
    documents = db.query(Document).all()

    result = []
    for doc in documents:
        # Skip demo/sample documents
        title_lower = (doc.title or '').lower()
        if 'demo' in title_lower or 'sample' in title_lower or 'example' in title_lower:
            continue

        # Get all cards for this document
        cards = db.query(Card).filter(Card.document_id == doc.id).all()
        total_cards = len(cards)

        if total_cards == 0:
            continue

        card_ids = [c.id for c in cards]

        # Get user card states
        states = db.query(UserCardState).filter(
            UserCardState.user_id == user_id,
            UserCardState.card_id.in_(card_ids)
        ).all()

        # Count studied cards and find last study date
        studied_states = [s for s in states if s.repetitions and s.repetitions > 0]
        cards_studied = len(studied_states)

        # Find most recent study date
        last_studied = None
        if studied_states:
            dates = [s.last_review_at for s in studied_states if s.last_review_at]
            if dates:
                last_studied = max(dates)

        # Calculate mastery using the existing service function
        mastery_percent = document_progress(db, doc.id, user_id)

        result.append({
            "document_id": doc.id,
            "title": doc.title,
            "total_cards": total_cards,
            "cards_studied": cards_studied,
            "mastery_percent": round(mastery_percent, 1),
            "last_studied": last_studied.isoformat() if last_studied else None
        })

    # Sort by last studied (most recent first), then by title
    result.sort(key=lambda x: (x['last_studied'] is None, x['last_studied'] or '', x['title']), reverse=True)

    return {"documents": result}


@router.get("/macro-topics-progress/{document_id}")
def get_macro_topics_progress(document_id: str, db: Session = Depends(get_db), user_id: str = "demo-user"):
    """
    Get progress breakdown by macro topics for a specific document.

    Args:
        document_id: Document ID to get macro topic progress for

    Returns:
        List of macro topics with their progress metrics:
        - macro_topic_id, name
        - total_cards: Number of cards in this macro topic
        - cards_studied: Number of cards reviewed at least once
        - mastery_percent: Average mastery for this macro topic
        - last_studied: Most recent study date for any card in this macro
    """
    from datetime import datetime

    # Verify document exists
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get all macro topics for this document
    macros = db.query(MacroTopic).filter(MacroTopic.document_id == document_id).all()

    if not macros:
        return {"document_title": document.title, "macros": []}

    result = []
    for macro in macros:
        # Get all micro topics under this macro
        micro_ids = [m.id for m in db.query(MicroTopic.id).filter(MicroTopic.macro_topic_id == macro.id).all()]

        if not micro_ids:
            continue

        # Get all cards for these micro topics
        cards = db.query(Card).filter(Card.micro_topic_id.in_(micro_ids)).all()
        total_cards = len(cards)

        if total_cards == 0:
            continue

        card_ids = [c.id for c in cards]

        # Get user card states
        states = db.query(UserCardState).filter(
            UserCardState.user_id == user_id,
            UserCardState.card_id.in_(card_ids)
        ).all()

        # Count studied cards and find last study date
        studied_states = [s for s in states if s.repetitions and s.repetitions > 0]
        cards_studied = len(studied_states)

        # Find most recent study date
        last_studied = None
        if studied_states:
            dates = [s.last_review_at for s in studied_states if s.last_review_at]
            if dates:
                last_studied = max(dates)

        # Calculate mastery percentage
        if not studied_states:
            mastery_percent = 0.0
        else:
            # Average mastery of studied cards
            seen_mastery = sum(s.mastery for s in studied_states) / len(studied_states)
            # Coverage (proportion of cards studied)
            coverage = len(studied_states) / total_cards
            # Combined metric
            mastery_percent = seen_mastery * coverage * 100.0

        result.append({
            "macro_topic_id": macro.id,
            "name": macro.name,
            "total_cards": total_cards,
            "cards_studied": cards_studied,
            "mastery_percent": round(mastery_percent, 1),
            "last_studied": last_studied.isoformat() if last_studied else None
        })

    # Sort by last studied (most recent first), then by name
    result.sort(key=lambda x: (x['last_studied'] is None, x['last_studied'] or '', x['name']), reverse=True)

    return {"document_title": document.title, "macros": result}


@router.get("/spaced-repetition-metrics")
def get_spaced_repetition_metrics(db: Session = Depends(get_db), user_id: str = "demo-user", document_id: Optional[str] = None):
    """
    Get spaced repetition metrics for tracking review schedule.

    Args:
        document_id: Optional document ID to filter metrics

    Returns:
        - cards_due_today: Cards due for review today (including overdue)
        - cards_overdue: Cards that were due before today
        - cards_due_soon: Cards due in the next 7 days
        - average_interval: Average time between reviews (in days)
        - retention_rate: Percentage of reviews that improved or maintained mastery
        - total_reviews: Total number of reviews completed
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    today_end = today_start + timedelta(days=1)
    seven_days = today_end + timedelta(days=7)

    # Base query for user card states
    states_query = db.query(UserCardState).filter(
        UserCardState.user_id == user_id,
        UserCardState.next_due_at.isnot(None)
    )

    # Filter by document if provided
    if document_id:
        states_query = states_query.join(Card).filter(Card.document_id == document_id)

    all_states = states_query.all()

    # Count cards due today (including overdue)
    cards_due_today = len([s for s in all_states if s.next_due_at <= today_end])

    # Count overdue cards (due before today)
    cards_overdue = len([s for s in all_states if s.next_due_at < today_start])

    # Count cards due soon (next 7 days, excluding today)
    cards_due_soon = len([s for s in all_states if today_end < s.next_due_at <= seven_days])

    # Calculate average interval
    intervals = [s.interval_days for s in all_states if s.interval_days and s.interval_days > 0]
    average_interval = sum(intervals) / len(intervals) if intervals else 0.0

    # Calculate retention rate from reviews
    reviews_query = db.query(Review).filter(Review.user_id == user_id)
    if document_id:
        reviews_query = reviews_query.join(Card).filter(Card.document_id == document_id)

    reviews = reviews_query.order_by(Review.timestamp).all()
    total_reviews = len(reviews)

    # Group reviews by card to track progression
    from collections import defaultdict
    card_reviews = defaultdict(list)
    for review in reviews:
        card_reviews[review.card_id].append(review.score)

    # Count reviews that maintained or improved (score >= previous score)
    retention_count = 0
    comparison_count = 0

    for card_id, scores in card_reviews.items():
        for i in range(1, len(scores)):
            comparison_count += 1
            if scores[i] >= scores[i-1]:  # Maintained or improved
                retention_count += 1

    retention_rate = (retention_count / comparison_count * 100) if comparison_count > 0 else 0.0

    return {
        "cards_due_today": cards_due_today,
        "cards_overdue": cards_overdue,
        "cards_due_soon": cards_due_soon,
        "average_interval": round(average_interval, 1),
        "retention_rate": round(retention_rate, 1),
        "total_reviews": total_reviews
    }


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
def browse_all_cards(db: Session = Depends(get_db), document_id: Optional[str] = None, macro_topic_id: Optional[int] = None, micro_topic_id: Optional[int] = None, type: Optional[str] = None, difficulty: Optional[str] = None):
    """
    Browse all documents and their cards organized by topics.

    Returns all documents with their cards grouped by topic metadata.
    Useful for students to review what cards exist before studying.

    Returns:
        List of documents, each containing topics with their cards
    """
    # Optional filter by document
    doc_query = db.query(Document)
    if document_id:
        doc_query = doc_query.filter(Document.id == document_id)
    documents = doc_query.all()

    result = []
    for doc in documents:
        # If macro/micro tables exist and cards are linked, build macro->micro tree
        macros_q = db.query(MacroTopic).filter(MacroTopic.document_id == doc.id)
        if macro_topic_id:
            macros_q = macros_q.filter(MacroTopic.id == macro_topic_id)
        macros = macros_q.all()

        macro_list = []
        if macros:
            for macro in macros:
                micros_q = db.query(MicroTopic).filter(MicroTopic.macro_topic_id == macro.id)
                if micro_topic_id:
                    micros_q = micros_q.filter(MicroTopic.id == micro_topic_id)
                micros = micros_q.all()
                micro_list = []
                for micro in micros:
                    cards_q = db.query(Card).filter(Card.document_id == doc.id, Card.micro_topic_id == micro.id)
                    if type:
                        try:
                            # Convert string to enum if matches
                            from backend.models import CardType as CT
                            cards_q = cards_q.filter(Card.type == getattr(CT, type))
                        except Exception:
                            pass
                    cards = cards_q.order_by(Card.id).all()
                    card_items = []
                    for card in cards:
                        type_str = str(card.type.value) if hasattr(card.type, 'value') else str(card.type)
                        if card.base_difficulty is None:
                            diff_label = "medium"
                        elif card.base_difficulty <= 0.33:
                            diff_label = "easy"
                        elif card.base_difficulty >= 0.67:
                            diff_label = "hard"
                        else:
                            diff_label = "medium"
                        if difficulty and diff_label != difficulty:
                            continue
                        card_items.append({
                            "id": card.id,
                            "type": type_str,
                            "front": card.front,
                            "back": card.back,
                            "difficulty": diff_label
                        })
                    micro_list.append({
                        "micro_topic_id": micro.id,
                        "micro_topic_name": micro.name,
                        "card_count": len(card_items),
                        "cards": card_items
                    })
                macro_list.append({
                    "macro_topic_id": macro.id,
                    "macro_topic_name": macro.name,
                    "micro_topics": micro_list
                })
            total_cards = sum(sum(mt["card_count"] for mt in m["micro_topics"]) for m in macro_list if m["micro_topics"])
            # Check if document has RAG chunks for chatbot
            chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
            result.append({
                "document_id": doc.id,
                "title": doc.title,
                "total_cards": total_cards,
                "chatbot_enabled": chunk_count > 0,
                "chunk_count": chunk_count,
                "macros": macro_list
            })
        else:
            # Legacy topic grouping if macro/micro not present
            cards = db.query(Card).filter(Card.document_id == doc.id).order_by(Card.id).all()
            topics_map = {}
            for card in cards:
                topic_name = card.topic or "Uncategorized"
                if topic_name not in topics_map:
                    topics_map[topic_name] = []
                type_str = str(card.type.value) if hasattr(card.type, 'value') else str(card.type)
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
            topics_list = [{"name": name, "cards": lst} for name, lst in topics_map.items()]
            # Check if document has RAG chunks for chatbot
            chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
            result.append({
                "document_id": doc.id,
                "title": doc.title,
                "total_cards": len(cards),
                "chatbot_enabled": chunk_count > 0,
                "chunk_count": chunk_count,
                "topics": topics_list
            })

    return {"documents": result}


@router.get("/macro/{doc_id}")
def get_macro_progress(doc_id: str, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    data = macro_progress(db, doc_id, user_id="demo-user")
    return {"document_id": doc_id, "title": document.title, "macros": data}


@router.get("/micro/{macro_id}")
def get_micro_progress(macro_id: int, db: Session = Depends(get_db)):
    data = micro_progress(db, macro_id, user_id="demo-user")
    return {"macro_topic_id": macro_id, "micros": data}


@router.get("/topics/{doc_id}")
def get_topic_mastery_progress(doc_id: str, db: Session = Depends(get_db)):
    """
    Get adaptive learning progress for all topics in a document.

    Returns UserTopicState for each micro topic with:
    - knowledge_score (0-100%)
    - cards_seen, cards_mastered
    - is_struggling flag
    - struggle_weight

    Args:
        doc_id: Document ID to get topic progress for

    Returns:
        JSON with document info and list of topic states
    """
    from backend.models import UserTopicState
    from backend.services.review import DEMO_USER_ID

    # Verify document exists
    document = db.query(Document).filter(Document.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get all micro topics with their states
    topic_states_query = db.query(
        MicroTopic,
        UserTopicState
    ).outerjoin(
        UserTopicState,
        (MicroTopic.id == UserTopicState.micro_topic_id) &
        (UserTopicState.user_id == DEMO_USER_ID)
    ).filter(
        MicroTopic.document_id == doc_id
    ).all()

    topics_data = []
    for micro_topic, topic_state in topic_states_query:
        # Get macro topic name
        macro = db.query(MacroTopic).filter(MacroTopic.id == micro_topic.macro_topic_id).first()
        macro_name = macro.name if macro else "Unknown"

        if topic_state:
            # Topic has been practiced
            is_struggling = topic_state.knowledge_score < 50.0 or topic_state.struggle_weight > 1.5
            topics_data.append({
                "micro_topic_id": micro_topic.id,
                "micro_topic_name": micro_topic.name,
                "macro_topic_name": macro_name,
                "knowledge_score": round(topic_state.knowledge_score, 1),
                "cards_seen": topic_state.cards_seen,
                "cards_mastered": topic_state.cards_mastered,
                "struggle_weight": round(topic_state.struggle_weight, 2),
                "is_struggling": is_struggling,
                "avg_card_score": round(topic_state.avg_card_score, 2),
                "total_reviews": topic_state.total_reviews,
                "last_practice_at": topic_state.last_practice_at.isoformat() if topic_state.last_practice_at else None
            })
        else:
            # Topic not yet practiced
            # Count total cards in this topic
            total_cards = db.query(Card).filter(Card.micro_topic_id == micro_topic.id).count()
            topics_data.append({
                "micro_topic_id": micro_topic.id,
                "micro_topic_name": micro_topic.name,
                "macro_topic_name": macro_name,
                "knowledge_score": 0.0,
                "cards_seen": 0,
                "cards_mastered": 0,
                "struggle_weight": 1.0,
                "is_struggling": False,
                "avg_card_score": 0.0,
                "total_reviews": 0,
                "total_cards": total_cards,
                "last_practice_at": None
            })

    return {
        "document_id": doc_id,
        "title": document.title,
        "topics": topics_data
    }


@router.get("/dashboard")
def get_dashboard_progress(db: Session = Depends(get_db)):
    """
    Get overall adaptive learning dashboard statistics.

    Returns aggregate stats across all documents:
    - Average knowledge score
    - Total topics
    - Struggling topics count
    - Total reviews

    Returns:
        JSON with dashboard statistics
    """
    from backend.models import UserTopicState
    from backend.services.review import DEMO_USER_ID
    from sqlalchemy import func

    # Get all topic states for user
    topic_states = db.query(UserTopicState).filter(
        UserTopicState.user_id == DEMO_USER_ID
    ).all()

    if not topic_states:
        return {
            "avg_knowledge_score": 0.0,
            "total_topics": 0,
            "struggling_topics": 0,
            "total_reviews": 0,
            "topics_mastered": 0
        }

    # Calculate aggregate statistics
    total_topics = len(topic_states)
    avg_knowledge = sum(ts.knowledge_score for ts in topic_states) / total_topics
    struggling_count = sum(1 for ts in topic_states if ts.knowledge_score < 50.0 or ts.struggle_weight > 1.5)
    total_reviews = sum(ts.total_reviews for ts in topic_states)
    topics_mastered = sum(1 for ts in topic_states if ts.knowledge_score >= 80.0)

    return {
        "avg_knowledge_score": round(avg_knowledge, 1),
        "total_topics": total_topics,
        "struggling_topics": struggling_count,
        "total_reviews": total_reviews,
        "topics_mastered": topics_mastered
    }
