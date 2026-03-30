"""add user avatar url

Revision ID: 20260318_02
Revises: 20260318_01
Create Date: 2026-03-18 00:10:00.000000

"""
from alembic import op


revision = "20260318_02"
down_revision = "20260318_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        DROP COLUMN IF EXISTS avatar_url
        """
    )