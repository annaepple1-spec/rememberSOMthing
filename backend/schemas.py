from typing import Optional
from pydantic import BaseModel, ConfigDict


class CardOut(BaseModel):
    """Schema for card output."""
    id: str
    front: str
    back: str
    type: str
    topic: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AnswerRequest(BaseModel):
    """Schema for answer submission."""
    card_id: str
    user_answer: str
    latency_ms: int


class AnswerResponse(BaseModel):
    """Schema for answer grading response."""
    score: int
    explanation: str
