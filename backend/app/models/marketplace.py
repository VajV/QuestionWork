"""Marketplace and guild domain models for the talent market."""

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.models.user import GradeEnum, UserStats


TalentMarketMode = Literal["all", "solo", "guild", "top-guilds"]
GuildMemberRole = Literal["leader", "officer", "member"]
GuildTier = Literal["bronze", "silver", "gold", "platinum"]
ItemCategory = Literal["cosmetic", "collectible", "equipable"]
ArtifactEquipSlot = Literal["profile_artifact"]


class GuildBadge(BaseModel):
    id: str
    name: str
    slug: str
    role: GuildMemberRole
    member_count: int = Field(ge=0)
    rating: int = Field(ge=0)
    season_position: Optional[int] = Field(default=None, ge=1)


class GuildPublicBadge(BaseModel):
    id: str
    badge_code: str
    name: str
    slug: str
    accent: str
    season_code: Optional[str] = None
    family: Optional[str] = None
    awarded_at: datetime


class TalentMarketMember(BaseModel):
    id: str
    username: str
    level: int = Field(ge=1)
    grade: GradeEnum
    xp: int = Field(ge=0)
    xp_to_next: int = Field(ge=0)
    stats: UserStats
    badges_count: int = Field(ge=0)
    skills: List[str] = Field(default_factory=list)
    avg_rating: Optional[float] = None
    review_count: int = Field(ge=0)
    trust_score: Optional[float] = Field(default=None, ge=0, le=1)
    typical_budget_band: Optional[str] = None
    availability_status: Optional[str] = None
    response_time_hint: Optional[str] = None
    character_class: Optional[str] = None
    market_kind: Literal["solo", "guild"]
    rank_score: int = Field(ge=0)
    rank_signals: List[str] = Field(default_factory=list)
    guild: Optional[GuildBadge] = None


class GuildCard(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    emblem: str = "ember"
    member_count: int = Field(ge=0)
    member_limit: int = Field(ge=1)
    total_xp: int = Field(ge=0)
    avg_rating: Optional[float] = None
    confirmed_quests: int = Field(ge=0)
    treasury_balance: str
    guild_tokens: int = Field(ge=0)
    rating: int = Field(ge=0)
    season_position: Optional[int] = Field(default=None, ge=1)
    top_skills: List[str] = Field(default_factory=list)
    leader_username: Optional[str] = None

class GuildPublicMember(BaseModel):
    id: str
    username: str
    level: int = Field(ge=1)
    grade: GradeEnum
    xp: int = Field(ge=0)
    xp_to_next: int = Field(ge=0)
    stats: UserStats
    skills: List[str] = Field(default_factory=list)
    avg_rating: Optional[float] = None
    review_count: int = Field(ge=0)
    character_class: Optional[str] = None
    role: GuildMemberRole
    contribution: int = Field(ge=0)
    joined_at: datetime

class GuildActivityEntry(BaseModel):
    id: str
    event_type: Literal[
        "guild_created",
        "member_joined",
        "member_left",
        "quest_confirmed",
        "guild_xp_awarded",
        "guild_tier_promoted",
        "guild_milestone_unlocked",
    ]
    summary: str
    actor_user_id: Optional[str] = None
    actor_username: Optional[str] = None
    quest_id: Optional[str] = None
    treasury_delta: str
    guild_tokens_delta: int = Field(ge=0)
    contribution_delta: int = Field(ge=0)
    created_at: datetime


class GuildRewardCard(BaseModel):
    id: str
    card_code: str
    name: str
    rarity: Literal["common", "rare", "epic", "legendary"]
    family: str
    description: str
    accent: str
    item_category: ItemCategory = "collectible"
    awarded_to_user_id: Optional[str] = None
    awarded_to_username: Optional[str] = None
    source_quest_id: str
    dropped_at: datetime


class UserArtifact(BaseModel):
    """Single owned artifact/cosmetic item for profile cabinet display."""
    id: str
    card_code: str
    name: str
    rarity: Literal["common", "rare", "epic", "legendary"]
    family: str
    description: str
    accent: str
    item_category: ItemCategory
    is_equipped: bool = False
    equip_slot: Optional[ArtifactEquipSlot] = None
    equipped_at: Optional[datetime] = None
    equipped_effect_summary: Optional[str] = None
    source_quest_id: str
    dropped_at: datetime


class ArtifactCabinet(BaseModel):
    """Aggregated artifact/cosmetic collection for profile display."""
    cosmetics: List[UserArtifact] = Field(default_factory=list)
    collectibles: List[UserArtifact] = Field(default_factory=list)
    equipable: List[UserArtifact] = Field(default_factory=list)
    total: int = Field(ge=0)


class ArtifactEquipResponse(BaseModel):
    artifact: UserArtifact
    cabinet: ArtifactCabinet
    message: str


class GuildSeasonalSet(BaseModel):
    family: str
    label: str
    accent: str
    season_code: str
    target_cards: int = Field(ge=1)
    collected_cards: int = Field(ge=0)
    missing_cards: int = Field(ge=0)
    progress_percent: int = Field(ge=0, le=100)
    completed: bool = False
    rarity: Optional[Literal["common", "rare", "epic", "legendary"]] = None
    reward_label: str
    reward_treasury_bonus: str
    reward_guild_tokens_bonus: int = Field(ge=0)
    reward_badge_name: str
    reward_claimed: bool = False
    reward_claimed_at: Optional[datetime] = None


class GuildLeaderboardEntry(BaseModel):
    rank: int = Field(ge=1)
    member: GuildPublicMember
    trophy_count: int = Field(ge=0)
    family_label: Optional[str] = None


class GuildMilestone(BaseModel):
    """A shared guild milestone — unlocked when seasonal XP crosses a threshold."""
    milestone_code: str
    label: str
    description: str
    threshold_xp: int = Field(ge=0)
    unlocked: bool = False
    unlocked_at: Optional[datetime] = None
    reward_description: str = ""


class GuildContributionSummary(BaseModel):
    """Top-contributor summary for the guild detail page."""
    user_id: str
    username: str
    contribution: int = Field(ge=0)
    quests_completed: int = Field(ge=0)
    role: GuildMemberRole
    rank: int = Field(ge=1)


class GuildProgressionSnapshot(BaseModel):
    season_code: str = ""
    seasonal_xp: int = Field(default=0, ge=0)
    current_tier: GuildTier = "bronze"
    next_tier: Optional[GuildTier] = None
    next_tier_xp: Optional[int] = Field(default=None, ge=0)
    xp_to_next_tier: int = Field(default=0, ge=0)
    progress_percent: int = Field(default=0, ge=0, le=100)
    xp_bonus_percent: int = Field(default=0, ge=0)
    tier_benefits: List[str] = Field(default_factory=list)
    season_rank: Optional[int] = Field(default=None, ge=1)
    completed_sets: int = Field(ge=0)
    total_sets: int = Field(ge=0)
    claimed_rewards: int = Field(ge=0)
    leaderboard: List[GuildLeaderboardEntry] = Field(default_factory=list)
    milestones: List[GuildMilestone] = Field(default_factory=list)
    top_contributors: List[GuildContributionSummary] = Field(default_factory=list)


class GuildDetailResponse(BaseModel):
    guild: GuildCard
    members: List[GuildPublicMember] = Field(default_factory=list)
    activity: List[GuildActivityEntry] = Field(default_factory=list)
    trophies: List[GuildRewardCard] = Field(default_factory=list)
    seasonal_sets: List[GuildSeasonalSet] = Field(default_factory=list)
    badges: List[GuildPublicBadge] = Field(default_factory=list)
    progression_snapshot: GuildProgressionSnapshot = Field(default_factory=GuildProgressionSnapshot)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TalentMarketSummary(BaseModel):
    total_freelancers: int = Field(ge=0)
    solo_freelancers: int = Field(ge=0)
    guild_freelancers: int = Field(ge=0)
    total_guilds: int = Field(ge=0)
    top_solo_xp: int = Field(ge=0)
    top_guild_rating: int = Field(ge=0)


class TalentMarketResponse(BaseModel):
    mode: TalentMarketMode
    summary: TalentMarketSummary
    members: List[TalentMarketMember] = Field(default_factory=list)
    guilds: List[GuildCard] = Field(default_factory=list)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    has_more: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GuildCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    description: Optional[str] = Field(default=None, max_length=500)
    emblem: str = Field(default="ember", min_length=3, max_length=24)


class GuildActionResponse(BaseModel):
    guild_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Plan 11 — Solo (non-guild) player card drops
# ---------------------------------------------------------------------------

class SoloCardDrop(BaseModel):
    """Single card awarded to a solo freelancer from the player_card_drops table."""
    id: str
    card_code: str
    name: str
    rarity: Literal["common", "rare", "epic", "legendary"]
    family: str
    description: str
    accent: str
    item_category: ItemCategory
    quest_id: str
    dropped_at: datetime


class PlayerCardCollection(BaseModel):
    """Solo card collection shown on the player's profile.

    Solo players drop less frequently (~5 %) than guild members (~10 %) but
    their card pool has a better rarity floor — minimum rarity is *rare*.
    """
    drops: List[SoloCardDrop] = Field(default_factory=list)
    total: int = Field(ge=0)
    drop_rate_note: str = (
        "Соло-игроки получают карты реже (~5 %), но каждая карта — минимум rare-класса."
    )
