"""Pydantic models for world meta snapshot exposed to the frontend."""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class WorldRegion(BaseModel):
    """A named map region derived from platform activity signals."""

    id: str
    name: str
    status: str  # "active" | "contested" | "dormant" | "hostile"
    progress_percent: int = Field(ge=0, le=100)
    dominant_faction_id: str
    activity_label: str


class WorldLoreBeat(BaseModel):
    """A short narrative beat tied to the current world state."""

    id: str
    text: str
    faction_id: Optional[str] = None
    beat_type: str  # "narrative" | "warning" | "milestone"


class WorldMetricSnapshot(BaseModel):
    total_users: int = 0
    freelancer_count: int = 0
    client_count: int = 0
    open_quests: int = 0
    in_progress_quests: int = 0
    revision_requested_quests: int = 0
    urgent_quests: int = 0
    confirmed_quests_week: int = 0
    unread_notifications: int = 0
    total_reviews: int = 0
    avg_rating: Optional[float] = None
    earned_badges: int = 0


class WorldSeason(BaseModel):
    id: str
    title: str
    stage: str
    progress_percent: int = Field(ge=0, le=100)
    completed_quests_week: int = 0
    target_quests_week: int = 0
    days_left: int = Field(ge=0, le=31)
    chapter: str = ""
    stage_description: str = ""
    next_unlock: str = ""


class WorldFaction(BaseModel):
    id: str
    name: str
    focus: str
    score: int = Field(ge=0)
    trend: str


class WorldCommunity(BaseModel):
    headline: str
    momentum: str
    target_label: str
    current_value: int = Field(ge=0)
    target_value: int = Field(ge=0)


class WorldTrendPoint(BaseModel):
    label: str
    value: int = Field(ge=0)


class WorldTrendMetric(BaseModel):
    id: str
    label: str
    current_value: int = Field(ge=0)
    previous_value: int = Field(ge=0)
    delta_value: int
    delta_percent: int
    direction: str
    points: List[WorldTrendPoint]


class WorldMetaResponse(BaseModel):
    season: WorldSeason
    factions: List[WorldFaction]
    leading_faction_id: str
    community: WorldCommunity
    metrics: WorldMetricSnapshot
    trends: List[WorldTrendMetric]
    regions: List[WorldRegion] = Field(default_factory=list)
    lore_beats: List[WorldLoreBeat] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))