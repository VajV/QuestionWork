"""merge current alembic heads

Revision ID: 20260325_02
Revises: 20260319_01, c6d7e8f9g0h1, z4d5e6f7g8h9
Create Date: 2026-03-25 22:45:00.000000
"""

from typing import Sequence, Union


revision: str = "20260325_02"
down_revision: Union[str, Sequence[str], None] = (
    "20260319_01",
    "c6d7e8f9g0h1",
    "z4d5e6f7g8h9",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass