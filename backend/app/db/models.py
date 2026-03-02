"""
SQLAlchemy ORM models — single source of truth for the database schema.

These models mirror the existing tables created by Alembic raw-SQL migrations.
With ``target_metadata = Base.metadata`` in alembic/env.py, Alembic can now
auto-generate migrations for any future schema changes.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class UserORM(Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="freelancer")

    # RPG fields
    level = Column(Integer, nullable=False, default=1)
    grade = Column(String(20), nullable=False, default="novice")
    xp = Column(Integer, nullable=False, default=0)
    xp_to_next = Column(Integer, nullable=False, default=100)

    # Stats
    stats_int = Column(Integer, nullable=False, default=10)
    stats_dex = Column(Integer, nullable=False, default=10)
    stats_cha = Column(Integer, nullable=False, default=10)

    # JSON fields
    badges = Column(JSONB, default="[]")
    bio = Column(String(500))
    skills = Column(JSONB, default="[]")

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

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
    )


class QuestORM(Base):
    __tablename__ = "quests"

    id = Column(String(50), primary_key=True)
    client_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    client_username = Column(String(50))
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    required_grade = Column(String(20), nullable=False, default="novice")
    skills = Column(JSONB, default="[]")
    budget = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="RUB")
    xp_reward = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="open")
    assigned_to = Column(String(50), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    client = relationship("UserORM", foreign_keys=[client_id], back_populates="quests_created")
    assignee = relationship("UserORM", foreign_keys=[assigned_to], back_populates="quests_assigned")
    applications = relationship("ApplicationORM", back_populates="quest", cascade="all, delete-orphan")
    transactions = relationship("TransactionORM", back_populates="quest")

    __table_args__ = (
        Index("idx_quests_status", "status"),
        Index("idx_quests_client_id", "client_id"),
        Index("idx_quests_assigned_to", "assigned_to"),
        Index("idx_quests_required_grade", "required_grade"),
        Index("idx_quests_created_at", created_at.desc()),
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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    quest = relationship("QuestORM", back_populates="applications")
    freelancer = relationship("UserORM", back_populates="applications")

    __table_args__ = (
        Index("idx_applications_quest_id", "quest_id"),
        Index("idx_applications_freelancer_id", "freelancer_id"),
        UniqueConstraint("quest_id", "freelancer_id", name="idx_applications_quest_freelancer"),
    )


class TransactionORM(Base):
    __tablename__ = "transactions"

    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quest_id = Column(String(50), ForeignKey("quests.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="RUB")
    type = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("UserORM", back_populates="transactions")
    quest = relationship("QuestORM", back_populates="transactions")

    __table_args__ = (
        Index("idx_transactions_user_id", "user_id"),
        Index("idx_transactions_quest_id", "quest_id"),
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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("UserORM", back_populates="wallets")

    __table_args__ = (
        UniqueConstraint("user_id", "currency", name="uq_wallets_user_currency"),
        Index("idx_wallets_user_id", "user_id"),
    )
