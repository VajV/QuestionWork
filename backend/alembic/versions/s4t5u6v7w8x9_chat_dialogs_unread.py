"""chat_dialogs_unread

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-03-07 15:00:00.000000

Add read receipts and system-message support for quest chat.
"""

from alembic import op

revision = "s4t5u6v7w8x9"
down_revision = "r3s4t5u6v7w8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE quest_messages ALTER COLUMN author_id DROP NOT NULL;"
    )
    op.execute(
        "ALTER TABLE quest_messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(20) NOT NULL DEFAULT 'user';"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS quest_message_reads (
            quest_id VARCHAR(50) NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
            user_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            last_read_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (quest_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_quest_message_reads_user ON quest_message_reads (user_id, last_read_at);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS quest_message_reads")
    op.execute("ALTER TABLE quest_messages DROP COLUMN IF EXISTS message_type;")
    op.execute("DELETE FROM quest_messages WHERE author_id IS NULL;")
    op.execute(
        "ALTER TABLE quest_messages ALTER COLUMN author_id SET NOT NULL;"
    )
