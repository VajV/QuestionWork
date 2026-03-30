"""week3_economy_core

Revision ID: d5e6f7a8b901
Revises: c3d4e5f6a789
Create Date: 2026-03-02 20:00:00.000000

Changes:
- users: add stat_points column (unspent RPG stat points)
- transactions: add status column (completed | pending | failed)
- wallets: ensure platform wallet row exists
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b901"
down_revision: Union[str, None] = "c3d4e5f6a789"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users: stat_points ────────────────────────────────────────────────
    op.execute("""
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS stat_points INTEGER NOT NULL DEFAULT 0;
    """)

    # ── transactions: status ─────────────────────────────────────────────
    # Default to 'completed' so existing rows stay semantically correct.
    op.execute("""
    ALTER TABLE transactions
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'completed';
    """)

    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_transactions_status
        ON transactions (status)
        WHERE status != 'completed';
    """)

    # ── platform virtual user + wallet ───────────────────────────────────
    platform_id = settings.PLATFORM_USER_ID  # 'platform' by default

    op.execute(
        sa.text("""
    INSERT INTO users (
        id, username, email, password_hash, role, level, grade, xp, xp_to_next,
        stats_int, stats_dex, stats_cha, stat_points, badges, bio, skills,
        created_at, updated_at
    )
    VALUES (
        :platform_id, 'platform', NULL,
        '!disabled',
        'client', 1, 'novice', 0, 100, 10, 10, 10, 0,
        '[]', 'Platform virtual account', '[]',
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    )
    ON CONFLICT (id) DO NOTHING;
    """).bindparams(platform_id=platform_id)
    )

    # Create a RUB wallet for the platform
    op.execute(
        sa.text("""
    INSERT INTO wallets (id, user_id, currency, balance, version, created_at, updated_at)
    VALUES (
        'wallet_platform_rub',
        :platform_id,
        'RUB',
        0,
        1,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT (user_id, currency) DO NOTHING;
    """).bindparams(platform_id=platform_id)
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_transactions_status;")
    op.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS status;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS stat_points;")
    op.execute(
        sa.text("DELETE FROM wallets WHERE user_id = :pid").bindparams(pid=settings.PLATFORM_USER_ID)
    )
    op.execute(
        sa.text("DELETE FROM users WHERE id = :pid").bindparams(pid=settings.PLATFORM_USER_ID)
    )
