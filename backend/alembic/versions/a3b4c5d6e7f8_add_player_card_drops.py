"""add_player_card_drops

Revision ID: a3b4c5d6e7f8
Revises: z1a2b3c4d5e6
Create Date: 2026-03-11 20:00:00.000000

Changes:
- Create player_card_drops table for solo (non-guild) freelancer card drops.
  Separate from guild_reward_cards so solo drops are never constrained by
  guild_id NOT NULL and have their own richer rarity floor / card pool.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS player_card_drops (
            id              VARCHAR(50)  PRIMARY KEY,
            freelancer_id   VARCHAR(50)  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            quest_id        VARCHAR(50)  NOT NULL UNIQUE,
            card_code       VARCHAR(64)  NOT NULL,
            name            VARCHAR(120) NOT NULL,
            rarity          VARCHAR(20)  NOT NULL,
            family          VARCHAR(40)  NOT NULL,
            description     VARCHAR(255) NOT NULL DEFAULT '',
            accent          VARCHAR(30)  NOT NULL DEFAULT 'slate',
            item_category   VARCHAR(32)  NOT NULL DEFAULT 'collectible',
            dropped_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_player_card_drops_rarity
                CHECK (rarity IN ('common', 'rare', 'epic', 'legendary')),
            CONSTRAINT chk_player_card_drops_item_category
                CHECK (item_category IN ('cosmetic', 'collectible', 'equipable'))
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_player_card_drops_freelancer_dropped
            ON player_card_drops (freelancer_id, dropped_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_player_card_drops_freelancer_dropped;")
    op.execute("DROP TABLE IF EXISTS player_card_drops;")
