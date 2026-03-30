"""week4_badges_notifications

Revision ID: e6f7a8b9c012
Revises: d5e6f7a8b901
Create Date: 2026-03-02 22:00:00.000000

Changes:
- badges catalogue table (platform-defined)
- user_badges join table (many-to-many)
- notifications table (per-user event feed)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "e6f7a8b9c012"
down_revision: Union[str, None] = "d5e6f7a8b901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── badges catalogue ─────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE badges (
        id VARCHAR(50) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        description TEXT NOT NULL,
        icon VARCHAR(100) NOT NULL DEFAULT 'medal',
        criteria_type VARCHAR(50) NOT NULL,
        criteria_value INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ── user_badges (earned) ─────────────────────────────────────────────
    op.execute("""
    CREATE TABLE user_badges (
        id VARCHAR(50) PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        badge_id VARCHAR(50) NOT NULL REFERENCES badges(id) ON DELETE CASCADE,
        earned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_user_badge UNIQUE (user_id, badge_id)
    );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_user_badges_user ON user_badges (user_id);")

    # ── notifications ────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE notifications (
        id VARCHAR(50) PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title VARCHAR(200) NOT NULL,
        message TEXT NOT NULL,
        event_type VARCHAR(50) NOT NULL DEFAULT 'general',
        is_read BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications (user_id, is_read, created_at DESC);")

    # ── seed badge catalogue ─────────────────────────────────────────────
    op.execute("""
    INSERT INTO badges (id, name, description, icon, criteria_type, criteria_value) VALUES
        ('badge_first_quest',   'First Quest',       'Complete your first quest',                    'sword',   'quests_completed',  1),
        ('badge_quest_5',       'Quest Veteran',     'Complete 5 quests',                            'shield',  'quests_completed',  5),
        ('badge_quest_10',      'Quest Master',      'Complete 10 quests',                           'trophy',  'quests_completed', 10),
        ('badge_quest_50',      'Quest Legend',      'Complete 50 quests',                           'crown',   'quests_completed', 50),
        ('badge_level_5',       'Rising Star',       'Reach level 5',                                'star',    'level',             5),
        ('badge_level_10',      'Experienced',       'Reach level 10',                               'spark',   'level',            10),
        ('badge_xp_1000',       'XP Hunter',         'Earn 1,000 XP total',                         'orb',     'xp',             1000),
        ('badge_xp_10000',      'XP Legend',         'Earn 10,000 XP total',                        'superstar','xp',            10000),
        ('badge_junior',        'Junior Freelancer', 'Reach Junior grade',                           'silver',  'grade_junior',      1),
        ('badge_middle',        'Middle Freelancer', 'Reach Middle grade',                           'gold',    'grade_middle',      1),
        ('badge_senior',        'Senior Freelancer', 'Reach Senior grade',                           'gem',     'grade_senior',      1),
        ('badge_earnings_1000', 'First Paycheck',    'Earn 1,000 RUB from quests',                  'coin',    'earnings',       1000),
        ('badge_earnings_10000','High Earner',       'Earn 10,000 RUB from quests',                 'bank',    'earnings',      10000)
    ON CONFLICT (id) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_notifications_user;")
    op.execute("DROP TABLE IF EXISTS notifications;")
    op.execute("DROP INDEX IF EXISTS idx_user_badges_user;")
    op.execute("DROP TABLE IF EXISTS user_badges;")
    op.execute("DROP TABLE IF EXISTS badges;")
