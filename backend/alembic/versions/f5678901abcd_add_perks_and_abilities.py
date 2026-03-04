"""Add perk tree and active abilities tables for class system Phase 2.

Revision ID: f5678901abcd
Revises: e4f5678901ab
Create Date: 2026-03-04
"""
from alembic import op

revision = "f5678901abcd"
down_revision = "e4f5678901ab"
branch_labels = None
depends_on = None


def upgrade():
    # ── user_perks: tracks which perks a user has unlocked ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_perks (
            id VARCHAR(50) PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            perk_id VARCHAR(60) NOT NULL,
            class_id VARCHAR(30) NOT NULL,
            unlocked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_perks_unique
        ON user_perks (user_id, perk_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_perks_user
        ON user_perks (user_id)
    """)

    # ── user_abilities: tracks active ability state (cooldowns, active status) ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_abilities (
            user_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            ability_id VARCHAR(60) NOT NULL,
            class_id VARCHAR(30) NOT NULL,
            last_activated_at TIMESTAMP WITH TIME ZONE,
            active_until TIMESTAMP WITH TIME ZONE,
            cooldown_until TIMESTAMP WITH TIME ZONE,
            times_used INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, ability_id)
        )
    """)

    # ── Add perk_points_spent to user_class_progress ──
    op.execute("""
        ALTER TABLE user_class_progress
        ADD COLUMN IF NOT EXISTS perk_points_spent INTEGER NOT NULL DEFAULT 0
    """)

    # ── Add rage_active_until to user_class_progress for quick checks ──
    op.execute("""
        ALTER TABLE user_class_progress
        ADD COLUMN IF NOT EXISTS rage_active_until TIMESTAMP WITH TIME ZONE
    """)


def downgrade():
    op.execute("ALTER TABLE user_class_progress DROP COLUMN IF EXISTS rage_active_until")
    op.execute("ALTER TABLE user_class_progress DROP COLUMN IF EXISTS perk_points_spent")
    op.execute("DROP TABLE IF EXISTS user_abilities")
    op.execute("DROP TABLE IF EXISTS user_perks")
