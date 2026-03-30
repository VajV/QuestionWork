"""add_analytics_and_lifecycle_tables

Revision ID: a1b2c3d4e5f6
Revises: z1a2b3c4d5e6
Create Date: 2026-03-12 10:00:00.000000

Changes:
- Add analytics_events table for first-party funnel instrumentation
- Add lifecycle_campaigns table for CRM campaign definitions
- Add lifecycle_messages table for outbox-style lifecycle message delivery
- Add saved_searches table for saved filters and alert subscriptions
- Add email_outbox table for persistent async email delivery
- Add notification_preferences table for per-user notification opt-in/out
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── analytics_events ────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS analytics_events (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        event_name      VARCHAR(100) NOT NULL,
        user_id         VARCHAR(64),
        session_id      VARCHAR(64),
        role            VARCHAR(20),
        source          VARCHAR(100),
        path            VARCHAR(500),
        properties_json JSONB NOT NULL DEFAULT '{}',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_analytics_events_event_name
        ON analytics_events (event_name);
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_analytics_events_user_id
        ON analytics_events (user_id)
        WHERE user_id IS NOT NULL;
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at
        ON analytics_events (created_at DESC);
    """)

    # ── lifecycle_campaigns ─────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS lifecycle_campaigns (
        id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        campaign_key VARCHAR(100) NOT NULL UNIQUE,
        name         VARCHAR(200) NOT NULL,
        description  TEXT,
        is_active    BOOLEAN NOT NULL DEFAULT TRUE,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    # Seed canonical campaign keys
    op.execute("""
    INSERT INTO lifecycle_campaigns (campaign_key, name, description) VALUES
        ('incomplete_profile',    'Incomplete Profile Nudge',   'Sent when a user has not completed their profile after registration.'),
        ('incomplete_quest_draft','Incomplete Quest Draft',      'Sent when a client created a quest draft but did not publish it.'),
        ('stale_shortlist',       'Stale Shortlist',             'Sent when a client has shortlisted talent but has not initiated contact.'),
        ('unreviewed_completion', 'Unreviewed Completion Nudge', 'Sent when a quest is completed but the client has not left a review.'),
        ('dormant_client',        'Dormant Client Reactivation', 'Sent at 7/14/30 days of client inactivity after successful completion.'),
        ('lead_no_register',      'Lead Without Registration',   'Sent to captured leads that did not proceed to registration.'),
        ('lead_no_quest',         'Registered But No Quest',     'Sent to clients who registered but have not posted a quest.')
    ON CONFLICT (campaign_key) DO NOTHING;
    """)

    # ── lifecycle_messages ──────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS lifecycle_messages (
        id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id          VARCHAR(64) NOT NULL,
        campaign_key     VARCHAR(100) NOT NULL,
        trigger_data     JSONB NOT NULL DEFAULT '{}',
        status           VARCHAR(20) NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending','sent','failed','suppressed')),
        send_after       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        sent_at          TIMESTAMPTZ,
        error_message    TEXT,
        idempotency_key  VARCHAR(200) NOT NULL UNIQUE,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_lifecycle_messages_status_send_after
        ON lifecycle_messages (status, send_after)
        WHERE status = 'pending';
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_lifecycle_messages_user_campaign
        ON lifecycle_messages (user_id, campaign_key);
    """)

    # ── saved_searches ──────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS saved_searches (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id         VARCHAR(64) NOT NULL,
        name            VARCHAR(200),
        search_type     VARCHAR(20) NOT NULL CHECK (search_type IN ('talent', 'quest')),
        filters_json    JSONB NOT NULL DEFAULT '{}',
        alert_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
        last_alerted_at TIMESTAMPTZ,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_saved_searches_user_id
        ON saved_searches (user_id);
    """)

    # ── email_outbox ─────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS email_outbox (
        id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id          VARCHAR(64),
        email_address    VARCHAR(255) NOT NULL,
        template_key     VARCHAR(100) NOT NULL,
        template_params  JSONB NOT NULL DEFAULT '{}',
        status           VARCHAR(20) NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending','sent','failed')),
        send_after       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        sent_at          TIMESTAMPTZ,
        attempt_count    INT NOT NULL DEFAULT 0,
        error_message    TEXT,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_email_outbox_status_send_after
        ON email_outbox (status, send_after)
        WHERE status = 'pending';
    """)

    # ── notification_preferences ─────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS notification_preferences (
        id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id               VARCHAR(64) NOT NULL UNIQUE,
        transactional_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        growth_enabled        BOOLEAN NOT NULL DEFAULT TRUE,
        digest_enabled        BOOLEAN NOT NULL DEFAULT TRUE,
        created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notification_preferences;")
    op.execute("DROP TABLE IF EXISTS email_outbox;")
    op.execute("DROP TABLE IF EXISTS saved_searches;")
    op.execute("DROP TABLE IF EXISTS lifecycle_messages;")
    op.execute("DROP TABLE IF EXISTS lifecycle_campaigns;")
    op.execute("DROP TABLE IF EXISTS analytics_events;")
