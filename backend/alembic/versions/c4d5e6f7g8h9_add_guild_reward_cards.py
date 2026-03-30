"""add_guild_reward_cards

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2026-03-11 15:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c4d5e6f7g8h9"
down_revision: Union[str, None] = "b3c4d5e6f7g8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_reward_cards (
            id VARCHAR(50) PRIMARY KEY,
            guild_id VARCHAR(50) NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
            source_quest_id VARCHAR(50) NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
            awarded_to_user_id VARCHAR(50) REFERENCES users(id) ON DELETE SET NULL,
            card_code VARCHAR(50) NOT NULL,
            name VARCHAR(80) NOT NULL,
            rarity VARCHAR(20) NOT NULL,
            family VARCHAR(30) NOT NULL,
            description VARCHAR(255) NOT NULL,
            accent VARCHAR(20) NOT NULL,
            dropped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_guild_reward_cards_source_quest UNIQUE (source_quest_id),
            CONSTRAINT chk_guild_reward_cards_rarity CHECK (rarity IN ('common', 'rare', 'epic', 'legendary'))
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_guild_reward_cards_guild_dropped ON guild_reward_cards (guild_id, dropped_at DESC);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_guild_reward_cards_guild_dropped;")
    op.execute("DROP TABLE IF EXISTS guild_reward_cards;")