"""audit_preserve_and_revision_count — P0 D-04 + P1 Q-04

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-03-09

Changes:
- D-04: Make admin_logs.target_id nullable + transactions.user_id nullable +
         change transactions FK from ON DELETE CASCADE to ON DELETE SET NULL
         (preserves financial + audit records when user is deleted).
- Q-04: Add revision_count column to quests for revision loop limit.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "v7w8x9y0z1a2"
down_revision: Union[str, None] = "u6v7w8x9y0z1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── D-04: Preserve audit trail on user deletion ───────────────────────

    # 1. Make admin_logs.target_id nullable so we can SET NULL on user delete
    op.alter_column("admin_logs", "target_id", nullable=True)

    # 2. Make transactions.user_id nullable + change FK to ON DELETE SET NULL
    op.alter_column("transactions", "user_id", nullable=True)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'transactions_user_id_fkey' AND table_name = 'transactions'
            ) THEN
                ALTER TABLE transactions DROP CONSTRAINT transactions_user_id_fkey;
            END IF;
            ALTER TABLE transactions ADD CONSTRAINT transactions_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
        END $$;
    """)

    # ── Q-04: Add revision_count column ───────────────────────────────────
    op.execute("ALTER TABLE quests ADD COLUMN IF NOT EXISTS revision_count INTEGER NOT NULL DEFAULT 0;")


def downgrade() -> None:
    # Revert revision_count
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS revision_count;")

    # Revert transactions FK back to CASCADE
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'transactions_user_id_fkey' AND table_name = 'transactions'
            ) THEN
                ALTER TABLE transactions DROP CONSTRAINT transactions_user_id_fkey;
            END IF;
            ALTER TABLE transactions ADD CONSTRAINT transactions_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        END $$;
    """)
    op.alter_column("transactions", "user_id", nullable=False)
    op.alter_column("admin_logs", "target_id", nullable=False)
