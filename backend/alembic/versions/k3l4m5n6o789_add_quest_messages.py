"""add_quest_messages — chat messages within quests

Revision ID: k3l4m5n6o789
Revises: j2k3l4m5n678
Create Date: 2026-03-05 14:00:00.000000

Changes:
- Create quest_messages table (id, quest_id, author_id, text, created_at)
- Indexes on quest_id, author_id
"""

from alembic import op

revision = "k3l4m5n6o789"
down_revision = "j2k3l4m5n678"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS quest_messages (
        id VARCHAR(50) PRIMARY KEY,
        quest_id VARCHAR(50) NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
        author_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        text TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_quest_messages_quest ON quest_messages (quest_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_quest_messages_author ON quest_messages (author_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS quest_messages")
