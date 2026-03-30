from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.quest import Quest
from app.models.user import GradeEnum, UserStats


class MatchBreakdown(BaseModel):
    skill_overlap: float = Field(default=0.0, ge=0, le=1)
    grade_fit: float = Field(default=0.0, ge=0, le=1)
    trust_score: float = Field(default=0.0, ge=0, le=1)
    availability: float = Field(default=0.0, ge=0, le=1)
    budget_fit: float = Field(default=0.0, ge=0, le=1)


class RecommendedFreelancerCard(BaseModel):
    id: str
    username: str
    level: int = Field(ge=1)
    grade: GradeEnum
    xp: int = Field(ge=0)
    xp_to_next: int = Field(ge=0)
    stats: UserStats
    skills: List[str] = Field(default_factory=list)
    avg_rating: Optional[float] = Field(default=None, ge=0, le=5)
    review_count: int = Field(default=0, ge=0)
    trust_score: Optional[float] = Field(default=None, ge=0, le=1)
    typical_budget_band: Optional[str] = None
    availability_status: Optional[str] = None
    response_time_hint: Optional[str] = None
    character_class: Optional[str] = None
    avatar_url: Optional[str] = None
    model_config = ConfigDict(use_enum_values=True)


class FreelancerRecommendation(BaseModel):
    freelancer: RecommendedFreelancerCard
    match_score: float = Field(ge=0, le=1)
    match_breakdown: MatchBreakdown = Field(default_factory=MatchBreakdown)
    matched_skills: List[str] = Field(default_factory=list)


class FreelancerRecommendationListResponse(BaseModel):
    quest_id: str
    recommendations: List[FreelancerRecommendation] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QuestRecommendation(BaseModel):
    quest: Quest
    match_score: float = Field(ge=0, le=1)
    match_breakdown: MatchBreakdown = Field(default_factory=MatchBreakdown)
    matched_skills: List[str] = Field(default_factory=list)


class QuestRecommendationListResponse(BaseModel):
    user_id: str
    recommendations: List[QuestRecommendation] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
