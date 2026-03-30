"""add_guild_activity_history

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2026-03-11 13:20:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b3c4d5e6f7g8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_activity (
            id VARCHAR(50) PRIMARY KEY,
            guild_id VARCHAR(50) NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
            user_id VARCHAR(50) REFERENCES users(id) ON DELETE SET NULL,
            quest_id VARCHAR(50) REFERENCES quests(id) ON DELETE SET NULL,
            event_type VARCHAR(40) NOT NULL,
            summary VARCHAR(255) NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            treasury_delta NUMERIC(12, 2) NOT NULL DEFAULT 0,
            guild_tokens_delta INTEGER NOT NULL DEFAULT 0,
            contribution_delta INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_guild_activity_event_type CHECK (
                event_type IN ('guild_created', 'member_joined', 'member_left', 'quest_confirmed')
            )
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_guild_activity_guild_created ON guild_activity (guild_id, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_guild_activity_user_created ON guild_activity (user_id, created_at DESC);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_guild_activity_user_created;")
    op.execute("DROP INDEX IF EXISTS idx_guild_activity_guild_created;")
    op.execute("DROP TABLE IF EXISTS guild_activity;")