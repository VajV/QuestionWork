"""Add quest_templates table.

Revision ID: m5n6o7p8q901
Revises: l4m5n6o7p890
Create Date: 2025-01-01 00:00:00.000000

quest_templates stores reusable quest blueprints for clients.
"""

from alembic import op

revision = "m5n6o7p8q901"
down_revision = "l4m5n6o7p890"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS quest_templates (
            id              VARCHAR(50) PRIMARY KEY,
            owner_id        VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name            VARCHAR(200) NOT NULL,
            title           VARCHAR(200) NOT NULL,
            description     TEXT NOT NULL DEFAULT '',
            required_grade  VARCHAR(20) NOT NULL DEFAULT 'novice',
            skills          JSONB NOT NULL DEFAULT '[]'::jsonb,
            budget          DOUBLE PRECISION NOT NULL DEFAULT 0,
            currency        VARCHAR(10) NOT NULL DEFAULT 'RUB',
            is_urgent       BOOLEAN NOT NULL DEFAULT FALSE,
            required_portfolio BOOLEAN NOT NULL DEFAULT FALSE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_quest_templates_owner
        ON quest_templates (owner_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS quest_templates CASCADE")
