"""add_guild_reward_card_equipment

Revision ID: z4d5e6f7g8h9
Revises: z3c4d5e6f7g8
Create Date: 2026-03-25 21:35:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "z4d5e6f7g8h9"
down_revision: Union[str, None] = "z3c4d5e6f7g8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE guild_reward_cards
            ADD COLUMN IF NOT EXISTS is_equipped BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS equip_slot VARCHAR(30),
            ADD COLUMN IF NOT EXISTS equipped_at TIMESTAMPTZ;
        """
    )
    op.execute(
        """
        ALTER TABLE guild_reward_cards
            DROP CONSTRAINT IF EXISTS chk_guild_reward_cards_equip_slot;
        """
    )
    op.execute(
        """
        ALTER TABLE guild_reward_cards
            ADD CONSTRAINT chk_guild_reward_cards_equip_slot
            CHECK (equip_slot IS NULL OR equip_slot IN ('profile_artifact'));
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_guild_reward_cards_equipped_slot
        ON guild_reward_cards (awarded_to_user_id, equip_slot)
        WHERE is_equipped = TRUE AND awarded_to_user_id IS NOT NULL AND equip_slot IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_guild_reward_cards_equipped_slot;")
    op.execute(
        """
        ALTER TABLE guild_reward_cards
            DROP CONSTRAINT IF EXISTS chk_guild_reward_cards_equip_slot;
        """
    )
    op.execute(
        """
        ALTER TABLE guild_reward_cards
            DROP COLUMN IF EXISTS equipped_at,
            DROP COLUMN IF EXISTS equip_slot,
            DROP COLUMN IF EXISTS is_equipped;
        """
    )