"""add_performance_indexes

Revision ID: 20260328_01
Revises: 20260325_02
Create Date: 2026-03-28 19:47:49.355213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260328_01'
down_revision: Union[str, None] = '20260325_02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_badges_user_id "
            "ON user_badges (user_id)"
        )
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_background_jobs_status_scheduled "
            "ON background_jobs (status, scheduled_for)"
        )
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_guild_members_guild_id "
            "ON guild_members (guild_id)"
        )
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_disputes_status "
            "ON disputes (status)"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_disputes_status")
    op.execute("DROP INDEX IF EXISTS idx_guild_members_guild_id")
    op.execute("DROP INDEX IF EXISTS idx_background_jobs_status_scheduled")
    op.execute("DROP INDEX IF EXISTS idx_user_badges_user_id")
