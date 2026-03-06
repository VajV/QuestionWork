"""audit_fixes — C-01 email NOT NULL

Revision ID: n6o7p8q9r012
Revises: m5n6o7p8q901
Create Date: 2026-03-06

Fixes:
  C-01: Add NOT NULL constraint on users.email column.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "n6o7p8q9r012"
down_revision: Union[str, None] = "m5n6o7p8q901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # C-01: Ensure no NULLs exist, then add NOT NULL constraint
    op.execute("""
        UPDATE users SET email = username || '@placeholder.local'
        WHERE email IS NULL;
    """)
    op.execute("""
        ALTER TABLE users ALTER COLUMN email SET NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
    """)
