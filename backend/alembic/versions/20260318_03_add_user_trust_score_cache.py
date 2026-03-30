"""add user trust score cache

Revision ID: 20260318_03
Revises: 20260318_02
Create Date: 2026-03-18 00:40:00.000000

"""

from alembic import op


revision = "20260318_03"
down_revision = "20260318_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS trust_score NUMERIC(5, 4)
        """
    )
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS trust_score_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS trust_score_updated_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        ALTER TABLE users
        DROP CONSTRAINT IF EXISTS chk_users_trust_score_range
        """
    )
    op.execute(
        """
        ALTER TABLE users
        ADD CONSTRAINT chk_users_trust_score_range
        CHECK (trust_score IS NULL OR (trust_score >= 0 AND trust_score <= 1))
        """
    )
    op.execute(
        """
        UPDATE users
        SET trust_score_breakdown = '{}'::jsonb
        WHERE trust_score_breakdown IS NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        DROP CONSTRAINT IF EXISTS chk_users_trust_score_range
        """
    )
    op.execute(
        """
        ALTER TABLE users
        DROP COLUMN IF EXISTS trust_score_updated_at
        """
    )
    op.execute(
        """
        ALTER TABLE users
        DROP COLUMN IF EXISTS trust_score_breakdown
        """
    )
    op.execute(
        """
        ALTER TABLE users
        DROP COLUMN IF EXISTS trust_score
        """
    )