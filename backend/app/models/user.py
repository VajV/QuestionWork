"""
Pydantic модели пользователя
"""

import json
import re

from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum


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
    class Config:
        populate_by_name = True


class UserBadge(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    earned_at: datetime


class UserProfile(BaseModel):
    id: str
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    role: UserRoleEnum = Field(default=UserRoleEnum.freelancer)
    level: int = Field(default=1, ge=1, le=100)
    grade: GradeEnum = Field(default=GradeEnum.novice)
    xp: int = Field(default=0, ge=0)
    xp_to_next: int = Field(default=100)
    stat_points: int = Field(default=0, ge=0)  # unspent RPG stat points
    stats: UserStats = Field(default_factory=UserStats)
    badges: List[UserBadge] = Field(default_factory=list)
    bio: Optional[str] = Field(None, max_length=500)
    skills: List[str] = Field(default_factory=list)
    character_class: Optional[str] = Field(None, description="RPG character class (e.g. berserk)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    class Config:
        use_enum_values = True


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRoleEnum = Field(default=UserRoleEnum.freelancer)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Enforce password complexity: >=1 uppercase, >=1 digit, >=1 special char."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", v):
            raise ValueError("Password must contain at least one special character")
        return v


class UserLogin(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


def _normalize_enum_value(raw_value: str) -> str:
    if not isinstance(raw_value, str):
        return raw_value
    if "." in raw_value:
        return raw_value.split(".")[-1]
    return raw_value


def row_to_user_profile(row) -> UserProfile:
    """Convert an asyncpg Record (or dict-like) to UserProfile.

    Centralises the repetitive row→model mapping used across auth, users and quests endpoints.
    """
    return UserProfile(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        role=UserRoleEnum(_normalize_enum_value(row["role"])),
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
        badges=json.loads(row["badges"]) if row["badges"] else [],
        bio=row["bio"],
        skills=json.loads(row["skills"]) if row["skills"] else [],
        character_class=row.get("character_class"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
