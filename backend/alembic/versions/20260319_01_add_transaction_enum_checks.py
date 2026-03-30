"""add transaction enum checks

Revision ID: 20260319_01
Revises: 20260318_04
Create Date: 2026-03-19 12:00:00.000000

"""

from alembic import op


revision = "20260319_01"
down_revision = "20260318_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS chk_transactions_type_allowed
        """
    )
    op.execute(
        """
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS chk_transactions_status_allowed
        """
    )

    op.execute(
        """
        ALTER TABLE transactions
        ADD CONSTRAINT chk_transactions_type_allowed
        CHECK (
            type IN (
                'income',
                'expense',
                'hold',
                'refund',
                'urgent_bonus_charge',
                'urgent_bonus',
                'commission',
                'withdrawal',
                'admin_adjust',
                'credit',
                'quest_payment',
                'release',
                'platform_fee',
                'deposit'
            )
        ) NOT VALID
        """
    )
    op.execute(
        """
        ALTER TABLE transactions VALIDATE CONSTRAINT chk_transactions_type_allowed
        """
    )

    op.execute(
        """
        ALTER TABLE transactions
        ADD CONSTRAINT chk_transactions_status_allowed
        CHECK (
            status IN (
                'pending',
                'completed',
                'rejected',
                'refunded',
                'held',
                'failed'
            )
        ) NOT VALID
        """
    )
    op.execute(
        """
        ALTER TABLE transactions VALIDATE CONSTRAINT chk_transactions_status_allowed
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS chk_transactions_status_allowed
        """
    )
    op.execute(
        """
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS chk_transactions_type_allowed
        """
    )
