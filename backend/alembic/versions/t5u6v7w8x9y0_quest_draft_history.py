"""quest_draft_history

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
Create Date: 2026-03-07 16:00:00.000000

Add draft quest status and quest status history timeline.
"""

from alembic import op

revision = "t5u6v7w8x9y0"
down_revision = "s4t5u6v7w8x9"
branch_labels = None
depends_on = None

NEW_STATUSES = "'draft', 'open', 'assigned', 'in_progress', 'completed', 'revision_requested', 'confirmed', 'cancelled'"
OLD_STATUSES = "'open', 'assigned', 'in_progress', 'completed', 'revision_requested', 'confirmed', 'cancelled'"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS quest_status_history (
            id VARCHAR(50) PRIMARY KEY,
            quest_id VARCHAR(50) NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
            from_status VARCHAR(20) NULL,
            to_status VARCHAR(20) NOT NULL,
            changed_by VARCHAR(50) NULL REFERENCES users(id) ON DELETE SET NULL,
            note TEXT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_quest_status_history_quest ON quest_status_history (quest_id, created_at)")
    op.execute("ALTER TABLE quests DROP CONSTRAINT IF EXISTS chk_quest_status;")
    op.execute(
        f"""
        ALTER TABLE quests
        ADD CONSTRAINT chk_quest_status
        CHECK (status IN ({NEW_STATUSES}));
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE quests DROP CONSTRAINT IF EXISTS chk_quest_status;")
    op.execute(
        f"""
        ALTER TABLE quests
        ADD CONSTRAINT chk_quest_status
        CHECK (status IN ({OLD_STATUSES}));
        """
    )
    op.execute("DROP TABLE IF EXISTS quest_status_history")
