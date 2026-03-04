"""
Pydantic models for the character class system.

API request/response schemas for class selection, progression, perks, abilities.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ClassBonusInfo(BaseModel):
    """A single passive bonus or weakness for display."""
    key: str = Field(..., description="Bonus type key")
    label: str = Field(..., description="Human-readable label")
    value: float | int | bool = Field(..., description="Bonus value")
    is_weakness: bool = Field(default=False)


# ── Perk models ──

class PerkInfo(BaseModel):
    """A perk node for display in the perk tree."""
    perk_id: str
    name: str
    name_ru: str
    description_ru: str
    icon: str
    tier: int
    required_class_level: int
    perk_point_cost: int
    prerequisite_ids: List[str] = Field(default_factory=list)
    effects: dict[str, float | int | bool] = Field(default_factory=dict)
    is_unlocked: bool = Field(default=False, description="User already owns this perk")
    can_unlock: bool = Field(default=False, description="User meets all requirements")
    lock_reason: Optional[str] = None


class PerkTreeResponse(BaseModel):
    """Full perk tree for user's class."""
    class_id: str
    perks: List[PerkInfo]
    perk_points_total: int = Field(description="Total perk points earned")
    perk_points_spent: int = Field(description="Perk points already used")
    perk_points_available: int = Field(description="Points available to spend")


class PerkUnlockRequest(BaseModel):
    """Request body for POST /classes/perks/unlock."""
    perk_id: str


class PerkUnlockResponse(BaseModel):
    """Response after unlocking a perk."""
    message: str
    perk: PerkInfo
    perk_points_available: int


# ── Ability models ──

class AbilityInfo(BaseModel):
    """An active ability for display."""
    ability_id: str
    name: str
    name_ru: str
    description_ru: str
    icon: str
    required_class_level: int
    cooldown_hours: int
    duration_hours: int
    effects: dict[str, float | int | bool] = Field(default_factory=dict)
    is_unlocked: bool = Field(default=False, description="Class level met")
    is_active: bool = Field(default=False, description="Currently activated")
    active_until: Optional[datetime] = None
    is_on_cooldown: bool = Field(default=False)
    cooldown_until: Optional[datetime] = None
    times_used: int = 0


class AbilityActivateRequest(BaseModel):
    """Request body for POST /classes/abilities/activate."""
    ability_id: str


class AbilityActivateResponse(BaseModel):
    """Response after activating an ability."""
    message: str
    ability: AbilityInfo


# ── Class info models (unchanged API) ──

class CharacterClassInfo(BaseModel):
    """Full info about a character class (for API responses)."""
    class_id: str = Field(..., description="Class identifier (e.g. 'berserk')")
    name: str = Field(..., description="Class name (English)")
    name_ru: str = Field(..., description="Class name (Russian)")
    icon: str = Field(..., description="Class icon emoji")
    color: str = Field(..., description="CSS color for theming")
    description: str
    description_ru: str
    min_unlock_level: int = Field(..., description="Minimum user level to unlock")
    bonuses: List[ClassBonusInfo] = Field(default_factory=list)
    weaknesses: List[ClassBonusInfo] = Field(default_factory=list)
    perk_count: int = Field(default=0, description="Number of perks in tree")
    ability_count: int = Field(default=0, description="Number of active abilities")


class UserClassInfo(BaseModel):
    """User's current class state (returned by GET /classes/me)."""
    class_id: str
    name: str
    name_ru: str
    icon: str
    color: str
    class_level: int = Field(default=1)
    class_xp: int = Field(default=0)
    class_xp_to_next: int = Field(default=500)
    quests_completed_as_class: int = Field(default=0)
    consecutive_quests: int = Field(default=0)

    is_trial: bool = Field(default=False, description="User is in trial period")
    trial_expires_at: Optional[datetime] = None

    active_bonuses: List[ClassBonusInfo] = Field(default_factory=list)
    weaknesses: List[ClassBonusInfo] = Field(default_factory=list)

    is_burnout: bool = Field(default=False, description="Burnout debuff active")
    burnout_until: Optional[datetime] = None

    # Phase 2 fields
    perk_points_total: int = Field(default=0)
    perk_points_spent: int = Field(default=0)
    perk_points_available: int = Field(default=0)
    unlocked_perks: List[str] = Field(default_factory=list)
    rage_active: bool = Field(default=False, description="Rage Mode currently active")
    rage_active_until: Optional[datetime] = None


class ClassSelectRequest(BaseModel):
    """Request body for POST /classes/select."""
    class_id: str = Field(..., description="Class to select (e.g. 'berserk')")


class ClassSelectResponse(BaseModel):
    """Response after selecting or confirming a class."""
    message: str
    class_info: UserClassInfo


class ClassListResponse(BaseModel):
    """Response for GET /classes/."""
    classes: List[CharacterClassInfo]
    user_level: int
    current_class: Optional[str] = None
