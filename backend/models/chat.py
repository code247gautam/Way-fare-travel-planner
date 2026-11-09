"""Chat API models."""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    trip_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    trip_id: Optional[str] = None
    preferences_ready: bool = False
    itinerary_ready: bool = False
