"""merge alembic heads after runtime and market changes

Revision ID: 20260412_01
Revises: 20260328_01, z5e6f7g8h9i0
Create Date: 2026-04-12 12:20:00.000000
"""

from typing import Sequence, Union


revision: str = "20260412_01"
down_revision: Union[str, Sequence[str], None] = (
    "20260328_01",
    "z5e6f7g8h9i0",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass