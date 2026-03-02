"""
Pydantic модели пользователя
"""

import json

from pydantic import BaseModel, Field, EmailStr
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
    stats: UserStats = Field(default_factory=UserStats)
    badges: List[UserBadge] = Field(default_factory=list)
    bio: Optional[str] = Field(None, max_length=500)
    skills: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    class Config:
        use_enum_values = True


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRoleEnum = Field(default=UserRoleEnum.freelancer)


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


def row_to_user_profile(row) -> UserProfile:
    """Convert an asyncpg Record (or dict-like) to UserProfile.

    Centralises the repetitive row→model mapping used across auth, users and quests endpoints.
    """
    return UserProfile(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        role=UserRoleEnum(row["role"]),
        level=row["level"],
        grade=GradeEnum(row["grade"]),
        xp=row["xp"],
        xp_to_next=row["xp_to_next"],
        stats=UserStats(
            int=row["stats_int"],
            dex=row["stats_dex"],
            cha=row["stats_cha"],
        ),
        badges=json.loads(row["badges"]) if row["badges"] else [],
        bio=row["bio"],
        skills=json.loads(row["skills"]) if row["skills"] else [],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
