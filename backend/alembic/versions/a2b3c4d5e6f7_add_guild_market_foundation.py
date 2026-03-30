"""add_guild_market_foundation

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-03-11 11:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guilds (
            id VARCHAR(50) PRIMARY KEY,
            owner_id VARCHAR(50) REFERENCES users(id) ON DELETE SET NULL,
            name VARCHAR(80) NOT NULL UNIQUE,
            slug VARCHAR(80) NOT NULL UNIQUE,
            description VARCHAR(500),
            emblem VARCHAR(24) NOT NULL DEFAULT 'ember',
            is_public BOOLEAN NOT NULL DEFAULT TRUE,
            member_limit INTEGER NOT NULL DEFAULT 20,
            treasury_balance NUMERIC(12, 2) NOT NULL DEFAULT 0,
            guild_tokens INTEGER NOT NULL DEFAULT 0,
            rating INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_guild_member_limit CHECK (member_limit >= 2 AND member_limit <= 20),
            CONSTRAINT chk_guild_tokens_non_negative CHECK (guild_tokens >= 0),
            CONSTRAINT chk_guild_rating_non_negative CHECK (rating >= 0),
            CONSTRAINT chk_guild_treasury_non_negative CHECK (treasury_balance >= 0)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_members (
            id VARCHAR(50) PRIMARY KEY,
            guild_id VARCHAR(50) NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
            user_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL DEFAULT 'member',
            contribution INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_guild_member_role CHECK (role IN ('leader', 'officer', 'member')),
            CONSTRAINT chk_guild_member_status CHECK (status IN ('active', 'left', 'removed')),
            CONSTRAINT chk_guild_contribution_non_negative CHECK (contribution >= 0),
            CONSTRAINT uq_guild_member_pair UNIQUE (guild_id, user_id)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_guilds_rating ON guilds (rating DESC, created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_guild_members_guild ON guild_members (guild_id, status, joined_at);")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_guild_members_active_user ON guild_members (user_id) WHERE status = 'active';")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_guild_members_active_user;")
    op.execute("DROP INDEX IF EXISTS idx_guild_members_guild;")
    op.execute("DROP INDEX IF EXISTS idx_guilds_rating;")
    op.execute("DROP TABLE IF EXISTS guild_members;")
    op.execute("DROP TABLE IF EXISTS guilds;")
