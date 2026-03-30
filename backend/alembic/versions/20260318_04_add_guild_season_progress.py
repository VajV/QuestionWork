"""add guild season progress

Revision ID: 20260318_04
Revises: 20260318_03
Create Date: 2026-03-18 01:10:00.000000

"""

from alembic import op


revision = "20260318_04"
down_revision = "20260318_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_season_progress (
            id VARCHAR(50) PRIMARY KEY,
            guild_id VARCHAR(50) NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
            season_code VARCHAR(16) NOT NULL,
            seasonal_xp INTEGER NOT NULL DEFAULT 0,
            current_tier VARCHAR(20) NOT NULL DEFAULT 'bronze',
            last_tier_change_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_guild_season_progress_pair UNIQUE (guild_id, season_code),
            CONSTRAINT chk_guild_season_progress_xp_non_negative CHECK (seasonal_xp >= 0),
            CONSTRAINT chk_guild_season_progress_tier CHECK (current_tier IN ('bronze', 'silver', 'gold', 'platinum'))
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_guild_season_progress_season_rank ON guild_season_progress (season_code, seasonal_xp DESC, updated_at ASC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_guild_season_progress_guild ON guild_season_progress (guild_id, season_code);"
    )

    op.execute("ALTER TABLE guild_activity DROP CONSTRAINT IF EXISTS chk_guild_activity_event_type")
    op.execute(
        """
        ALTER TABLE guild_activity
        ADD CONSTRAINT chk_guild_activity_event_type CHECK (
            event_type IN (
                'guild_created',
                'member_joined',
                'member_left',
                'quest_confirmed',
                'guild_xp_awarded',
                'guild_tier_promoted'
            )
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM guild_activity WHERE event_type IN ('guild_xp_awarded', 'guild_tier_promoted')"
    )
    op.execute("ALTER TABLE guild_activity DROP CONSTRAINT IF EXISTS chk_guild_activity_event_type")
    op.execute(
        """
        ALTER TABLE guild_activity
        ADD CONSTRAINT chk_guild_activity_event_type CHECK (
            event_type IN ('guild_created', 'member_joined', 'member_left', 'quest_confirmed')
        )
        """
    )
    op.execute("DROP INDEX IF EXISTS idx_guild_season_progress_guild")
    op.execute("DROP INDEX IF EXISTS idx_guild_season_progress_season_rank")
    op.execute("DROP TABLE IF EXISTS guild_season_progress")