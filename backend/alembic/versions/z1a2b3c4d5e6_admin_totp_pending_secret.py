"""admin_totp_pending_secret

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-03-10 18:00:00.000000

Changes:
- Add pending_totp_secret column to users for staged TOTP activation.
  Setup writes here; enable promotes to totp_secret after verification.
"""

from typing import Sequence, Union
from alembic import op

revision: str = "z1a2b3c4d5e6"
down_revision: Union[str, None] = "y0z1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS pending_totp_secret VARCHAR(64) DEFAULT NULL;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS pending_totp_secret;")
