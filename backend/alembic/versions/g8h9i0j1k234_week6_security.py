"""week6_security

Revision ID: g8h9i0j1k234
Revises: f7a8b9c0d123
Create Date: 2026-03-02 12:00:00.000000

Changes:
- Add totp_secret column to users for optional admin 2FA (TOTP/RFC 6238)
- Add backup_jobs table to track nightly dump runs
- Add index on transactions.status for faster pending-withdrawal queries
"""

from typing import Sequence, Union
from alembic import op

revision: str = "g8h9i0j1k234"
down_revision: Union[str, None] = "f7a8b9c0d123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── TOTP secret per user (NULL = TOTP not configured) ────────────────
    op.execute("""
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64) DEFAULT NULL;
    """)

    # ── backup_jobs: lightweight audit of DB dump execution ──────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS backup_jobs (
        id          VARCHAR(50)  PRIMARY KEY,
        started_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP WITH TIME ZONE,
        status      VARCHAR(20)  NOT NULL DEFAULT 'running',  -- running|ok|error
        size_bytes  BIGINT,
        path        TEXT,
        error       TEXT
    );
    """)

    # ── Partial index on transactions for pending withdrawals ─────────────
    # Speeds up the auto-processor's SELECT on every cron invocation.
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_txn_pending_withdrawal
    ON transactions (created_at ASC)
    WHERE status = 'pending' AND type = 'withdrawal';
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_txn_pending_withdrawal;")
    op.execute("DROP TABLE IF EXISTS backup_jobs;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS totp_secret;")
