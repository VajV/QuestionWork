"""add_assigned_quest_status

Revision ID: p1q2r3s4t5u6
Revises: n9p8q7r6s5t4
Create Date: 2026-03-07 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, None] = "n9p8q7r6s5t4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_STATUSES = "'open', 'in_progress', 'completed', 'confirmed', 'cancelled'"
NEW_STATUSES = "'open', 'assigned', 'in_progress', 'completed', 'confirmed', 'cancelled'"


def upgrade() -> None:
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
