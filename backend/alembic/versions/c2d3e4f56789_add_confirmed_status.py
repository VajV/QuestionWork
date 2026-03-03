"""add_confirmed_quest_status

Revision ID: c2d3e4f56789
Revises: b1c2d3e4f567
Create Date: 2026-03-03 12:00:00.000000

"""

from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f56789"
down_revision: Union[str, None] = "b1c2d3e4f567"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add a CHECK constraint to enforce valid quest status values,
    # including the new 'confirmed' status.
    op.execute("""
    ALTER TABLE quests
    ADD CONSTRAINT chk_quest_status
    CHECK (status IN ('open', 'in_progress', 'completed', 'confirmed', 'cancelled'));
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE quests DROP CONSTRAINT IF EXISTS chk_quest_status;")
