"""Pydantic models for lifecycle CRM and email outbox."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ── Lifecycle ─────────────────────────────────────────────────────────────────

class LifecycleCampaign(BaseModel):
    """A named trigger → message template definition."""
    id: str
    campaign_key: str
    name: str
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


class LifecycleMessage(BaseModel):
    """Represents one pending/sent lifecycle nudge for a user."""
    id: str
    user_id: str
    campaign_key: str
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    status: str  # pending | sent | failed | suppressed
    send_after: datetime
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    idempotency_key: str
    created_at: Optional[datetime] = None


# ── Email outbox ──────────────────────────────────────────────────────────────

class EmailOutboxEntry(BaseModel):
    """Row in the email_outbox persistent delivery table."""
    id: str
    user_id: Optional[str] = None
    email_address: str
    template_key: str
    template_params: Dict[str, Any] = Field(default_factory=dict)
    status: str  # pending | sent | failed
    send_after: datetime
    sent_at: Optional[datetime] = None
    attempt_count: int = 0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


# ── Saved searches ────────────────────────────────────────────────────────────

class SavedSearch(BaseModel):
    id: str
    user_id: str
    name: Optional[str] = None
    search_type: str  # talent | quest
    filters_json: Dict[str, Any] = Field(default_factory=dict)
    alert_enabled: bool = False
    last_alerted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class SavedSearchCreate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    search_type: str = Field(..., pattern="^(talent|quest)$")
    filters_json: Dict[str, Any] = Field(default_factory=dict)
    alert_enabled: bool = False

    @field_validator("filters_json")
    @classmethod
    def validate_filters_json(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if len(v) > 20:
            raise ValueError("filters_json must have ≤ 20 keys")
        for val in v.values():
            if isinstance(val, dict) and any(isinstance(vv, dict) for vv in val.values()):
                raise ValueError("filters_json nesting depth must be ≤ 2")
        return v


class SavedSearchListResponse(BaseModel):
    items: List[SavedSearch]
    total: int
