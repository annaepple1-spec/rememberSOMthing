import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, Integer, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from backend.database import Base


class CardType(str, enum.Enum):
    """Enum for card types."""
    definition = "definition"
    application = "application"
    connection = "connection"
    cloze = "cloze"
    mcq = "mcq"


class Document(Base):
    """Document model representing a collection of flashcards."""
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    cards = relationship("Card", back_populates="document")


class Card(Base):
    """Card model representing a single flashcard."""
    __tablename__ = "cards"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    # Legacy combined topic string (e.g., "Macro - Micro"). Kept for backfill traceability.
    topic = Column(String, nullable=True)
    # New hierarchy linkage: optional micro topic id
    micro_topic_id = Column(Integer, ForeignKey("micro_topics.id"), nullable=True)
    type = Column(Enum(CardType), nullable=False)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    # For MCQ cards: stores the correct option index (0=A, 1=B, 2=C, 3=D)
    correct_option_index = Column(Integer, nullable=True)
    base_difficulty = Column(Float, default=0.5)

    # Relationship
    document = relationship("Document", back_populates="cards")
    micro_topic = relationship("MicroTopic", back_populates="cards")


class UserCardState(Base):
    """UserCardState model for tracking spaced repetition state per user per card."""
    __tablename__ = "user_card_states"

    user_id = Column(String, primary_key=True)
    card_id = Column(String, ForeignKey("cards.id"), primary_key=True)
    
    interval_days = Column(Float, default=0.0)
    next_due_at = Column(DateTime, nullable=True)
    easiness = Column(Float, default=2.5)
    repetitions = Column(Integer, default=0)
    last_score = Column(Integer, nullable=True)
    mastery = Column(Float, default=0.0)
    last_review_at = Column(DateTime, nullable=True)


class Review(Base):
    """Review model for tracking answer history."""
    __tablename__ = "reviews"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    card_id = Column(String, ForeignKey("cards.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    score = Column(Integer, nullable=False)
    latency_ms = Column(Integer, nullable=False)


class MacroTopic(Base):
    """Top-level topic grouping for a document (e.g., MRP, Aggregate Planning)."""
    __tablename__ = "macro_topics"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    micro_topics = relationship("MicroTopic", back_populates="macro_topic", cascade="all, delete-orphan")


class MicroTopic(Base):
    """Second-level topic grouping under a macro (e.g., BOM Structure under MRP)."""
    __tablename__ = "micro_topics"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    macro_topic_id = Column(Integer, ForeignKey("macro_topics.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    macro_topic = relationship("MacroTopic", back_populates="micro_topics")
    cards = relationship("Card", back_populates="micro_topic")


class UserTopicState(Base):
    """User's mastery state for a specific micro topic (adaptive learning)."""
    __tablename__ = "user_topic_states"

    user_id = Column(String, primary_key=True)
    micro_topic_id = Column(Integer, ForeignKey("micro_topics.id"), primary_key=True)
    
    # Knowledge score (0-100%) calculated from weighted card mastery
    knowledge_score = Column(Float, default=0.0)
    cards_seen = Column(Integer, default=0)
    cards_mastered = Column(Integer, default=0)
    
    # Struggle weight (1.0 base, increased for struggling topics)
    struggle_weight = Column(Float, default=1.0)
    
    # Average card score (0-3 scale) for this topic
    avg_card_score = Column(Float, default=0.0)
    
    last_practice_at = Column(DateTime, nullable=True)
    total_reviews = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class DocumentChunk(Base):
    """Text chunk from document with embedding for RAG retrieval."""
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Order in document
    page_number = Column(Integer, nullable=True)  # Source page if available
    start_char = Column(Integer, nullable=True)  # Character offset in document
    end_char = Column(Integer, nullable=True)
    # Embedding stored as JSON string (will use ChromaDB for vector ops)
    embedding_id = Column(String, nullable=True)  # Reference to ChromaDB
    created_at = Column(DateTime, default=datetime.utcnow)


class QuizSession(Base):
    """Quiz session tracking for RAG-based interactive quizzing."""
    __tablename__ = "quiz_sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    last_activity_at = Column(DateTime, default=datetime.utcnow)
    questions_asked = Column(Integer, default=0)
    questions_correct = Column(Integer, default=0)
    total_score = Column(Float, default=0.0)  # Sum of scores (0-3 per question)
    is_active = Column(Integer, default=1)  # 1=active, 0=ended


class QuizInteraction(Base):
    """Individual question/answer interaction in a quiz session."""
    __tablename__ = "quiz_interactions"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("quiz_sessions.id"), nullable=False)
    card_id = Column(String, ForeignKey("cards.id"), nullable=True)  # Linked card if using existing
    question_text = Column(Text, nullable=False)
    user_answer = Column(Text, nullable=False)
    correct_answer = Column(Text, nullable=False)
    score = Column(Integer, nullable=False)  # 0-3
    explanation = Column(Text, nullable=True)  # Grading explanation
    retrieved_context = Column(Text, nullable=True)  # RAG context used
    timestamp = Column(DateTime, default=datetime.utcnow)
