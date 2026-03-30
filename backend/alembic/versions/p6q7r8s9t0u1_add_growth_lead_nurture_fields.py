"""add_growth_lead_nurture_fields

Revision ID: p6q7r8s9t0u1
Revises: o1p2q3r4s5t6
Create Date: 2026-03-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, None] = "o1p2q3r4s5t6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE growth_leads ADD COLUMN IF NOT EXISTS ref TEXT NULL")
    op.execute("ALTER TABLE growth_leads ADD COLUMN IF NOT EXISTS landing_path TEXT NULL")
    op.execute("ALTER TABLE growth_leads ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'new'")
    op.execute("ALTER TABLE growth_leads ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMPTZ NULL")
    op.execute("ALTER TABLE growth_leads ADD COLUMN IF NOT EXISTS next_contact_at TIMESTAMPTZ NULL")
    op.execute("ALTER TABLE growth_leads ADD COLUMN IF NOT EXISTS nurture_stage TEXT NOT NULL DEFAULT 'intake'")
    op.execute("ALTER TABLE growth_leads ADD COLUMN IF NOT EXISTS converted_user_id TEXT NULL")
    op.execute(
        """
        UPDATE growth_leads
        SET next_contact_at = COALESCE(next_contact_at, created_at + INTERVAL '1 day'),
            status = COALESCE(NULLIF(status, ''), 'new'),
            nurture_stage = COALESCE(NULLIF(nurture_stage, ''), 'intake')
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_growth_leads_status_next_contact ON growth_leads (status, next_contact_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_growth_leads_status_next_contact")
    op.execute("ALTER TABLE growth_leads DROP COLUMN IF EXISTS converted_user_id")
    op.execute("ALTER TABLE growth_leads DROP COLUMN IF EXISTS nurture_stage")
    op.execute("ALTER TABLE growth_leads DROP COLUMN IF EXISTS next_contact_at")
    op.execute("ALTER TABLE growth_leads DROP COLUMN IF EXISTS last_contacted_at")
    op.execute("ALTER TABLE growth_leads DROP COLUMN IF EXISTS status")
    op.execute("ALTER TABLE growth_leads DROP COLUMN IF EXISTS landing_path")
    op.execute("ALTER TABLE growth_leads DROP COLUMN IF EXISTS ref")