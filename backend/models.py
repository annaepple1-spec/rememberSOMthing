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
