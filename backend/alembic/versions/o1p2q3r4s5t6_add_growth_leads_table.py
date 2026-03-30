"""add_growth_leads_table

Revision ID: o1p2q3r4s5t6
Revises: n9p8q7r6s5t4
Create Date: 2026-03-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "o1p2q3r4s5t6"
down_revision: Union[str, None] = "n9p8q7r6s5t4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS growth_leads (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            company_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            use_case TEXT NOT NULL,
            budget_band TEXT NULL,
            message TEXT NULL,
            source TEXT NOT NULL,
            utm_source TEXT NULL,
            utm_medium TEXT NULL,
            utm_campaign TEXT NULL,
            utm_term TEXT NULL,
            utm_content TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_growth_leads_created_at ON growth_leads (created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_growth_leads_email ON growth_leads (email)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_growth_leads_email")
    op.execute("DROP INDEX IF EXISTS ix_growth_leads_created_at")
    op.execute("DROP TABLE IF EXISTS growth_leads")