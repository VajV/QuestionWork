"""admin_god_mode — ban columns on users

Revision ID: h9i0j1k2l345
Revises: g8h9i0j1k234
Create Date: 2026-03-04 12:00:00.000000

Changes:
- Add is_banned BOOLEAN DEFAULT FALSE to users
- Add banned_reason VARCHAR(500) to users
- Add banned_at TIMESTAMPTZ to users
- Add index on users.is_banned for quick filtering
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "h9i0j1k2l345"
down_revision: Union[str, Sequence[str]] = ("g8h9i0j1k234", "f5678901abcd")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_banned", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("users", sa.Column("banned_reason", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_is_banned", "users", ["is_banned"])


def downgrade() -> None:
    op.drop_index("ix_users_is_banned", table_name="users")
    op.drop_column("users", "banned_at")
    op.drop_column("users", "banned_reason")
    op.drop_column("users", "is_banned")
