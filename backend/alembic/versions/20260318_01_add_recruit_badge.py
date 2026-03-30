"""add recruit badge for onboarding

Revision ID: 20260318_01
Revises: 20260317_01
Create Date: 2026-03-18 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260318_01"
down_revision = "20260317_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO badges (id, name, description, icon, criteria_type, criteria_value)
        VALUES (
            'badge_recruit',
            'Новобранец',
            'Завершил онбординг и готов к работе',
            '/icons/badges/recruit.svg',
            'registration',
            1
        )
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM badges WHERE id = 'badge_recruit'")
