"""Pydantic schemas for the dispute resolution system."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DisputeStatus(str, Enum):
    open = "open"
    responded = "responded"
    escalated = "escalated"
    resolved = "resolved"
    closed = "closed"


class ResolutionType(str, Enum):
    refund = "refund"
    partial = "partial"
    freelancer = "freelancer"


class DisputeCreate(BaseModel):
    quest_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=10, max_length=2000)


class DisputeRespond(BaseModel):
    response_text: str = Field(..., min_length=10, max_length=2000)


class DisputeResolve(BaseModel):
    resolution_type: ResolutionType
    resolution_note: str = Field(..., min_length=5, max_length=2000)
    partial_percent: Optional[float] = Field(
        None,
        ge=1,
        le=99,
        description="Required when resolution_type is 'partial'. Percentage awarded to freelancer.",
    )


class DisputeOut(BaseModel):
    id: str
    quest_id: str
    initiator_id: str
    respondent_id: str
    reason: str
    response_text: Optional[str] = None
    status: DisputeStatus
    resolution_type: Optional[ResolutionType] = None
    partial_percent: Optional[float] = None
    resolution_note: Optional[str] = None
    moderator_id: Optional[str] = None
    auto_escalate_at: datetime
    created_at: datetime
    responded_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DisputeListResponse(BaseModel):
    items: list[DisputeOut]
    total: int
