"""add_rpg_check_constraints

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-03-14 00:01:00.000000

Changes:
- CHECK constraint: users.review_count >= 0
- CHECK constraint: user_class_progress.class_level >= 1
- CHECK constraint: user_class_progress.perk_points_spent >= 0
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b2c3d4e5f6a8"
down_revision: Union[str, None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users "
        "ADD CONSTRAINT chk_users_review_count_non_negative "
        "CHECK (review_count >= 0)"
    )
    op.execute(
        "ALTER TABLE user_class_progress "
        "ADD CONSTRAINT chk_class_level_positive "
        "CHECK (class_level >= 1)"
    )
    op.execute(
        "ALTER TABLE user_class_progress "
        "ADD CONSTRAINT chk_perk_points_non_negative "
        "CHECK (perk_points_spent >= 0)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE user_class_progress "
        "DROP CONSTRAINT IF EXISTS chk_perk_points_non_negative"
    )
    op.execute(
        "ALTER TABLE user_class_progress "
        "DROP CONSTRAINT IF EXISTS chk_class_level_positive"
    )
    op.execute(
        "ALTER TABLE users "
        "DROP CONSTRAINT IF EXISTS chk_users_review_count_non_negative"
    )
