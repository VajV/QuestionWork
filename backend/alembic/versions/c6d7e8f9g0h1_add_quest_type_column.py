"""add_quest_type_column

Revision ID: c6d7e8f9g0h1
Revises: b4c5d6e7f8g9
Create Date: 2026-03-24 12:00:00.000000

Changes:
- Add quest_type VARCHAR(20) column to quests table (default 'standard').
- Index on quest_type for filtered listing of training quests.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6d7e8f9g0h1"
down_revision: Union[str, None] = "b4c5d6e7f8g9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE quests ADD COLUMN IF NOT EXISTS quest_type VARCHAR(20) NOT NULL DEFAULT 'standard'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_quests_quest_type ON quests (quest_type)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_quests_quest_type")
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS quest_type")
