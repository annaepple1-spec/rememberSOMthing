"""
Quiz Bot API endpoints for RAG-based interactive quizzing.
"""
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db
from backend.models import (
    QuizSession, QuizInteraction, Card, Document, UserCardState, Review, DocumentChunk
)
from backend.services.rag import retrieve_context, get_related_cards, assemble_quiz_context
from backend.services.review import grade_answer_by_type
from backend.services.conversational import generate_chat_response, generate_follow_up_questions

router = APIRouter()


def check_documents_have_chunks(db: Session, document_ids: list) -> tuple[bool, list]:
    """
    Check if documents have RAG chunks for chatbot functionality.
    
    Returns:
        (all_have_chunks: bool, docs_without_chunks: list of doc IDs)
    """
    docs_without_chunks = []
    for doc_id in document_ids:
        chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).count()
        if chunk_count == 0:
            docs_without_chunks.append(doc_id)
    
    return len(docs_without_chunks) == 0, docs_without_chunks


# Request/Response schemas
class StartQuizRequest(BaseModel):
    document_id: str = None  # Single document (optional for backward compatibility)
    document_ids: list = None  # Multiple documents (new multi-doc mode)
    user_id: str = "default_user"


class StartQuizResponse(BaseModel):
    session_id: str
    document_title: str
    message: str


class AskQuestionRequest(BaseModel):
    session_id: str


class AskQuestionResponse(BaseModel):
    question_id: str
    question_text: str
    card_type: str
    card_id: Optional[str]
    context_preview: Optional[str]
    options: Optional[list] = None  # For MCQ cards


class SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    card_id: str
    answer: str


class SubmitAnswerResponse(BaseModel):
    score: int
    explanation: str
    correct_answer: str
    is_correct: bool


class QuizHistoryResponse(BaseModel):
    session_id: str
    document_title: str
    questions_asked: int
    questions_correct: int
    average_score: float
    interactions: list


class ChatRequest(BaseModel):
    session_id: str
    message: str
    document_ids: Optional[list] = None  # For multi-doc mode
    conversation_history: Optional[list] = None  # List of {"role": "user"/"assistant", "content": "..."}


class ChatResponse(BaseModel):
    response: str
    citations: str
    sources: list
    follow_up_questions: Optional[list] = None


@router.post("/quiz/start", response_model=StartQuizResponse)
async def start_quiz(request: StartQuizRequest, db: Session = Depends(get_db)):
    """Start a new quiz session for one or more documents."""
    
    # Determine if single or multi-doc mode
    if request.document_ids and len(request.document_ids) > 0:
        # Multi-document mode
        document_ids = request.document_ids
        documents = db.query(Document).filter(Document.id.in_(document_ids)).all()
        
        if not documents:
            raise HTTPException(status_code=404, detail="No documents found")
        
        doc_titles = [doc.title for doc in documents]
        primary_doc_id = document_ids[0]  # Use first document as primary for session
        document_title = f"{len(documents)} documents: " + ", ".join(doc_titles[:3]) + ("..." if len(doc_titles) > 3 else "")
        
        # Check if there are cards across all documents
        total_cards = db.query(Card).filter(Card.document_id.in_(document_ids)).count()
        if total_cards == 0:
            raise HTTPException(status_code=400, detail="No flashcards found for selected documents")
        
        # Check if documents have RAG chunks for chatbot
        has_chunks, docs_without = check_documents_have_chunks(db, document_ids)
        if not has_chunks:
            doc_titles_missing = [db.query(Document).filter(Document.id == doc_id).first().title 
                                  for doc_id in docs_without if db.query(Document).filter(Document.id == doc_id).first()]
            raise HTTPException(
                status_code=400, 
                detail=f"Study Chat not available. The following documents weren't properly indexed for chat: {', '.join(doc_titles_missing)}. Please re-upload these documents or use the Practice tab for flashcard study."
            )
    else:
        # Single document mode (backward compatibility)
        if not request.document_id:
            raise HTTPException(status_code=400, detail="No document specified")
        
        document = db.query(Document).filter(Document.id == request.document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        primary_doc_id = request.document_id
        document_ids = [request.document_id]
        document_title = document.title
        
        # Check if there are cards for this document
        card_count = db.query(Card).filter(Card.document_id == request.document_id).count()
        if card_count == 0:
            raise HTTPException(status_code=400, detail="No flashcards found for this document")
        
        # Check if document has RAG chunks for chatbot
        has_chunks, _ = check_documents_have_chunks(db, [request.document_id])
        if not has_chunks:
            raise HTTPException(
                status_code=400,
                detail=f"Study Chat not available for '{document.title}'. This document wasn't properly indexed for chat. Please re-upload or use the Practice tab for flashcard study."
            )
        
        total_cards = card_count
    
    # Create quiz session (store document_ids in session for later use)
    session_id = str(uuid.uuid4())
    quiz_session = QuizSession(
        id=session_id,
        user_id=request.user_id,
        document_id=primary_doc_id,  # Store primary doc for compatibility
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow()
    )
    
    db.add(quiz_session)
    db.commit()
    
    # Store document_ids list in a separate way (you might want to add a new field or use JSON)
    # For now, we'll pass it in the response and frontend will track it
    
    return StartQuizResponse(
        session_id=session_id,
        document_title=document_title,
        message=f"Chat started! Ready to answer questions from {total_cards} flashcards across your selected documents."
    )


@router.post("/quiz/ask", response_model=AskQuestionResponse)
async def ask_question(request: AskQuestionRequest, db: Session = Depends(get_db)):
    """Get next quiz question using RAG to select relevant card."""
    
    # Verify session exists and is active
    session = db.query(QuizSession).filter(QuizSession.id == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    if not session.is_active:
        raise HTTPException(status_code=400, detail="Quiz session has ended")
    
    # Get cards from document, prioritize unseen or low-mastery cards
    cards = db.query(Card).filter(Card.document_id == session.document_id).all()
    
    if not cards:
        raise HTTPException(status_code=404, detail="No cards available")
    
    # Use RAG to select a relevant card based on recent context
    # For now, select a random card (can enhance with adaptive selection later)
    import random
    selected_card = random.choice(cards)
    
    # Assemble context for the question
    enriched_question, context_chunks = assemble_quiz_context(
        session.document_id,
        selected_card,
        db
    )
    
    # Create question ID
    question_id = str(uuid.uuid4())
    
    # Prepare context preview
    context_preview = None
    if context_chunks and len(context_chunks) > 0:
        context_preview = context_chunks[0]["text"][:200] + "..."
    
    # Parse MCQ options if applicable
    options = None
    question_text = selected_card.front
    
    if selected_card.type.value == "mcq":
        # Parse options from front text
        parts = selected_card.front.split('\n')
        opt_start = next((i for i, line in enumerate(parts) if line.strip().lower().startswith('options:')), -1)
        
        if opt_start != -1:
            question_text = '\n'.join(parts[:opt_start])
            option_lines = [line.strip() for line in parts[opt_start + 1:] if line.strip()]
            options = option_lines
    
    # Update session activity
    session.last_activity_at = datetime.utcnow()
    db.commit()
    
    return AskQuestionResponse(
        question_id=question_id,
        question_text=question_text,
        card_type=selected_card.type.value,
        card_id=selected_card.id,
        context_preview=context_preview,
        options=options
    )


@router.post("/quiz/answer", response_model=SubmitAnswerResponse)
async def submit_answer(request: SubmitAnswerRequest, db: Session = Depends(get_db)):
    """Submit answer to quiz question and get grading."""
    
    # Verify session exists
    session = db.query(QuizSession).filter(QuizSession.id == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    # Get the card that was asked
    card = db.query(Card).filter(Card.id == request.card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    # Grade the answer using existing grading system
    try:
        result = grade_answer_by_type(
            card=card,
            user_answer=request.answer
        )
        score = result["score"]
        explanation = result["explanation"]
    except Exception as e:
        # Fallback grading
        score = 0
        explanation = f"Error grading answer: {str(e)}"
    
    # Store interaction
    interaction = QuizInteraction(
        id=request.question_id,
        session_id=request.session_id,
        card_id=card.id,
        question_text=card.front,
        user_answer=request.answer,
        correct_answer=card.back,
        score=score,
        explanation=explanation,
        timestamp=datetime.utcnow()
    )
    db.add(interaction)
    
    # Update session stats
    session.questions_asked += 1
    session.total_score += score
    if score >= 2:  # Consider 2+ as correct
        session.questions_correct += 1
    session.last_activity_at = datetime.utcnow()
    
    db.commit()
    
    return SubmitAnswerResponse(
        score=score,
        explanation=explanation,
        correct_answer=card.back,
        is_correct=(score >= 2)
    )


@router.get("/quiz/history/{session_id}", response_model=QuizHistoryResponse)
async def get_quiz_history(session_id: str, db: Session = Depends(get_db)):
    """Get quiz session history and statistics."""
    
    session = db.query(QuizSession).filter(QuizSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    document = db.query(Document).filter(Document.id == session.document_id).first()
    
    interactions = db.query(QuizInteraction).filter(
        QuizInteraction.session_id == session_id
    ).order_by(QuizInteraction.timestamp).all()
    
    interaction_list = [
        {
            "question": inter.question_text,
            "user_answer": inter.user_answer,
            "correct_answer": inter.correct_answer,
            "score": inter.score,
            "explanation": inter.explanation,
            "timestamp": inter.timestamp.isoformat()
        }
        for inter in interactions
    ]
    
    avg_score = session.total_score / session.questions_asked if session.questions_asked > 0 else 0
    
    return QuizHistoryResponse(
        session_id=session_id,
        document_title=document.title if document else "Unknown",
        questions_asked=session.questions_asked,
        questions_correct=session.questions_correct,
        average_score=round(avg_score, 2),
        interactions=interaction_list
    )


@router.post("/quiz/end/{session_id}")
async def end_quiz(session_id: str, db: Session = Depends(get_db)):
    """End a quiz session."""
    
    session = db.query(QuizSession).filter(QuizSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    session.is_active = 0
    db.commit()
    
    return {"message": "Quiz session ended", "session_id": session_id}


@router.post("/quiz/chat", response_model=ChatResponse)
async def chat_with_document(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Conversational chat endpoint using RAG to answer questions from uploaded documents.
    Provides intelligent responses with citations from course material.
    Supports both single and multi-document mode.
    """
    # Verify session exists
    session = db.query(QuizSession).filter(QuizSession.id == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Quiz session not found")
    
    # Get document information
    # If document_ids provided, use multi-doc mode; otherwise use session's document_id
    if request.document_ids and len(request.document_ids) > 0:
        # Multi-document mode
        documents = db.query(Document).filter(Document.id.in_(request.document_ids)).all()
        if not documents:
            raise HTTPException(status_code=404, detail="Documents not found")
        
        result = generate_chat_response(
            user_question=request.message,
            document_ids=request.document_ids,
            db=db,
            conversation_history=request.conversation_history
        )
    else:
        # Single document mode
        document = db.query(Document).filter(Document.id == session.document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        result = generate_chat_response(
            user_question=request.message,
            document_id=session.document_id,
            document_title=document.title,
            db=db,
            conversation_history=request.conversation_history
        )
    
    # Generate follow-up questions
    # Use first document for follow-ups
    doc_id = request.document_ids[0] if request.document_ids else session.document_id
    follow_ups = generate_follow_up_questions(
        user_question=request.message,
        response=result['response'],
        document_id=doc_id,
        db=db
    )
    
    # Update session activity
    session.last_activity_at = datetime.utcnow()
    db.commit()
    
    return ChatResponse(
        response=result['response'],
        citations=result['citations'],
        sources=result['sources'],
        follow_up_questions=follow_ups
    )
