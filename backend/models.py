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
    topic = Column(String, nullable=True)
    type = Column(Enum(CardType), nullable=False)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    base_difficulty = Column(Float, default=0.5)

    # Relationship
    document = relationship("Document", back_populates="cards")


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
