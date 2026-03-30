"""
Pydantic модели пользователя
"""

import json
import re

from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum

from app.core.classes import ClassId


class GradeEnum(str, Enum):
    novice = "novice"
    junior = "junior"
    middle = "middle"
    senior = "senior"


class UserRoleEnum(str, Enum):
    client = "client"
    freelancer = "freelancer"
    admin = "admin"


class UserStats(BaseModel):
    intelligence: int = Field(default=10, ge=1, le=100, alias="int")
    dexterity: int = Field(default=10, ge=1, le=100, alias="dex")
    charisma: int = Field(default=10, ge=1, le=100, alias="cha")
    model_config = ConfigDict(populate_by_name=True)


class UserBadge(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    earned_at: datetime


def _safe_json_list(raw_value):
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return raw_value
    if isinstance(raw_value, tuple):
        return list(raw_value)
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


class UserProfile(BaseModel):
    id: str
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    role: UserRoleEnum = Field(default=UserRoleEnum.freelancer)
    is_banned: bool = False
    banned_reason: Optional[str] = None
    level: int = Field(default=1, ge=1, le=100)
    grade: GradeEnum = Field(default=GradeEnum.novice)
    xp: int = Field(default=0, ge=0)
    xp_to_next: int = Field(default=100)
    stat_points: int = Field(default=0, ge=0)  # unspent RPG stat points
    stats: UserStats = Field(default_factory=UserStats)
    badges: List[UserBadge] = Field(default_factory=list)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)
    skills: List[str] = Field(default_factory=list)
    availability_status: Optional[str] = Field(default=None, max_length=32)
    portfolio_links: List[str] = Field(default_factory=list)
    portfolio_summary: Optional[str] = Field(None, max_length=500)
    onboarding_completed: bool = False
    onboarding_completed_at: Optional[datetime] = None
    profile_completeness_percent: int = Field(default=0, ge=0, le=100)
    character_class: Optional[ClassId] = Field(None, description="RPG character class (e.g. berserk)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = ConfigDict(use_enum_values=True)


class FactionAlignment(BaseModel):
    """Derived player faction alignment — computed from existing user activity signals.

    Alignment is seasonal: the dominant pattern of a user's quest history determines
    which faction they contribute to. No new DB columns required.
    """

    faction_id: str = Field(
        ..., description="'vanguard' | 'keepers' | 'artisans' | 'none'"
    )
    faction_name: str
    contribution_score: int = Field(
        default=0, ge=0, le=100,
        description="Normalized 0-100 contribution weight",
    )
    rank: str = Field(
        default="recruit",
        description="'recruit' | 'soldier' | 'champion' | 'legend'",
    )
    alignment_note: str = Field(
        default="", description="Human-readable rationale for this alignment"
    )


class PublicUserProfile(BaseModel):
    id: str
    username: str = Field(..., min_length=3, max_length=50)
    role: UserRoleEnum = Field(default=UserRoleEnum.freelancer)
    level: int = Field(default=1, ge=1, le=100)
    grade: GradeEnum = Field(default=GradeEnum.novice)
    xp: int = Field(default=0, ge=0)
    xp_to_next: int = Field(default=100)
    stat_points: int = Field(default=0, ge=0)
    stats: UserStats = Field(default_factory=UserStats)
    badges: List[UserBadge] = Field(default_factory=list)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)
    skills: List[str] = Field(default_factory=list)
    character_class: Optional[ClassId] = Field(None, description="RPG character class (e.g. berserk)")
    # Proof fields
    avg_rating: Optional[float] = Field(None, ge=0, le=5)
    review_count: int = 0
    trust_score: Optional[float] = Field(None, ge=0, le=1)
    trust_score_updated_at: Optional[datetime] = None
    confirmed_quest_count: int = 0
    completion_rate: Optional[float] = Field(None, ge=0, le=100)
    typical_budget_band: Optional[str] = None
    availability_status: Optional[str] = None
    response_time_hint: Optional[str] = None
    portfolio_links: List[str] = Field(default_factory=list)
    portfolio_summary: Optional[str] = None
    onboarding_completed: bool = False
    onboarding_completed_at: Optional[datetime] = None
    profile_completeness_percent: int = Field(default=0, ge=0, le=100)
    reputation_stats: Optional["ReputationStats"] = Field(None,
        description="Derived RPG reputation stat profile (reliability, craft, influence, resolve)")
    faction_alignment: Optional[FactionAlignment] = Field(
        None, description="Derived faction alignment from user activity signals"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = ConfigDict(use_enum_values=True)


class TrustScoreBreakdownRaw(BaseModel):
    average_rating_5: float = Field(default=0.0, ge=0, le=5)
    accepted_quests: int = Field(default=0, ge=0)
    confirmed_quests: int = Field(default=0, ge=0)
    on_time_quests: int = Field(default=0, ge=0)
    grade: GradeEnum = Field(default=GradeEnum.novice)
    model_config = ConfigDict(use_enum_values=True)


class TrustScoreBreakdown(BaseModel):
    avg_rating: float = Field(default=0.0, ge=0, le=1)
    completion_rate: float = Field(default=0.0, ge=0, le=1)
    on_time_rate: float = Field(default=0.0, ge=0, le=1)
    level_bonus: float = Field(default=0.0, ge=0, le=1)
    raw: TrustScoreBreakdownRaw = Field(default_factory=TrustScoreBreakdownRaw)
    model_config = ConfigDict(use_enum_values=True)


class TrustScoreResponse(BaseModel):
    user_id: str
    trust_score: Optional[float] = Field(default=None, ge=0, le=1)
    breakdown: TrustScoreBreakdown = Field(default_factory=TrustScoreBreakdown)
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(use_enum_values=True)


class ReputationStats(BaseModel):
    """Derived RPG reputation stats computed from existing user signals.

    All values are 0-100 integers (D&D-style stat bars).
    These are presentation stats only — financial and moderation logic
    continues to use the canonical trust_score.
    """
    reliability: int = Field(default=0, ge=0, le=100,
        description="Delivery rate: weighted completion_rate + trust factor")
    craft: int = Field(default=0, ge=0, le=100,
        description="Quality of work: avg rating + grade progression")
    influence: int = Field(default=0, ge=0, le=100,
        description="Experience depth: quest history + reviews + level")
    resolve: int = Field(default=0, ge=0, le=100,
        description="Persistence: trust score + profile completeness")


# Resolve forward reference now that ReputationStats is defined
PublicUserProfile.model_rebuild()


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRoleEnum = Field(default=UserRoleEnum.freelancer, exclude=True)

    @field_validator("role")
    @classmethod
    def prevent_admin_registration(cls, v: UserRoleEnum) -> UserRoleEnum:
        """Never allow self-registration as admin."""
        if v == UserRoleEnum.admin:
            return UserRoleEnum.freelancer
        return v

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Enforce password complexity: >=1 uppercase, >=1 digit, >=1 special char."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        # L-11: Use string.punctuation-equivalent explicit set
        import string
        if not any(ch in string.punctuation for ch in v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserLogin(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile

    def model_dump(self, **kwargs: object) -> dict:
        d = super().model_dump(**kwargs)
        if "user" in d and isinstance(d["user"], dict):
            d["user"].pop("email", None)
        return d

    def model_dump_json(self, **kwargs: object) -> str:
        import json as _json
        raw = super().model_dump_json(**kwargs)
        parsed = _json.loads(raw)
        if "user" in parsed and isinstance(parsed["user"], dict):
            parsed["user"].pop("email", None)
        return _json.dumps(parsed)


def _normalize_enum_value(raw_value: str) -> str:
    if not isinstance(raw_value, str):
        return raw_value
    if "." in raw_value:
        return raw_value.split(".")[-1]
    return raw_value


def _safe_character_class(raw_value) -> Optional[ClassId]:
    """Return a ClassId if the value is valid, otherwise None."""
    if raw_value is None:
        return None
    normalised = _normalize_enum_value(raw_value)
    try:
        return ClassId(normalised)
    except ValueError:
        return None


def row_to_user_profile(row) -> UserProfile:
    """Convert an asyncpg Record (or dict-like) to UserProfile.

    Centralises the repetitive row→model mapping used across auth, users and quests endpoints.
    """
    return UserProfile(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        role=UserRoleEnum(_normalize_enum_value(row["role"])),
        is_banned=row.get("is_banned", False),
        banned_reason=row.get("banned_reason"),
        level=row["level"],
        grade=GradeEnum(_normalize_enum_value(row["grade"])),
        xp=row["xp"],
        xp_to_next=row["xp_to_next"],
        stat_points=row.get("stat_points", 0),
        stats=UserStats(
            int=row["stats_int"],
            dex=row["stats_dex"],
            cha=row["stats_cha"],
        ),
        badges=_safe_json_list(row.get("badges")),
        bio=row["bio"],
        avatar_url=row.get("avatar_url"),
        skills=_safe_json_list(row.get("skills")),
        availability_status=row.get("availability_status"),
        portfolio_links=_safe_json_list(row.get("portfolio_links")),
        portfolio_summary=row.get("portfolio_summary"),
        onboarding_completed=bool(row.get("onboarding_completed", False)),
        onboarding_completed_at=row.get("onboarding_completed_at"),
        profile_completeness_percent=int(row.get("profile_completeness_percent") or 0),
        character_class=_safe_character_class(row.get("character_class")),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def to_public_user_profile(
    profile: UserProfile,
    *,
    avg_rating: Optional[float] = None,
    review_count: int = 0,
    trust_score: Optional[float] = None,
    trust_score_updated_at: Optional[datetime] = None,
    confirmed_quest_count: int = 0,
    completion_rate: Optional[float] = None,
    typical_budget_band: Optional[str] = None,
    availability_status: Optional[str] = None,
    response_time_hint: Optional[str] = None,
    portfolio_links: Optional[List[str]] = None,
    portfolio_summary: Optional[str] = None,
    onboarding_completed: bool = False,
    onboarding_completed_at: Optional[datetime] = None,
    profile_completeness_percent: int = 0,
    reputation_stats: Optional["ReputationStats"] = None,
    faction_alignment: Optional[FactionAlignment] = None,
) -> PublicUserProfile:
    """Convert an internal profile to the public-safe API representation."""
    return PublicUserProfile(
        id=profile.id,
        username=profile.username,
        role=profile.role,
        level=profile.level,
        grade=profile.grade,
        xp=profile.xp,
        xp_to_next=profile.xp_to_next,
        stat_points=profile.stat_points,
        stats=profile.stats,
        badges=profile.badges,
        bio=profile.bio,
        avatar_url=profile.avatar_url,
        skills=profile.skills,
        character_class=profile.character_class,
        avg_rating=avg_rating,
        review_count=review_count,
        trust_score=trust_score,
        trust_score_updated_at=trust_score_updated_at,
        confirmed_quest_count=confirmed_quest_count,
        completion_rate=completion_rate,
        typical_budget_band=typical_budget_band,
        availability_status=availability_status,
        response_time_hint=response_time_hint,
        portfolio_links=portfolio_links if portfolio_links is not None else profile.portfolio_links,
        portfolio_summary=portfolio_summary if portfolio_summary is not None else profile.portfolio_summary,
        onboarding_completed=onboarding_completed,
        onboarding_completed_at=onboarding_completed_at,
        profile_completeness_percent=profile_completeness_percent,
        reputation_stats=reputation_stats,
        faction_alignment=faction_alignment,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


