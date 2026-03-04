"""add class system tables

Revision ID: e4f5678901ab
Revises: d3e4f5678901
Create Date: 2026-03-04 11:00:00.000000

"""

from typing import Sequence, Union
from alembic import op

revision: str = "e4f5678901ab"
down_revision: Union[str, None] = "d3e4f5678901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New columns on users ──────────────────────
    op.execute("""
    ALTER TABLE users
    ADD COLUMN character_class VARCHAR(30),
    ADD COLUMN class_selected_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN class_trial_expires_at TIMESTAMP WITH TIME ZONE;
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_users_character_class ON users (character_class) WHERE character_class IS NOT NULL;")

    # ── Class progression table ───────────────────
    op.execute("""
    CREATE TABLE user_class_progress (
        user_id           VARCHAR(50) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        class_id          VARCHAR(30) NOT NULL,
        class_xp          INTEGER NOT NULL DEFAULT 0,
        class_level       INTEGER NOT NULL DEFAULT 1,
        quests_completed   INTEGER NOT NULL DEFAULT 0,
        consecutive_quests INTEGER NOT NULL DEFAULT 0,
        last_quest_at     TIMESTAMP WITH TIME ZONE,
        burnout_until     TIMESTAMP WITH TIME ZONE,
        updated_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_ucp_class_id ON user_class_progress (class_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_class_progress;")
    op.execute("DROP INDEX IF EXISTS idx_users_character_class;")
    op.execute("""
    ALTER TABLE users
    DROP COLUMN IF EXISTS class_trial_expires_at,
    DROP COLUMN IF EXISTS class_selected_at,
    DROP COLUMN IF EXISTS character_class;
    """)
