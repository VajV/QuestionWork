"""add_quest_delivery_fields

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-03-07 00:30:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "q2r3s4t5u6v7"
down_revision: Union[str, None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE quests ADD COLUMN IF NOT EXISTS delivery_note TEXT;")
    op.execute("ALTER TABLE quests ADD COLUMN IF NOT EXISTS delivery_url TEXT;")
    op.execute("ALTER TABLE quests ADD COLUMN IF NOT EXISTS delivery_submitted_at TIMESTAMP WITH TIME ZONE;")


def downgrade() -> None:
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS delivery_submitted_at;")
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS delivery_url;")
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS delivery_note;")
