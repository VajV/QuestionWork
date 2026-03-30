"""Pydantic models for analytics event ingestion."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalyticsEventIngest(BaseModel):
    """A single analytics event submitted by the frontend."""

    event_name: str = Field(..., max_length=100)
    session_id: Optional[str] = Field(None, max_length=64)
    role: Optional[str] = Field(None, max_length=20)
    source: Optional[str] = Field(None, max_length=100)
    path: Optional[str] = Field(None, max_length=500)
    properties: Dict[str, Any] = Field(default_factory=dict)
    # Client-side timestamp; server-side as fallback
    timestamp: Optional[datetime] = None


class AnalyticsEventBatch(BaseModel):
    """Batch of analytics events (up to 50 per request)."""

    events: List[AnalyticsEventIngest] = Field(..., min_length=1, max_length=50)


class AnalyticsIngestResponse(BaseModel):
    """Acknowledgement returned after batch ingestion."""

    ingested: int


class FunnelKPIs(BaseModel):
    """Admin-facing growth funnel KPIs."""

    landing_views: int = 0
    register_started: int = 0
    clients_registered: int = 0
    clients_with_quests: int = 0
    quests_created: int = 0
    applications_submitted: int = 0
    hires: int = 0
    confirmed_completions: int = 0
    clients_with_repeat_hire: int = 0

    # Computed conversion rates (0–100 %)
    @property
    def landing_to_register_pct(self) -> float:
        return round(self.register_started / self.landing_views * 100, 1) if self.landing_views else 0.0

    @property
    def register_to_quest_pct(self) -> float:
        return round(self.clients_with_quests / self.clients_registered * 100, 1) if self.clients_registered else 0.0

    @property
    def quest_to_hire_pct(self) -> float:
        return round(self.hires / self.quests_created * 100, 1) if self.quests_created else 0.0

    @property
    def hire_to_completion_pct(self) -> float:
        return round(self.confirmed_completions / self.hires * 100, 1) if self.hires else 0.0

    @property
    def repeat_hire_pct(self) -> float:
        return round(self.clients_with_repeat_hire / self.confirmed_completions * 100, 1) if self.confirmed_completions else 0.0

