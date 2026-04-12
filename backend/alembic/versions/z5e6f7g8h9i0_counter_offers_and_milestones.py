"""Add counter_offer fields to applications and quest_milestones table.

Revision ID: z5e6f7g8h9i0
Revises: z4d5e6f7g8h9
Create Date: 2026-04-11

"""
from typing import Union
from alembic import op
import sqlalchemy as sa

revision: str = "z5e6f7g8h9i0"
down_revision: Union[str, None] = "z4d5e6f7g8h9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Counter-offer fields on applications ─────────────────────────────────
    op.add_column(
        "applications",
        sa.Column(
            "counter_offer_price",
            sa.Numeric(10, 2),
            nullable=True,
            comment="Client counter-offer price, if client responded to proposed_price",
        ),
    )
    op.add_column(
        "applications",
        sa.Column(
            "counter_offer_status",
            sa.String(20),
            nullable=True,
            server_default=None,
            comment="pending | accepted | declined",
        ),
    )
    op.add_column(
        "applications",
        sa.Column(
            "counter_offer_message",
            sa.Text,
            nullable=True,
        ),
    )
    op.add_column(
        "applications",
        sa.Column(
            "counter_offered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "applications",
        sa.Column(
            "counter_responded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # CHECK constraint: only valid statuses
    op.create_check_constraint(
        "chk_applications_counter_offer_status",
        "applications",
        "counter_offer_status IS NULL OR counter_offer_status IN ('pending','accepted','declined')",
    )

    # ── Quest milestones table ────────────────────────────────────────────────
    op.create_table(
        "quest_milestones",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column(
            "quest_id",
            sa.String(50),
            sa.ForeignKey("quests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="RUB"),
        sa.Column("sort_order", sa.Integer, nullable=False, default=0),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_tx_id", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("amount > 0", name="chk_milestones_amount_positive"),
        sa.CheckConstraint(
            "status IN ('pending','active','completed','cancelled')",
            name="chk_milestones_status",
        ),
    )
    op.create_index("idx_milestones_quest_id", "quest_milestones", ["quest_id", "sort_order"])
    op.create_index(
        "idx_milestones_status",
        "quest_milestones",
        ["status"],
        postgresql_where=sa.text("status = 'active'"),
    )

    # ── Referral codes table ──────────────────────────────────────────────────
    op.create_table(
        "referrals",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column(
            "referrer_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column(
            "referred_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("referred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_granted", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("idx_referrals_referrer_id", "referrals", ["referrer_id"])
    op.create_index("idx_referrals_code", "referrals", ["code"], unique=True)

    # ── Weekly challenges table ───────────────────────────────────────────────
    op.create_table(
        "weekly_challenges",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("challenge_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("target_value", sa.Integer, nullable=False),
        sa.Column("xp_reward", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("target_value > 0", name="chk_challenges_target_positive"),
        sa.CheckConstraint("xp_reward > 0", name="chk_challenges_xp_positive"),
        sa.UniqueConstraint("week_start", "challenge_type", name="uq_weekly_challenge_type"),
    )
    op.create_index("idx_weekly_challenges_week", "weekly_challenges", ["week_start"])

    op.create_table(
        "user_challenge_progress",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "challenge_id",
            sa.String(50),
            sa.ForeignKey("weekly_challenges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("current_value", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reward_granted", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("user_id", "challenge_id", name="uq_user_challenge"),
    )
    op.create_index(
        "idx_user_challenge_progress_user",
        "user_challenge_progress",
        ["user_id", "challenge_id"],
    )


def downgrade() -> None:
    op.drop_table("user_challenge_progress")
    op.drop_table("weekly_challenges")
    op.drop_index("idx_referrals_code", "referrals")
    op.drop_index("idx_referrals_referrer_id", "referrals")
    op.drop_table("referrals")
    op.drop_index("idx_milestones_status", "quest_milestones")
    op.drop_index("idx_milestones_quest_id", "quest_milestones")
    op.drop_table("quest_milestones")
    op.drop_constraint("chk_applications_counter_offer_status", "applications", type_="check")
    op.drop_column("applications", "counter_responded_at")
    op.drop_column("applications", "counter_offered_at")
    op.drop_column("applications", "counter_offer_message")
    op.drop_column("applications", "counter_offer_status")
    op.drop_column("applications", "counter_offer_price")
