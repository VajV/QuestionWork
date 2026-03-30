"""add_missing_gin_indexes

Revision ID: a1b2c3d4e5f7
Revises: z1a2b3c4d5e6
Create Date: 2026-03-14 00:00:00.000000

Changes:
- GIN index on users.skills JSONB for talent search queries
- Composite index on quest_reviews(quest_id, created_at DESC) for review listings
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_skills_gin "
            "ON users USING GIN (skills)"
        )
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quest_reviews_quest_id "
            "ON quest_reviews (quest_id, created_at DESC)"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_quest_reviews_quest_id")
    op.execute("DROP INDEX IF EXISTS idx_users_skills_gin")
