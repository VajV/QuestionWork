"""add freelancer onboarding and profile proof fields

Revision ID: r4t5u6v7w8x9
Revises: q7r8s9t0u1v2
Create Date: 2026-03-12 20:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "r4t5u6v7w8x9"
down_revision: Union[str, Sequence[str], None] = "q7r8s9t0u1v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS availability_status VARCHAR(32)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS portfolio_links JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS portfolio_summary VARCHAR(500)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_completeness_percent INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS profile_completeness_percent")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS onboarding_completed_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS onboarding_completed")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS portfolio_summary")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS portfolio_links")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS availability_status")