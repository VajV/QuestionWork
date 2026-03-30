"""add withdrawal idempotency key

Revision ID: b2c3d4e5f6a7
Revises: 8b805dc99a93
Create Date: 2026-03-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = '8b805dc99a93'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'transactions',
        sa.Column('idempotency_key', sa.String(64), nullable=True)
    )
    # Partial unique index: only enforces uniqueness among withdrawal rows
    op.create_index(
        'uq_transactions_withdrawal_idempotency_key',
        'transactions',
        ['idempotency_key'],
        unique=True,
        postgresql_where=sa.text("type = 'withdrawal' AND idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index('uq_transactions_withdrawal_idempotency_key', table_name='transactions')
    op.drop_column('transactions', 'idempotency_key')
