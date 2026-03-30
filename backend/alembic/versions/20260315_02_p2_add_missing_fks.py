"""P2-13: add missing FK constraints for analytics_events, saved_searches, notification_preferences

Revision ID: 20260315_02
Revises: 20260315_01
Create Date: 2026-03-15

These tables had user_id columns without foreign key constraints, meaning
orphaned rows could accumulate when users are deleted.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260315_02"
down_revision: Union[str, None] = "20260315_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # analytics_events.user_id is nullable, so ON DELETE SET NULL
    op.execute("""
    ALTER TABLE analytics_events
        ADD CONSTRAINT fk_analytics_events_user_id
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE SET NULL;
    """)

    # saved_searches.user_id is NOT NULL, cascade delete with user
    op.execute("""
    ALTER TABLE saved_searches
        ADD CONSTRAINT fk_saved_searches_user_id
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE;
    """)

    # notification_preferences.user_id is NOT NULL + UNIQUE, cascade
    op.execute("""
    ALTER TABLE notification_preferences
        ADD CONSTRAINT fk_notification_preferences_user_id
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE notification_preferences DROP CONSTRAINT IF EXISTS fk_notification_preferences_user_id;")
    op.execute("ALTER TABLE saved_searches DROP CONSTRAINT IF EXISTS fk_saved_searches_user_id;")
    op.execute("ALTER TABLE analytics_events DROP CONSTRAINT IF EXISTS fk_analytics_events_user_id;")
