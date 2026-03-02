"""week5_admin_ops

Revision ID: f7a8b9c0d123
Revises: e6f7a8b9c012
Create Date: 2026-03-02 10:00:00.000000

Changes:
- admin_logs table for audit trail of all admin actions
- indexes on admin_logs for efficient query by admin or by time
- 'admin' role is VARCHAR(20) so no ALTER TYPE needed; just documented here

Note: To create an initial admin user, set ADMIN_DEFAULT_PASSWORD in .env
and run: python scripts/seed_admin.py
"""

from typing import Sequence, Union
from alembic import op

revision: str = "f7a8b9c0d123"
down_revision: Union[str, None] = "e6f7a8b9c012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── admin_logs: immutable audit trail ────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS admin_logs (
        id          VARCHAR(50)  PRIMARY KEY,
        admin_id    VARCHAR(50)  NOT NULL REFERENCES users(id),
        action      VARCHAR(100) NOT NULL,
        target_type VARCHAR(50)  NOT NULL,
        target_id   VARCHAR(255) NOT NULL,
        old_value   JSONB,
        new_value   JSONB,
        ip_address  VARCHAR(45),
        created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_logs_admin_id "
        "ON admin_logs (admin_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_logs_created_at "
        "ON admin_logs (created_at DESC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_logs_target "
        "ON admin_logs (target_type, target_id);"
    )

    # ── partial index: fast lookup of pending withdrawals ────────────────
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_transactions_pending_withdrawal "
        "ON transactions (created_at DESC) "
        "WHERE type = 'withdrawal' AND status = 'pending';"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_transactions_pending_withdrawal;")
    op.execute("DROP INDEX IF EXISTS idx_admin_logs_target;")
    op.execute("DROP INDEX IF EXISTS idx_admin_logs_created_at;")
    op.execute("DROP INDEX IF EXISTS idx_admin_logs_admin_id;")
    op.execute("DROP TABLE IF EXISTS admin_logs;")
