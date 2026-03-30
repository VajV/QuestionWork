"""add_quest_revision_flow

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-03-07 01:10:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "r3s4t5u6v7w8"
down_revision: Union[str, None] = "q2r3s4t5u6v7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_STATUSES = "'open', 'assigned', 'in_progress', 'completed', 'confirmed', 'cancelled'"
NEW_STATUSES = "'open', 'assigned', 'in_progress', 'completed', 'revision_requested', 'confirmed', 'cancelled'"


def upgrade() -> None:
    op.execute("ALTER TABLE quests ADD COLUMN IF NOT EXISTS revision_reason TEXT;")
    op.execute("ALTER TABLE quests ADD COLUMN IF NOT EXISTS revision_requested_at TIMESTAMP WITH TIME ZONE;")
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
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS revision_requested_at;")
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS revision_reason;")