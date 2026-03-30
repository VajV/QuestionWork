"""add_quest_skills_gin_index

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-03-10 13:30:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "y0z1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "x9y0z1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_quests_skills_gin ON quests USING GIN (skills);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_quests_skills_gin;")