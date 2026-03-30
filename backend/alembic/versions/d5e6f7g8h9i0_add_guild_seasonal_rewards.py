"""add_guild_seasonal_rewards

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-03-11 18:20:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d5e6f7g8h9i0"
down_revision: Union[str, None] = "c4d5e6f7g8h9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_seasonal_rewards (
            id VARCHAR(50) PRIMARY KEY,
            guild_id VARCHAR(50) NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
            family VARCHAR(30) NOT NULL,
            season_code VARCHAR(40) NOT NULL,
            label VARCHAR(80) NOT NULL,
            accent VARCHAR(20) NOT NULL,
            treasury_bonus NUMERIC(12, 2) NOT NULL DEFAULT 0,
            guild_tokens_bonus INTEGER NOT NULL DEFAULT 0,
            badge_name VARCHAR(80) NOT NULL,
            claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_guild_seasonal_reward_claim UNIQUE (guild_id, season_code, family)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_guild_seasonal_rewards_guild_claimed ON guild_seasonal_rewards (guild_id, claimed_at DESC);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_guild_seasonal_rewards_guild_claimed;")
    op.execute("DROP TABLE IF EXISTS guild_seasonal_rewards;")
