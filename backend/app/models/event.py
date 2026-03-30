"""Pydantic schemas for the seasonal events system."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EventStatus(str, Enum):
    draft = "draft"
    active = "active"
    ended = "ended"
    finalized = "finalized"


class EventCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20, max_length=5000)
    xp_multiplier: Decimal = Field(default=Decimal("1.5"), ge=Decimal("1.0"), le=Decimal("5.0"))
    badge_reward_id: Optional[str] = None
    max_participants: Optional[int] = Field(None, ge=10, le=10000)
    start_at: datetime
    end_at: datetime


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=20, max_length=5000)
    xp_multiplier: Optional[Decimal] = Field(None, ge=Decimal("1.0"), le=Decimal("5.0"))
    badge_reward_id: Optional[str] = None
    max_participants: Optional[int] = Field(None, ge=10, le=10000)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class EventOut(BaseModel):
    id: str
    title: str
    description: str
    status: EventStatus
    xp_multiplier: Decimal
    badge_reward_id: Optional[str] = None
    max_participants: Optional[int] = None
    participant_count: int = 0
    created_by: str
    start_at: datetime
    end_at: datetime
    finalized_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    items: list[EventOut]
    total: int
    has_more: bool = False


class EventParticipantOut(BaseModel):
    id: str
    event_id: str
    user_id: str
    username: str
    score: int
    joined_at: datetime


class ScoreSubmit(BaseModel):
    score_delta: int = Field(..., ge=1, le=10000, description="Points to add to user's event score")


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    username: str
    grade: str
    score: int
    xp_bonus: int
    badge_awarded: bool


class EventLeaderboardResponse(BaseModel):
    event_id: str
    entries: list[LeaderboardEntry]
    total_participants: int
