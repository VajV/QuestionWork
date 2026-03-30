"""merge_heads_before_idempotency

Revision ID: 8b805dc99a93
Revises: a1b2c3d4e5f6, r4t5u6v7w8x9
Create Date: 2026-03-13 22:10:50.878827

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b805dc99a93'
down_revision: Union[str, None] = ('a1b2c3d4e5f6', 'r4t5u6v7w8x9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
