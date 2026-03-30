"""add unique partial index on email_outbox.dedupe_key

Revision ID: 20260315_01
Revises: 20260314_01
Create Date: 2026-03-15

P1-19 FIX: email_outbox.dedupe_key had no uniqueness constraint, allowing
duplicate emails to be queued with the same dedupe_key.  A unique partial
index (WHERE dedupe_key IS NOT NULL) prevents this while allowing NULLable
rows for non-idempotent sends.
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260315_01"
down_revision: Union[str, None] = "20260314_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_email_outbox_dedupe_key",
        "email_outbox",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("dedupe_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_email_outbox_dedupe_key", table_name="email_outbox")
