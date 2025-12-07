"""Router for tracking user progress on documents."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Document, Card, MacroTopic, MicroTopic
from backend.services.progress import document_progress, macro_progress, micro_progress

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
                        "cards": card_items if micro_topic_id else []
                    })
                macro_list.append({
                    "macro_topic_id": macro.id,
                    "macro_topic_name": macro.name,
                    "micro_topics": micro_list
                })
            total_cards = sum(m["micro_topics"] and sum(mt["card_count"] for mt in m["micro_topics"]) for m in macro_list)
            result.append({
                "document_id": doc.id,
                "title": doc.title,
                "total_cards": total_cards,
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
            result.append({
                "document_id": doc.id,
                "title": doc.title,
                "total_cards": len(cards),
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
