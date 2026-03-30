"""template_budget_numeric — change quest_templates.budget to NUMERIC(15,2)

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-03-10 12:00:00.000000

Changes:
- ALTER quest_templates.budget from DOUBLE PRECISION → NUMERIC(15,2)
  to match the rest of the financial columns (quests.budget, wallets.balance, etc.)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "x9y0z1a2b3c4"
down_revision: Union[str, Sequence[str]] = "w8x9y0z1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "quest_templates",
        "budget",
        existing_type=sa.Float(),
        type_=sa.Numeric(15, 2),
        existing_nullable=False,
        postgresql_using="budget::numeric(15,2)",
    )


def downgrade() -> None:
    op.alter_column(
        "quest_templates",
        "budget",
        existing_type=sa.Numeric(15, 2),
        type_=sa.Float(),
        existing_nullable=False,
    )