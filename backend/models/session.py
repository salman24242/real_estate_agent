"""Pydantic models describing the Redis-stored conversation session."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from backend.models.filters import FilterState


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class SessionState(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    channel: str = "chat"  # "chat", "voice", or "whatsapp"
    messages: list[Message] = Field(default_factory=list)
    filter_state: FilterState = Field(default_factory=FilterState)
    turn_count: int = 0
    ready_to_query: bool = False
    last_results: list[dict] = Field(default_factory=list)
