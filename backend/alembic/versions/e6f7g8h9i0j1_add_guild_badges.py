"""add_guild_badges

Revision ID: e6f7g8h9i0j1
Revises: d5e6f7g8h9i0
Create Date: 2026-03-11 19:40:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e6f7g8h9i0j1"
down_revision: Union[str, None] = "d5e6f7g8h9i0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_badges (
            id VARCHAR(50) PRIMARY KEY,
            guild_id VARCHAR(50) NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
            badge_code VARCHAR(80) NOT NULL,
            name VARCHAR(80) NOT NULL,
            slug VARCHAR(80) NOT NULL,
            accent VARCHAR(20) NOT NULL,
            season_code VARCHAR(40),
            family VARCHAR(30),
            awarded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_guild_badges_guild_badge_code UNIQUE (guild_id, badge_code)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_guild_badges_guild_awarded ON guild_badges (guild_id, awarded_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_guild_badges_slug ON guild_badges (slug);")
    op.execute(
        """
        INSERT INTO guild_badges (
            id,
            guild_id,
            badge_code,
            name,
            slug,
            accent,
            season_code,
            family,
            awarded_at
        )
        SELECT
            CONCAT('gbadge_', SUBSTRING(MD5(gsr.guild_id || ':' || gsr.season_code || ':' || gsr.family) FROM 1 FOR 12)) AS id,
            gsr.guild_id,
            CONCAT(gsr.season_code, ':', gsr.family) AS badge_code,
            gsr.badge_name,
            LOWER(TRIM(BOTH '-' FROM REGEXP_REPLACE(gsr.badge_name, '[^a-zA-Z0-9]+', '-', 'g'))) AS slug,
            gsr.accent,
            gsr.season_code,
            gsr.family,
            gsr.claimed_at
        FROM guild_seasonal_rewards gsr
        ON CONFLICT (guild_id, badge_code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_guild_badges_slug;")
    op.execute("DROP INDEX IF EXISTS idx_guild_badges_guild_awarded;")
    op.execute("DROP TABLE IF EXISTS guild_badges;")