"""
Extra schemas - mostly for future use
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from src.pylibs.models import EventCategory, EventSubtype, EventType


class BulkUserCreate(BaseModel):
    user_ids: list[str]
    score: float = 500.0
    alpha: float = 0.25


class FreqCapUpdate(BaseModel):
    subtype: EventSubtype
    max_count: int = Field(..., ge=1)
    window_days: int = Field(..., ge=1)


class ScoreHistoryEntry(BaseModel):
    ts: datetime
    score: float
    event_type: Optional[EventType]
    delta: float


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    score: float
    level: str


class AuditEntry(BaseModel):
    event_id: str
    user_id: str
    category: EventCategory
    event_type: EventType
    weight: int
    object_id: str
    prev_score: float
    new_score: float
    processed_at: datetime
    skipped: bool
    skip_reason: Optional[str] = None
