"""
SQLAlchemy ORM models — single source of truth for the database schema.

These models mirror the existing tables created by Alembic raw-SQL migrations.
With ``target_metadata = Base.metadata`` in alembic/env.py, Alembic can now
auto-generate migrations for any future schema changes.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


user_role_enum = Enum("client", "freelancer", "admin", name="user_role_enum")
grade_enum = Enum("novice", "junior", "middle", "senior", name="grade_enum")
quest_status_enum = Enum(
    "draft",
    "open",
    "assigned",
    "in_progress",
    "completed",
    "revision_requested",
    "confirmed",
    "cancelled",
    "disputed",
    name="quest_status_enum",
)


class UserORM(Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(user_role_enum, nullable=False, default="freelancer")

    # RPG fields
    level = Column(Integer, nullable=False, default=1)
    grade = Column(grade_enum, nullable=False, default="novice")
    xp = Column(Integer, nullable=False, default=0)
    xp_to_next = Column(Integer, nullable=False, default=100)

    # Stats
    stats_int = Column(Integer, nullable=False, default=10)
    stats_dex = Column(Integer, nullable=False, default=10)
    stats_cha = Column(Integer, nullable=False, default=10)

    # JSON fields
    badges = Column(JSONB, server_default=sa_text("'[]'::jsonb"))
    bio = Column(String(500))
    avatar_url = Column(String(500), nullable=True)
    skills = Column(JSONB, server_default=sa_text("'[]'::jsonb"))
    availability_status = Column(String(32), nullable=True)
    portfolio_links = Column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))
    portfolio_summary = Column(String(500), nullable=True)
    onboarding_completed = Column(Boolean, nullable=False, default=False, server_default=sa_text("FALSE"))
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)
    profile_completeness_percent = Column(Integer, nullable=False, default=0, server_default=sa_text("0"))

    # Character class
    character_class = Column(String(30), nullable=True)
    class_selected_at = Column(DateTime(timezone=True), nullable=True)
    class_trial_expires_at = Column(DateTime(timezone=True), nullable=True)
    totp_secret = Column(String(64), nullable=True)
    pending_totp_secret = Column(String(64), nullable=True)

    # Ban fields
    is_banned = Column(Boolean, nullable=False, default=False)
    banned_reason = Column(String(500), nullable=True)
    banned_at = Column(DateTime(timezone=True), nullable=True)

    # Reviews
    avg_rating = Column(Numeric(3, 2), nullable=True)
    review_count = Column(Integer, nullable=False, default=0)
    trust_score = Column(Numeric(5, 4), nullable=True)
    trust_score_breakdown = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    trust_score_updated_at = Column(DateTime(timezone=True), nullable=True)

    # Stat / perk points
    stat_points = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))

    # Relationships
    quests_created = relationship("QuestORM", foreign_keys="QuestORM.client_id", back_populates="client")
    quests_assigned = relationship("QuestORM", foreign_keys="QuestORM.assigned_to", back_populates="assignee")
    applications = relationship("ApplicationORM", back_populates="freelancer")
    transactions = relationship("TransactionORM", back_populates="user")
    wallets = relationship("WalletORM", back_populates="user")

    # Indexes (match existing migration b1c2d3e4f567)
    __table_args__ = (
        Index("idx_users_grade", "grade"),
        Index("idx_users_role", "role"),
        Index(
            "idx_users_character_class",
            "character_class",
            postgresql_where=sa_text("character_class IS NOT NULL"),
        ),
        Index("ix_users_is_banned", "is_banned"),
        CheckConstraint("xp >= 0", name="chk_users_xp_non_negative"),
        CheckConstraint("level >= 1", name="chk_users_level_positive"),
        CheckConstraint("xp_to_next >= 0", name="chk_users_xp_to_next_positive"),
        CheckConstraint("stat_points >= 0", name="chk_users_stat_points_non_negative"),
        CheckConstraint("avg_rating >= 0 AND avg_rating <= 5", name="chk_users_avg_rating_range"),
        CheckConstraint("review_count >= 0", name="chk_users_review_count_non_negative"),
        CheckConstraint(
            "trust_score IS NULL OR (trust_score >= 0 AND trust_score <= 1)",
            name="chk_users_trust_score_range",
        ),
    )


class QuestORM(Base):
    __tablename__ = "quests"

    id = Column(String(50), primary_key=True)
    client_id = Column(String(50), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    client_username = Column(String(50))
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    required_grade = Column(grade_enum, nullable=False, default="novice")
    skills = Column(JSONB, server_default=sa_text("'[]'::jsonb"))
    budget = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="RUB")
    xp_reward = Column(Integer, nullable=False)
    status = Column(quest_status_enum, nullable=False, default="open")
    assigned_to = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    delivery_note = Column(Text, nullable=True)
    delivery_url = Column(Text, nullable=True)
    delivery_submitted_at = Column(DateTime(timezone=True), nullable=True)
    revision_reason = Column(Text, nullable=True)
    revision_requested_at = Column(DateTime(timezone=True), nullable=True)
    is_urgent = Column(Boolean, nullable=False, default=False)
    deadline = Column(DateTime(timezone=True), nullable=True)
    required_portfolio = Column(Boolean, nullable=False, default=False)
    revision_count = Column(Integer, nullable=False, default=0)
    platform_fee_percent = Column(Numeric(5, 2), nullable=True)

    # Relationships
    client = relationship("UserORM", foreign_keys=[client_id], back_populates="quests_created")
    assignee = relationship("UserORM", foreign_keys=[assigned_to], back_populates="quests_assigned")
    applications = relationship("ApplicationORM", back_populates="quest", cascade="all, delete-orphan")
    transactions = relationship("TransactionORM", back_populates="quest")
    status_history = relationship("QuestStatusHistoryORM", back_populates="quest", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_quests_status", "status"),
        Index("idx_quests_client_id", "client_id"),
        Index("idx_quests_assigned_to", "assigned_to"),
        Index("idx_quests_required_grade", "required_grade"),
        Index("idx_quests_created_at", created_at.desc()),
        Index(
            "idx_quests_is_urgent",
            "is_urgent",
            postgresql_where=sa_text("is_urgent = TRUE"),
        ),
        Index(
            "idx_quests_deadline",
            "deadline",
            postgresql_where=sa_text("deadline IS NOT NULL"),
        ),
        Index("idx_quests_skills_gin", "skills", postgresql_using="gin"),
        CheckConstraint("budget > 0", name="chk_quests_budget_positive"),
        CheckConstraint("xp_reward >= 0", name="chk_quests_xp_reward_non_negative"),
    )


class QuestStatusHistoryORM(Base):
    __tablename__ = "quest_status_history"

    id = Column(String(50), primary_key=True)
    quest_id = Column(String(50), ForeignKey("quests.id", ondelete="CASCADE"), nullable=False)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    changed_by = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"), nullable=False)

    quest = relationship("QuestORM", back_populates="status_history")

    __table_args__ = (
        Index("idx_quest_status_history_quest", "quest_id", "created_at"),
    )


class ApplicationORM(Base):
    __tablename__ = "applications"

    id = Column(String(50), primary_key=True)
    quest_id = Column(String(50), ForeignKey("quests.id", ondelete="CASCADE"), nullable=False)
    freelancer_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    freelancer_username = Column(String(50), nullable=False)
    freelancer_grade = Column(String(20), nullable=False)
    cover_letter = Column(Text)
    proposed_price = Column(Numeric(10, 2))
    created_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))

    # Relationships
    quest = relationship("QuestORM", back_populates="applications")
    freelancer = relationship("UserORM", back_populates="applications")

    __table_args__ = (
        Index("idx_applications_quest_id", "quest_id"),
        Index("idx_applications_freelancer_id", "freelancer_id"),
        Index("idx_applications_quest_freelancer", "quest_id", "freelancer_id", unique=True),
    )


class TransactionORM(Base):
    __tablename__ = "transactions"

    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    quest_id = Column(String(50), ForeignKey("quests.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="RUB")
    type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="completed")
    idempotency_key = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))

    # Relationships
    user = relationship("UserORM", back_populates="transactions")
    quest = relationship("QuestORM", back_populates="transactions")

    __table_args__ = (
        Index("idx_transactions_user_id", "user_id"),
        Index("idx_transactions_quest_id", "quest_id"),
        Index("idx_transactions_created_at", created_at.desc()),
        Index(
            "idx_transactions_status",
            "status",
            postgresql_where=sa_text("status != 'completed'"),
        ),
        Index(
            "idx_transactions_pending_withdrawal",
            created_at.desc(),
            postgresql_where=sa_text("type = 'withdrawal' AND status = 'pending'"),
        ),
        Index(
            "uq_transactions_withdrawal_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=sa_text("type = 'withdrawal' AND idempotency_key IS NOT NULL"),
        ),
        CheckConstraint(
            "type IN ('income', 'expense', 'hold', 'refund', 'urgent_bonus_charge', 'urgent_bonus', 'commission', 'withdrawal', 'admin_adjust', 'credit', 'quest_payment', 'release', 'platform_fee')",
            name="chk_transactions_type_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'completed', 'rejected', 'refunded', 'held', 'failed')",
            name="chk_transactions_status_allowed",
        ),
        CheckConstraint("amount > 0", name="chk_transactions_amount_positive"),
    )


class WalletORM(Base):
    """
    Wallet ledger — running balance snapshot per user per currency.

    Uses ``version`` column for optimistic locking:
    UPDATE wallets SET balance = ..., version = version + 1
    WHERE user_id = $1 AND currency = $2 AND version = $3
    If affected rows == 0 → concurrent modification detected → retry or fail.
    """
    __tablename__ = "wallets"

    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    currency = Column(String(10), nullable=False, default="RUB")
    balance = Column(Numeric(12, 2), nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))

    # Relationships
    user = relationship("UserORM", back_populates="wallets")

    __table_args__ = (
        UniqueConstraint("user_id", "currency", name="uq_wallets_user_currency"),
        Index("idx_wallets_user_id", "user_id"),
        CheckConstraint("balance >= 0", name="chk_wallets_balance_non_negative"),
    )


class GuildORM(Base):
    __tablename__ = "guilds"

    id = Column(String(50), primary_key=True)
    owner_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(80), nullable=False, unique=True)
    slug = Column(String(80), nullable=False, unique=True)
    description = Column(String(500), nullable=True)
    emblem = Column(String(24), nullable=False, default="ember")
    is_public = Column(Boolean, nullable=False, default=True)
    member_limit = Column(Integer, nullable=False, default=20)
    treasury_balance = Column(Numeric(12, 2), nullable=False, default=0)
    guild_tokens = Column(Integer, nullable=False, default=0)
    rating = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (Index("idx_guilds_rating", rating.desc(), created_at.desc()),)


class GuildMemberORM(Base):
    __tablename__ = "guild_members"

    id = Column(String(50), primary_key=True)
    guild_id = Column(String(50), ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False, default="member")
    contribution = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="active")
    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_guild_member_pair"),
        Index("idx_guild_members_guild", "guild_id", "status", "joined_at"),
        Index(
            "uq_guild_members_active_user",
            "user_id",
            unique=True,
            postgresql_where=sa_text("status = 'active'"),
        ),
    )


class GuildActivityORM(Base):
    __tablename__ = "guild_activity"

    id = Column(String(50), primary_key=True)
    guild_id = Column(String(50), ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    quest_id = Column(String(50), ForeignKey("quests.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(40), nullable=False)
    summary = Column(String(255), nullable=False)
    payload = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    treasury_delta = Column(Numeric(12, 2), nullable=False, default=0)
    guild_tokens_delta = Column(Integer, nullable=False, default=0)
    contribution_delta = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_guild_activity_guild_created", "guild_id", created_at.desc()),
        Index("idx_guild_activity_user_created", "user_id", created_at.desc()),
    )


class GuildSeasonProgressORM(Base):
    __tablename__ = "guild_season_progress"

    id = Column(String(50), primary_key=True)
    guild_id = Column(String(50), ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False)
    season_code = Column(String(16), nullable=False)
    seasonal_xp = Column(Integer, nullable=False, default=0)
    current_tier = Column(String(20), nullable=False, default="bronze")
    last_tier_change_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("guild_id", "season_code", name="uq_guild_season_progress_pair"),
        CheckConstraint("seasonal_xp >= 0", name="chk_guild_season_progress_xp_non_negative"),
        CheckConstraint(
            "current_tier IN ('bronze', 'silver', 'gold', 'platinum')",
            name="chk_guild_season_progress_tier",
        ),
        Index("idx_guild_season_progress_season_rank", "season_code", seasonal_xp.desc(), updated_at.asc()),
        Index("idx_guild_season_progress_guild", "guild_id", "season_code"),
    )


class GuildRewardCardORM(Base):
    __tablename__ = "guild_reward_cards"

    id = Column(String(50), primary_key=True)
    guild_id = Column(String(50), ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False)
    source_quest_id = Column(String(50), ForeignKey("quests.id", ondelete="CASCADE"), nullable=False, unique=True)
    awarded_to_user_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    card_code = Column(String(50), nullable=False)
    name = Column(String(80), nullable=False)
    rarity = Column(String(20), nullable=False)
    family = Column(String(30), nullable=False)
    description = Column(String(255), nullable=False)
    accent = Column(String(20), nullable=False)
    dropped_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_guild_reward_cards_guild_dropped", "guild_id", dropped_at.desc()),
    )


class GuildSeasonalRewardORM(Base):
    __tablename__ = "guild_seasonal_rewards"

    id = Column(String(50), primary_key=True)
    guild_id = Column(String(50), ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False)
    family = Column(String(30), nullable=False)
    season_code = Column(String(40), nullable=False)
    label = Column(String(80), nullable=False)
    accent = Column(String(20), nullable=False)
    treasury_bonus = Column(Numeric(12, 2), nullable=False, default=0)
    guild_tokens_bonus = Column(Integer, nullable=False, default=0)
    badge_name = Column(String(80), nullable=False)
    claimed_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("guild_id", "season_code", "family", name="uq_guild_seasonal_reward_claim"),
        Index("idx_guild_seasonal_rewards_guild_claimed", "guild_id", claimed_at.desc()),
    )


class GuildBadgeORM(Base):
    __tablename__ = "guild_badges"

    id = Column(String(50), primary_key=True)
    guild_id = Column(String(50), ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False)
    badge_code = Column(String(80), nullable=False)
    name = Column(String(80), nullable=False)
    slug = Column(String(80), nullable=False)
    accent = Column(String(20), nullable=False)
    season_code = Column(String(40), nullable=True)
    family = Column(String(30), nullable=True)
    awarded_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("guild_id", "badge_code", name="uq_guild_badges_guild_badge_code"),
        Index("idx_guild_badges_guild_awarded", "guild_id", awarded_at.desc()),
        Index("idx_guild_badges_slug", "slug"),
    )


class GuildSeasonRewardConfigORM(Base):
    __tablename__ = "guild_season_reward_configs"

    id = Column(String(50), primary_key=True)
    season_code = Column(String(40), nullable=False)
    family = Column(String(30), nullable=False)
    label = Column(String(80), nullable=False)
    accent = Column(String(20), nullable=False)
    treasury_bonus = Column(Numeric(12, 2), nullable=False, default=0)
    guild_tokens_bonus = Column(Integer, nullable=False, default=0)
    badge_name = Column(String(80), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("season_code", "family", name="uq_guild_season_reward_config_pair"),
        Index("idx_guild_season_reward_configs_active", "season_code", "is_active"),
    )


class EventORM(Base):
    __tablename__ = "events"

    id = Column(String(50), primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    xp_multiplier = Column(Numeric(4, 2), nullable=False, default=1.0)
    badge_reward_id = Column(String(50), ForeignKey("badges.id", ondelete="SET NULL"), nullable=True)
    max_participants = Column(Integer, nullable=True)
    created_by = Column(String(50), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'ended', 'finalized')", name="chk_events_status"),
        CheckConstraint("xp_multiplier >= 1.0 AND xp_multiplier <= 5.0", name="chk_events_xp_multiplier"),
        CheckConstraint("end_at > start_at", name="chk_events_dates"),
        Index("idx_events_status", "status"),
    )


class EventParticipantORM(Base):
    __tablename__ = "event_participants"

    id = Column(String(50), primary_key=True)
    event_id = Column(String(50), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, nullable=False, default=0)
    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_participant"),
        CheckConstraint("score >= 0", name="chk_event_participants_score"),
        Index("idx_event_participants_user", "user_id"),
    )


class EventLeaderboardORM(Base):
    __tablename__ = "event_leaderboard"

    id = Column(String(50), primary_key=True)
    event_id = Column(String(50), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rank = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False, default=0)
    xp_bonus = Column(Integer, nullable=False, default=0)
    badge_awarded = Column(Boolean, nullable=False, default=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_leaderboard_entry"),
        CheckConstraint("rank >= 1", name="chk_event_leaderboard_rank"),
        Index("idx_event_leaderboard_event", "event_id", "rank"),
        Index("idx_event_leaderboard_user", "user_id"),
    )


class BadgeORM(Base):
    __tablename__ = "badges"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String(100), nullable=False, default="medal")
    criteria_type = Column(String(50), nullable=False)
    criteria_value = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))


class UserBadgeORM(Base):
    __tablename__ = "user_badges"

    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    badge_id = Column(String(50), ForeignKey("badges.id", ondelete="CASCADE"), nullable=False)
    earned_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),
        Index("idx_user_badges_user", "user_id"),
    )


class NotificationORM(Base):
    __tablename__ = "notifications"

    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    event_type = Column(String(50), nullable=False, default="general")
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_notifications_user", "user_id", "is_read", created_at.desc()),
    )


class AdminLogORM(Base):
    __tablename__ = "admin_logs"

    id = Column(String(50), primary_key=True)
    admin_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(255), nullable=True)
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    command_id = Column(UUID(as_uuid=False), ForeignKey("command_requests.id", ondelete="SET NULL"), nullable=True)
    job_id = Column(UUID(as_uuid=False), ForeignKey("background_jobs.id", ondelete="SET NULL"), nullable=True)
    request_id = Column(String(64), nullable=True)
    trace_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_admin_logs_admin_id", "admin_id"),
        Index("idx_admin_logs_created_at", created_at.desc()),
        Index("idx_admin_logs_target", "target_type", "target_id"),
    )


class BackupJobORM(Base):
    __tablename__ = "backup_jobs"

    id = Column(String(50), primary_key=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="running")
    size_bytes = Column(BigInteger, nullable=True)
    path = Column(Text, nullable=True)
    error = Column(Text, nullable=True)


class QuestReviewORM(Base):
    __tablename__ = "quest_reviews"

    id = Column(String(50), primary_key=True)
    quest_id = Column(String(50), ForeignKey("quests.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reviewee_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(SmallInteger, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("quest_id", "reviewer_id", name="uq_quest_reviews_quest_reviewer"),
        Index("idx_quest_reviews_reviewer", "reviewer_id"),
        Index("idx_quest_reviews_reviewee", "reviewee_id"),
        Index(
            "idx_quest_reviews_5star",
            "reviewee_id",
            postgresql_where=sa_text("rating = 5"),
        ),
        CheckConstraint("rating >= 1 AND rating <= 5", name="chk_quest_reviews_rating_range"),
    )


class QuestMessageORM(Base):
    __tablename__ = "quest_messages"

    id = Column(String(50), primary_key=True)
    quest_id = Column(String(50), ForeignKey("quests.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))
    message_type = Column(String(20), nullable=False, default="user")

    __table_args__ = (
        Index("idx_quest_messages_quest", "quest_id", "created_at"),
        Index("idx_quest_messages_author", "author_id"),
    )


class QuestMessageReadORM(Base):
    __tablename__ = "quest_message_reads"

    quest_id = Column(String(50), ForeignKey("quests.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    last_read_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_quest_message_reads_user", "user_id", "last_read_at"),
    )


class QuestTemplateORM(Base):
    __tablename__ = "quest_templates"

    id = Column(String(50), primary_key=True)
    owner_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, server_default=sa_text("''"))
    required_grade = Column(String(20), nullable=False, default="novice")
    skills = Column(JSONB, nullable=False, server_default=sa_text("'[]'::jsonb"))
    budget = Column(Numeric(15, 2), nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="RUB")
    is_urgent = Column(Boolean, nullable=False, default=False)
    required_portfolio = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_quest_templates_owner", "owner_id"),
    )


class UserClassProgressORM(Base):
    __tablename__ = "user_class_progress"

    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    class_id = Column(String(30), nullable=False)
    class_xp = Column(Integer, nullable=False, default=0)
    class_level = Column(Integer, nullable=False, default=1)
    quests_completed = Column(Integer, nullable=False, default=0)
    consecutive_quests = Column(Integer, nullable=False, default=0)
    last_quest_at = Column(DateTime(timezone=True), nullable=True)
    burnout_until = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=sa_text("CURRENT_TIMESTAMP"))
    perk_points_spent = Column(Integer, nullable=False, default=0)
    rage_active_until = Column(DateTime(timezone=True), nullable=True)
    bonus_perk_points = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_ucp_class_id", "class_id"),
        Index("idx_ucp_user_id", "user_id"),
        CheckConstraint("class_level >= 1", name="chk_class_level_positive"),
        CheckConstraint("perk_points_spent >= 0", name="chk_perk_points_non_negative"),
    )


class UserPerkORM(Base):
    __tablename__ = "user_perks"

    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    perk_id = Column(String(60), nullable=False)
    class_id = Column(String(30), nullable=False)
    unlocked_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_user_perks_unique", "user_id", "perk_id", unique=True),
        Index("idx_user_perks_user", "user_id"),
    )


class UserAbilityORM(Base):
    __tablename__ = "user_abilities"

    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    ability_id = Column(String(60), primary_key=True)
    class_id = Column(String(30), nullable=False)
    last_activated_at = Column(DateTime(timezone=True), nullable=True)
    active_until = Column(DateTime(timezone=True), nullable=True)
    cooldown_until = Column(DateTime(timezone=True), nullable=True)
    times_used = Column(Integer, nullable=False, default=0)


class EmailOutboxORM(Base):
    __tablename__ = "email_outbox"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(String(64), nullable=True)
    email_address = Column(String(255), nullable=False)
    template_key = Column(String(100), nullable=False)
    template_params = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    status = Column(String(20), nullable=False, server_default=sa_text("'pending'"))
    send_after = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))
    sent_at = Column(DateTime(timezone=True), nullable=True)
    attempt_count = Column(Integer, nullable=False, server_default=sa_text("0"))
    error_message = Column(Text, nullable=True)
    command_id = Column(UUID(as_uuid=False), ForeignKey("command_requests.id", ondelete="SET NULL"), nullable=True)
    job_id = Column(UUID(as_uuid=False), ForeignKey("background_jobs.id", ondelete="SET NULL"), nullable=True)
    dedupe_key = Column(String(200), nullable=True)
    provider_message_id = Column(String(255), nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))

    __table_args__ = (
        Index(
            "idx_email_outbox_status_send_after",
            "status",
            "send_after",
            postgresql_where=sa_text("status = 'pending'"),
        ),
        # P1-19 FIX: unique partial index prevents duplicate emails for the same dedupe_key
        Index(
            "uq_email_outbox_dedupe_key",
            "dedupe_key",
            unique=True,
            postgresql_where=sa_text("dedupe_key IS NOT NULL"),
        ),
    )


class CommandRequestORM(Base):
    __tablename__ = "command_requests"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    command_kind = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)
    dedupe_key = Column(String(255), nullable=True)
    requested_by_user_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_by_admin_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    request_ip = Column(INET, nullable=True)
    request_user_agent = Column(Text, nullable=True)
    request_id = Column(String(64), nullable=True)
    trace_id = Column(String(64), nullable=True)
    payload_json = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    result_json = Column(JSONB, nullable=True)
    error_code = Column(String(100), nullable=True)
    error_text = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))

    __table_args__ = (
        Index(
            "uq_command_requests_dedupe_active",
            "dedupe_key",
            unique=True,
            postgresql_where=sa_text("dedupe_key IS NOT NULL AND status IN ('accepted', 'running')"),
        ),
        Index("idx_command_requests_kind_submitted_at", "command_kind", submitted_at.desc()),
        Index("idx_command_requests_admin_submitted_at", "requested_by_admin_id", submitted_at.desc()),
    )


class BackgroundJobORM(Base):
    __tablename__ = "background_jobs"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    kind = Column(String(100), nullable=False)
    queue_name = Column(String(50), nullable=False, server_default=sa_text("'default'"))
    status = Column(String(20), nullable=False)
    priority = Column(SmallInteger, nullable=False, server_default=sa_text("100"))
    dedupe_key = Column(String(255), nullable=True)
    payload_json = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    scheduled_for = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))
    available_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))
    enqueued_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    last_error_code = Column(String(100), nullable=True)
    last_enqueue_error = Column(Text, nullable=True)
    queue_publish_attempts = Column(Integer, nullable=False, server_default=sa_text("0"))
    attempt_count = Column(Integer, nullable=False, server_default=sa_text("0"))
    max_attempts = Column(Integer, nullable=False, server_default=sa_text("5"))
    lock_token = Column(UUID(as_uuid=False), nullable=True)
    locked_by = Column(String(255), nullable=True)
    trace_id = Column(String(64), nullable=True)
    request_id = Column(String(64), nullable=True)
    created_by_user_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_admin_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    command_id = Column(UUID(as_uuid=False), ForeignKey("command_requests.id", ondelete="SET NULL"), nullable=True)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(UUID(as_uuid=False), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))

    __table_args__ = (
        Index(
            "uq_background_jobs_dedupe_active",
            "dedupe_key",
            unique=True,
            postgresql_where=sa_text("dedupe_key IS NOT NULL AND status IN ('queued', 'running', 'retry_scheduled')"),
        ),
        Index("idx_background_jobs_status_scheduled_for", "status", "scheduled_for"),
        Index("idx_background_jobs_kind_status_scheduled_for", "kind", "status", "scheduled_for"),
        Index("idx_background_jobs_command_id", "command_id"),
    )


class BackgroundJobAttemptORM(Base):
    __tablename__ = "background_job_attempts"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    job_id = Column(UUID(as_uuid=False), ForeignKey("background_jobs.id", ondelete="CASCADE"), nullable=False)
    attempt_no = Column(Integer, nullable=False)
    worker_id = Column(String(255), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False)
    error_code = Column(String(100), nullable=True)
    error_text = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    external_ref = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))

    __table_args__ = (
        UniqueConstraint("job_id", "attempt_no", name="uq_background_job_attempts_job_attempt_no"),
        Index("idx_background_job_attempts_status_created_at", "status", created_at),
    )


class RuntimeHeartbeatORM(Base):
    __tablename__ = "runtime_heartbeats"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    runtime_kind = Column(String(50), nullable=False)
    runtime_id = Column(String(255), nullable=False)
    hostname = Column(String(255), nullable=False)
    pid = Column(Integer, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), nullable=False)
    meta_json = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("runtime_kind", "runtime_id", name="uq_runtime_heartbeats_kind_runtime_id"),
        Index("idx_runtime_heartbeats_kind_last_seen", "runtime_kind", "last_seen_at"),
    )


# ── Tables added by analytics/lifecycle/growth migrations ────────────────────


class AnalyticsEventORM(Base):
    __tablename__ = "analytics_events"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    event_name = Column(String(100), nullable=False)
    user_id = Column(String(64), nullable=True)
    session_id = Column(String(64), nullable=True)
    role = Column(String(20), nullable=True)
    source = Column(String(100), nullable=True)
    path = Column(String(500), nullable=True)
    properties_json = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))

    __table_args__ = (
        Index("idx_analytics_events_event_name", "event_name"),
        Index(
            "idx_analytics_events_user_id",
            "user_id",
            postgresql_where=sa_text("user_id IS NOT NULL"),
        ),
        Index("idx_analytics_events_created_at", created_at.desc()),
    )


class LifecycleCampaignORM(Base):
    __tablename__ = "lifecycle_campaigns"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    campaign_key = Column(String(100), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=sa_text("TRUE"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))


class LifecycleMessageORM(Base):
    __tablename__ = "lifecycle_messages"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(String(64), nullable=False)
    campaign_key = Column(String(100), nullable=False)
    trigger_data = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    status = Column(String(20), nullable=False, server_default=sa_text("'pending'"))
    send_after = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    idempotency_key = Column(String(200), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))

    __table_args__ = (
        Index(
            "idx_lifecycle_messages_status_send_after",
            "status",
            "send_after",
            postgresql_where=sa_text("status = 'pending'"),
        ),
        Index("idx_lifecycle_messages_user_campaign", "user_id", "campaign_key"),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'suppressed')",
            name="chk_lifecycle_messages_status",
        ),
    )


class SavedSearchORM(Base):
    __tablename__ = "saved_searches"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(String(64), nullable=False)
    name = Column(String(200), nullable=True)
    search_type = Column(String(20), nullable=False)
    filters_json = Column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    alert_enabled = Column(Boolean, nullable=False, server_default=sa_text("FALSE"))
    last_alerted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))

    __table_args__ = (
        Index("idx_saved_searches_user_id", "user_id"),
        CheckConstraint(
            "search_type IN ('talent', 'quest')",
            name="chk_saved_searches_search_type",
        ),
    )


class NotificationPreferenceORM(Base):
    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    user_id = Column(String(64), nullable=False, unique=True)
    transactional_enabled = Column(Boolean, nullable=False, server_default=sa_text("TRUE"))
    growth_enabled = Column(Boolean, nullable=False, server_default=sa_text("TRUE"))
    digest_enabled = Column(Boolean, nullable=False, server_default=sa_text("TRUE"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))


class GrowthLeadORM(Base):
    __tablename__ = "growth_leads"

    id = Column(Text, primary_key=True)
    email = Column(Text, nullable=False)
    company_name = Column(Text, nullable=False)
    contact_name = Column(Text, nullable=False)
    use_case = Column(Text, nullable=False)
    budget_band = Column(Text, nullable=True)
    message = Column(Text, nullable=True)
    source = Column(Text, nullable=False)
    utm_source = Column(Text, nullable=True)
    utm_medium = Column(Text, nullable=True)
    utm_campaign = Column(Text, nullable=True)
    utm_term = Column(Text, nullable=True)
    utm_content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("CURRENT_TIMESTAMP"))
    # Nurture fields (added by p6q7r8s9t0u1 migration)
    ref = Column(Text, nullable=True)
    landing_path = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=sa_text("'new'"))
    last_contacted_at = Column(DateTime(timezone=True), nullable=True)
    next_contact_at = Column(DateTime(timezone=True), nullable=True)
    nurture_stage = Column(Text, nullable=False, server_default=sa_text("'intake'"))
    converted_user_id = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_growth_leads_created_at", created_at.desc()),
        Index("ix_growth_leads_email", "email"),
        Index("ix_growth_leads_status_next_contact", "status", "next_contact_at"),
    )


class ShortlistORM(Base):
    __tablename__ = "shortlists"

    id = Column(String(50), primary_key=True)
    client_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    freelancer_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))

    __table_args__ = (
        UniqueConstraint("client_id", "freelancer_id", name="uq_shortlists_client_freelancer"),
        Index("idx_shortlists_client", "client_id", created_at.desc()),
    )


class DisputeORM(Base):
    __tablename__ = "disputes"

    id = Column(String(50), primary_key=True)
    quest_id = Column(String(50), ForeignKey("quests.id", ondelete="RESTRICT"), nullable=False)
    initiator_id = Column(String(50), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    respondent_id = Column(String(50), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reason = Column(Text, nullable=False)
    response_text = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, server_default=sa_text("'open'"))
    resolution_type = Column(String(20), nullable=True)
    partial_percent = Column(Numeric(5, 2), nullable=True)
    resolution_note = Column(Text, nullable=True)
    moderator_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    auto_escalate_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=sa_text("NOW()"))
    responded_at = Column(DateTime(timezone=True), nullable=True)
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_disputes_quest_id", "quest_id"),
        Index("idx_disputes_initiator", "initiator_id"),
        Index("idx_disputes_respondent", "respondent_id"),
        Index("idx_disputes_status", "status"),
        Index(
            "idx_disputes_auto_escalate",
            "auto_escalate_at",
            postgresql_where=sa_text("status IN ('open', 'responded')"),
        ),
        CheckConstraint(
            "partial_percent IS NULL OR (partial_percent >= 1 AND partial_percent <= 99)",
            name="chk_disputes_partial_percent",
        ),
        CheckConstraint(
            "resolution_type IS NULL OR resolution_type IN ('refund', 'partial', 'freelancer')",
            name="chk_disputes_resolution_type",
        ),
        CheckConstraint(
            "status IN ('open', 'responded', 'escalated', 'resolved', 'closed')",
            name="chk_disputes_status",
        ),
    )
