"""Add quest chains (legendary quest chain progression)

Revision ID: z3c4d5e6f7g8
Revises: z2b3c4d5e6f7
Create Date: 2026-03-25
"""
from alembic import op

revision = "z3c4d5e6f7g8"
down_revision = "z2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Quest chains table
    op.execute("""
        CREATE TABLE IF NOT EXISTS quest_chains (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            description TEXT NOT NULL,
            total_steps INTEGER NOT NULL DEFAULT 2,
            final_xp_bonus INTEGER NOT NULL DEFAULT 0,
            final_badge_id TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # Chain steps — maps quest_id to chain position
    op.execute("""
        CREATE TABLE IF NOT EXISTS chain_steps (
            id          TEXT PRIMARY KEY,
            chain_id    TEXT NOT NULL REFERENCES quest_chains(id) ON DELETE CASCADE,
            quest_id    TEXT NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
            step_order  INTEGER NOT NULL,
            UNIQUE (chain_id, step_order),
            UNIQUE (chain_id, quest_id)
        )
    """)

    # User chain progress
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_chain_progress (
            id              TEXT PRIMARY KEY,
            chain_id        TEXT NOT NULL REFERENCES quest_chains(id) ON DELETE CASCADE,
            user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            current_step    INTEGER NOT NULL DEFAULT 0,
            status          TEXT NOT NULL DEFAULT 'not_started',
            started_at      TIMESTAMPTZ,
            completed_at    TIMESTAMPTZ,
            UNIQUE (chain_id, user_id)
        )
    """)

    # Indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_chain_steps_chain_id ON chain_steps(chain_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chain_steps_quest_id ON chain_steps(quest_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_chain_progress_user_id ON user_chain_progress(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_chain_progress_chain_id ON user_chain_progress(chain_id)")

    # Add chain metadata columns to quests
    op.execute("ALTER TABLE quests ADD COLUMN IF NOT EXISTS chain_id TEXT")
    op.execute("ALTER TABLE quests ADD COLUMN IF NOT EXISTS chain_step_order INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS chain_step_order")
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS chain_id")
    op.execute("DROP TABLE IF EXISTS user_chain_progress")
    op.execute("DROP TABLE IF EXISTS chain_steps")
    op.execute("DROP TABLE IF EXISTS quest_chains")
