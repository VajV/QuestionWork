"""expand_guild_progression

Revision ID: b4c5d6e7f8g9
Revises: a3b4c5d6e7f8
Create Date: 2026-03-23 12:00:00.000000

Changes:
- Create guild_milestones table to track shared guild progression milestones.
  Each row records when a guild unlocked a specific milestone code in a given season.
  Additive-only — no existing tables or columns are altered.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c5d6e7f8g9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guild_milestones",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("guild_id", sa.Text(), nullable=False),
        sa.Column("season_code", sa.Text(), nullable=False),
        sa.Column("milestone_code", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("threshold_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["guild_id"], ["guilds.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_guild_milestones_guild_season",
        "guild_milestones",
        ["guild_id", "season_code"],
    )
    op.create_unique_constraint(
        "uq_guild_milestones_guild_season_code",
        "guild_milestones",
        ["guild_id", "season_code", "milestone_code"],
    )


def downgrade() -> None:
    op.drop_table("guild_milestones")
