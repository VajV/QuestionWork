"""Add review-related badges to catalogue.

Revision ID: l4m5n6o7p890
Revises: k3l4m5n6o789
Create Date: 2025-01-01 00:00:00.000000

New criteria_types:
  - reviews_given      (count of reviews the user wrote)
  - five_star_received (count of 5-star reviews received by the user)
"""

from alembic import op

revision = "l4m5n6o7p890"
down_revision = "k3l4m5n6o789"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Badge: First review written
    op.execute("""
        INSERT INTO badges (id, name, description, icon, criteria_type, criteria_value)
        VALUES (
            'badge_first_review',
            'Первый отзыв',
            'Оставьте свой первый отзыв',
            'note',
            'reviews_given',
            1
        )
        ON CONFLICT (id) DO NOTHING
    """)

    # Badge: 5 reviews written
    op.execute("""
        INSERT INTO badges (id, name, description, icon, criteria_type, criteria_value)
        VALUES (
            'badge_reviewer_5',
            'Опытный критик',
            'Оставьте 5 отзывов',
            'pen',
            'reviews_given',
            5
        )
        ON CONFLICT (id) DO NOTHING
    """)

    # Badge: 10 reviews written
    op.execute("""
        INSERT INTO badges (id, name, description, icon, criteria_type, criteria_value)
        VALUES (
            'badge_reviewer_10',
            'Летописец гильдии',
            'Оставьте 10 отзывов',
            'books',
            'reviews_given',
            10
        )
        ON CONFLICT (id) DO NOTHING
    """)

    # Badge: First 5-star received
    op.execute("""
        INSERT INTO badges (id, name, description, icon, criteria_type, criteria_value)
        VALUES (
            'badge_five_star_1',
            'Звезда гильдии',
            'Получите первый 5-звёздочный отзыв',
            'star',
            'five_star_received',
            1
        )
        ON CONFLICT (id) DO NOTHING
    """)

    # Badge: 5 five-star reviews received
    op.execute("""
        INSERT INTO badges (id, name, description, icon, criteria_type, criteria_value)
        VALUES (
            'badge_five_star_5',
            'Легенда гильдии',
            'Получите 5 пятизвёздочных отзывов',
            'superstar',
            'five_star_received',
            5
        )
        ON CONFLICT (id) DO NOTHING
    """)

    # Badge: 10 five-star reviews received
    op.execute("""
        INSERT INTO badges (id, name, description, icon, criteria_type, criteria_value)
        VALUES (
            'badge_five_star_10',
            'Мифический мастер',
            'Получите 10 пятизвёздочных отзывов',
            'spark',
            'five_star_received',
            10
        )
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM user_badges WHERE badge_id IN (
            'badge_first_review', 'badge_reviewer_5', 'badge_reviewer_10',
            'badge_five_star_1', 'badge_five_star_5', 'badge_five_star_10'
        )
    """)
    op.execute("""
        DELETE FROM badges WHERE id IN (
            'badge_first_review', 'badge_reviewer_5', 'badge_reviewer_10',
            'badge_five_star_1', 'badge_five_star_5', 'badge_five_star_10'
        )
    """)
