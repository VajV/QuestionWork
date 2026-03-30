"""Add disputes table for dispute resolution system.

Adds:
  - 'disputed' value to quest_status_enum
  - disputes table (quest_id, initiator_id, respondent_id, reason, status, etc.)
  - Partial indexes for pending auto-escalation and active dispute uniqueness

Revision ID: 20260316_03
Revises: 20260315_02
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260316_03"
down_revision: Union[str, None] = "20260315_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'disputed' to quest_status_enum (IF NOT EXISTS prevents re-run errors)
    op.execute("ALTER TYPE quest_status_enum ADD VALUE IF NOT EXISTS 'disputed'")

    op.execute("""
    CREATE TABLE disputes (
        id               VARCHAR(50) PRIMARY KEY,
        quest_id         VARCHAR(50) NOT NULL
                             REFERENCES quests(id) ON DELETE RESTRICT,
        initiator_id     VARCHAR(50) NOT NULL
                             REFERENCES users(id) ON DELETE RESTRICT,
        respondent_id    VARCHAR(50) NOT NULL
                             REFERENCES users(id) ON DELETE RESTRICT,
        reason           TEXT NOT NULL,
        response_text    TEXT,
        status           VARCHAR(30) NOT NULL DEFAULT 'open',
        resolution_type  VARCHAR(20),
        partial_percent  NUMERIC(5, 2),
        resolution_note  TEXT,
        moderator_id     VARCHAR(50) REFERENCES users(id) ON DELETE SET NULL,
        auto_escalate_at TIMESTAMPTZ NOT NULL,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        responded_at     TIMESTAMPTZ,
        escalated_at     TIMESTAMPTZ,
        resolved_at      TIMESTAMPTZ,
        CONSTRAINT chk_disputes_partial_percent
            CHECK (partial_percent IS NULL OR (partial_percent >= 1 AND partial_percent <= 99)),
        CONSTRAINT chk_disputes_resolution_type
            CHECK (resolution_type IS NULL OR resolution_type IN ('refund', 'partial', 'freelancer')),
        CONSTRAINT chk_disputes_status
            CHECK (status IN ('open', 'responded', 'escalated', 'resolved', 'closed'))
    )
    """)

    op.execute("CREATE INDEX idx_disputes_quest_id  ON disputes(quest_id)")
    op.execute("CREATE INDEX idx_disputes_initiator  ON disputes(initiator_id)")
    op.execute("CREATE INDEX idx_disputes_respondent ON disputes(respondent_id)")
    op.execute("CREATE INDEX idx_disputes_status     ON disputes(status)")

    # Partial index: only active (non-terminal) disputes needing auto-escalation
    op.execute("""
    CREATE INDEX idx_disputes_auto_escalate
        ON disputes(auto_escalate_at)
        WHERE status IN ('open', 'responded')
    """)

    # Unique index: at most one active dispute per quest at a time
    op.execute("""
    CREATE UNIQUE INDEX idx_disputes_quest_active
        ON disputes(quest_id)
        WHERE status NOT IN ('resolved', 'closed')
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS disputes")
    # Note: removing an enum value in PostgreSQL requires recreating the type,
    # which is unsafe on live data. Skip enum downgrade.
