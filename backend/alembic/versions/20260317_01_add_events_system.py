"""Add events system tables.

Creates:
  - events (seasonal events with XP multipliers, badge rewards)
  - event_participants (user participation and scores)
  - event_leaderboard (finalized rankings with XP bonuses)

Revision ID: 20260317_01
Revises: 20260316_03
Create Date: 2026-03-17
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260317_01"
down_revision: Union[str, None] = "20260316_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id               VARCHAR(50) PRIMARY KEY,
        title            VARCHAR(200) NOT NULL,
        description      TEXT NOT NULL,
        status           VARCHAR(20) NOT NULL DEFAULT 'draft',
        xp_multiplier    NUMERIC(4, 2) NOT NULL DEFAULT 1.0,
        badge_reward_id  VARCHAR(50) REFERENCES badges(id) ON DELETE SET NULL,
        max_participants INTEGER,
        created_by       VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        start_at         TIMESTAMPTZ NOT NULL,
        end_at           TIMESTAMPTZ NOT NULL,
        finalized_at     TIMESTAMPTZ,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT chk_events_status
            CHECK (status IN ('draft', 'active', 'ended', 'finalized')),
        CONSTRAINT chk_events_xp_multiplier
            CHECK (xp_multiplier >= 1.0 AND xp_multiplier <= 5.0),
        CONSTRAINT chk_events_dates
            CHECK (end_at > start_at),
        CONSTRAINT chk_events_duration
            CHECK (end_at - start_at <= INTERVAL '72 hours')
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS event_participants (
        id          VARCHAR(50) PRIMARY KEY,
        event_id    VARCHAR(50) NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        user_id     VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        score       INTEGER NOT NULL DEFAULT 0,
        joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT chk_event_participants_score CHECK (score >= 0),
        CONSTRAINT uq_event_participant UNIQUE (event_id, user_id)
    )
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS event_leaderboard (
        id              VARCHAR(50) PRIMARY KEY,
        event_id        VARCHAR(50) NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        user_id         VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        rank            INTEGER NOT NULL,
        score           INTEGER NOT NULL DEFAULT 0,
        xp_bonus        INTEGER NOT NULL DEFAULT 0,
        badge_awarded   BOOLEAN NOT NULL DEFAULT FALSE,
        computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT chk_event_leaderboard_rank CHECK (rank >= 1),
        CONSTRAINT chk_event_leaderboard_score CHECK (score >= 0),
        CONSTRAINT uq_event_leaderboard_entry UNIQUE (event_id, user_id)
    )
    """)

    # Indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_status ON events(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_start_at ON events(start_at) WHERE status IN ('draft', 'active')")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_end_at ON events(end_at) WHERE status = 'active'")
    op.execute("CREATE INDEX IF NOT EXISTS idx_event_participants_event ON event_participants(event_id, score DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_event_participants_user ON event_participants(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_event_leaderboard_event ON event_leaderboard(event_id, rank)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_event_leaderboard_user ON event_leaderboard(user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_event_leaderboard_user")
    op.execute("DROP INDEX IF EXISTS idx_event_leaderboard_event")
    op.execute("DROP INDEX IF EXISTS idx_event_participants_user")
    op.execute("DROP INDEX IF EXISTS idx_event_participants_event")
    op.execute("DROP INDEX IF EXISTS idx_events_end_at")
    op.execute("DROP INDEX IF EXISTS idx_events_start_at")
    op.execute("DROP INDEX IF EXISTS idx_events_status")
    op.execute("DROP TABLE IF EXISTS event_leaderboard")
    op.execute("DROP TABLE IF EXISTS event_participants")
    op.execute("DROP TABLE IF EXISTS events")
