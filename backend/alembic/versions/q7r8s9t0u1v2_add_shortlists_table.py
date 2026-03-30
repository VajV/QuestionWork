"""add_shortlists_table

Revision ID: q7r8s9t0u1v2
Revises: c5d6e7f8g9h0, f7g8h9i0j1k2, p6q7r8s9t0u1
Create Date: 2026-03-12 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, Sequence[str]] = ("c5d6e7f8g9h0", "f7g8h9i0j1k2", "p6q7r8s9t0u1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS shortlists (
            id VARCHAR(50) PRIMARY KEY,
            client_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            freelancer_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (client_id, freelancer_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_shortlists_client ON shortlists (client_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS shortlists;")
