"""
Pydantic models for the Badge/Achievement and Notification systems.
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────
# Badges
# ──────────────────────────────────────────

class Badge(BaseModel):
    """Platform-defined badge in the catalogue."""
    id: str
    name: str
    description: str
    icon: str = "🏅"
    criteria_type: str
    criteria_value: int
    created_at: Optional[datetime] = None


class UserBadgeEarned(BaseModel):
    """A badge that a specific user has earned."""
    id: str          # user_badge row id
    user_id: str
    badge_id: str
    badge_name: str
    badge_description: str
    badge_icon: str
    earned_at: datetime


class BadgeAwardResult(BaseModel):
    """Returned by BadgeService.check_and_award — new badges earned this call."""
    newly_earned: List[UserBadgeEarned] = Field(default_factory=list)


# ──────────────────────────────────────────
# Notifications
# ──────────────────────────────────────────

class Notification(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    event_type: str = "general"
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationListResponse(BaseModel):
    notifications: List[Notification]
    total: int
    unread_count: int
