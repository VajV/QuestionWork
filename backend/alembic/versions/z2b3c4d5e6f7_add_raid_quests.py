"""add_raid_quests

Revision ID: z2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-03-25 12:00:00.000000

Changes:
- Add raid_max_members and raid_current_members columns to quests table.
- Create raid_participants table for multi-member raid tracking.
- Add indexes for efficient raid participant lookups.
"""

from typing import Sequence, Union
from alembic import op

revision: str = "z2b3c4d5e6f7"
down_revision: Union[str, None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Raid columns on quests table (nullable for solo/training quests)
    op.execute("""
        ALTER TABLE quests
        ADD COLUMN IF NOT EXISTS raid_max_members INTEGER,
        ADD COLUMN IF NOT EXISTS raid_current_members INTEGER NOT NULL DEFAULT 0
    """)

    # Raid participants table
    op.execute("""
        CREATE TABLE IF NOT EXISTS raid_participants (
            id VARCHAR(36) PRIMARY KEY,
            quest_id VARCHAR(36) NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
            user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            username VARCHAR(100) NOT NULL,
            role_slot VARCHAR(30) NOT NULL DEFAULT 'any',
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (quest_id, user_id)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_raid_participants_quest_id
        ON raid_participants (quest_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_raid_participants_user_id
        ON raid_participants (user_id)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_raid_participants_user_id")
    op.execute("DROP INDEX IF EXISTS idx_raid_participants_quest_id")
    op.execute("DROP TABLE IF EXISTS raid_participants")
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS raid_current_members")
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS raid_max_members")
