"""add_wallets_table

Revision ID: c3d4e5f6a789
Revises: b1c2d3e4f567
Create Date: 2026-03-02 15:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a789"
down_revision: Union[str, None] = "b1c2d3e4f567"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create wallets table
    op.execute("""
    CREATE TABLE wallets (
        id VARCHAR(50) PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
        balance NUMERIC(12, 2) NOT NULL DEFAULT 0,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_wallets_user_currency UNIQUE (user_id, currency),
        CONSTRAINT chk_wallets_balance_non_negative CHECK (balance >= 0)
    );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_wallets_user_id ON wallets (user_id);")

    # Populate initial wallets for existing users (balance = SUM of income transactions or 0)
    op.execute("""
    INSERT INTO wallets (id, user_id, currency, balance, version, created_at, updated_at)
    SELECT
        'wallet_' || SUBSTR(MD5(u.id || '_RUB'), 1, 12),
        u.id,
        'RUB',
        COALESCE(t_sum.total, 0),
        1,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    FROM users u
    LEFT JOIN (
        SELECT user_id, SUM(amount) AS total
        FROM transactions
        WHERE type = 'income' AND currency = 'RUB'
        GROUP BY user_id
    ) t_sum ON t_sum.user_id = u.id;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS wallets;")
