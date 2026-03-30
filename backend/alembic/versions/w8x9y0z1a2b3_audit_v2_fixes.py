"""audit_v2_fixes — P2-1, P2-7, P1-3 database-level fixes

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-03-09

Changes:
- P2-1: Make admin_logs.admin_id nullable + add ON DELETE SET NULL FK.
- P2-7: Add partial index on quest_reviews for badge 5-star queries.
- P1-3: Alter users.avg_rating from DOUBLE PRECISION to NUMERIC(3,2).
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "w8x9y0z1a2b3"
down_revision: Union[str, None] = "v7w8x9y0z1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # P2-1: admin_logs.admin_id — make nullable and fix FK for admin deletion
    op.alter_column("admin_logs", "admin_id", nullable=True)
    # Drop existing FK if present, then re-create with ON DELETE SET NULL
    op.execute("ALTER TABLE admin_logs DROP CONSTRAINT IF EXISTS admin_logs_admin_id_fkey")
    op.create_foreign_key(
        "admin_logs_admin_id_fkey",
        "admin_logs", "users",
        ["admin_id"], ["id"],
        ondelete="SET NULL",
    )

    # P2-7: Partial index for badge 5-star rating queries
    op.create_index(
        "idx_quest_reviews_5star",
        "quest_reviews",
        ["reviewee_id"],
        postgresql_where=sa.text("rating = 5"),
    )

    # P1-3: Alter users.avg_rating from DOUBLE PRECISION to NUMERIC(3,2)
    op.alter_column(
        "users",
        "avg_rating",
        type_=sa.Numeric(precision=3, scale=2),
        existing_type=sa.Float(),
        existing_nullable=True,
        postgresql_using="avg_rating::NUMERIC(3,2)",
    )


def downgrade() -> None:
    # Reverse P1-3
    op.alter_column(
        "users",
        "avg_rating",
        type_=sa.Float(),
        existing_type=sa.Numeric(precision=3, scale=2),
        existing_nullable=True,
    )

    # Reverse P2-7
    op.drop_index("idx_quest_reviews_5star", table_name="quest_reviews")

    # Reverse P2-1
    op.drop_constraint("admin_logs_admin_id_fkey", "admin_logs", type_="foreignkey")
    op.create_foreign_key(
        "admin_logs_admin_id_fkey",
        "admin_logs", "users",
        ["admin_id"], ["id"],
    )
    op.alter_column("admin_logs", "admin_id", nullable=False)
