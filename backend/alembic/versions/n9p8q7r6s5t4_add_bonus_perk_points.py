"""Add bonus perk points for admin class rewards.

Revision ID: n9p8q7r6s5t4
Revises: f5678901abcd
Create Date: 2026-03-06
"""

from alembic import op


revision = "n9p8q7r6s5t4"
down_revision = "n6o7p8q9r012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE user_class_progress
        ADD COLUMN IF NOT EXISTS bonus_perk_points INTEGER NOT NULL DEFAULT 0
    """)


def downgrade():
    op.execute("ALTER TABLE user_class_progress DROP COLUMN IF EXISTS bonus_perk_points")