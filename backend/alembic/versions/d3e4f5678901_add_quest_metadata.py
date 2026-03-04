"""add quest metadata (is_urgent, deadline, required_portfolio)

Revision ID: d3e4f5678901
Revises: c2d3e4f56789
Create Date: 2026-03-04 10:00:00.000000

"""

from typing import Sequence, Union
from alembic import op

revision: str = "d3e4f5678901"
down_revision: Union[str, None] = "c2d3e4f56789"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE quests
    ADD COLUMN is_urgent BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN deadline TIMESTAMP WITH TIME ZONE,
    ADD COLUMN required_portfolio BOOLEAN NOT NULL DEFAULT FALSE;
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_quests_is_urgent ON quests (is_urgent) WHERE is_urgent = TRUE;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_quests_deadline ON quests (deadline) WHERE deadline IS NOT NULL;")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_quests_deadline;")
    op.execute("DROP INDEX IF EXISTS idx_quests_is_urgent;")
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS required_portfolio;")
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS deadline;")
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS is_urgent;")
