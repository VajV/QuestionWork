"""audit_v3_constraints — missing CHECK constraints and users.created_at index

Revision ID: c5d6e7f8g9h0
Revises: a2b3c4d5e6f7
Create Date: 2026-03-12

Addresses:
- P2-04: stats_int / stats_dex / stats_cha must be >= 0
- P2-10: avg_rating range 0-5
- P2-06: index on users.created_at for ORDER BY
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c5d6e7f8g9h0"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # P2-04: RPG stat columns must be non-negative
    # (stat_points already covered by i1j2k3l4m567)
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT chk_users_stats_non_negative "
        "CHECK (stats_int >= 0 AND stats_dex >= 0 AND stats_cha >= 0)"
    )

    # P2-10: avg_rating must be 0-5 (nullable)
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT chk_users_avg_rating_range "
        "CHECK (avg_rating IS NULL OR (avg_rating >= 0 AND avg_rating <= 5))"
    )

    # P2-06: index on users.created_at for ORDER BY created_at DESC
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_created_at "
            "ON users (created_at DESC)"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_created_at")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_avg_rating_range")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_stats_non_negative")
