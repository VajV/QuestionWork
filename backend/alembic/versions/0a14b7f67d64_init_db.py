"""init_db

Revision ID: 0a14b7f67d64
Revises:
Create Date: 2026-03-01 18:56:32.369725

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0a14b7f67d64"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE users (
        id VARCHAR(50) PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(255) UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(20) NOT NULL DEFAULT 'freelancer',
        level INTEGER NOT NULL DEFAULT 1,
        grade VARCHAR(20) NOT NULL DEFAULT 'novice',
        xp INTEGER NOT NULL DEFAULT 0,
        xp_to_next INTEGER NOT NULL DEFAULT 100,
        stats_int INTEGER NOT NULL DEFAULT 10,
        stats_dex INTEGER NOT NULL DEFAULT 10,
        stats_cha INTEGER NOT NULL DEFAULT 10,
        badges JSONB DEFAULT '[]',
        bio VARCHAR(500),
        skills JSONB DEFAULT '[]',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """)

    op.execute("""
    CREATE TABLE quests (
        id VARCHAR(50) PRIMARY KEY,
        client_id VARCHAR(50) REFERENCES users(id),
        client_username VARCHAR(50),
        title VARCHAR(200) NOT NULL,
        description TEXT NOT NULL,
        required_grade VARCHAR(20) NOT NULL DEFAULT 'novice',
        skills JSONB DEFAULT '[]',
        budget NUMERIC(10, 2) NOT NULL,
        currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
        xp_reward INTEGER NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'open',
        assigned_to VARCHAR(50) REFERENCES users(id),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP WITH TIME ZONE
    );
    """)

    op.execute("""
    CREATE TABLE applications (
        id VARCHAR(50) PRIMARY KEY,
        quest_id VARCHAR(50) NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
        freelancer_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        freelancer_username VARCHAR(50) NOT NULL,
        freelancer_grade VARCHAR(20) NOT NULL,
        cover_letter TEXT,
        proposed_price NUMERIC(10, 2),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """)

    op.execute("""
    CREATE TABLE transactions (
        id VARCHAR(50) PRIMARY KEY,
        user_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        quest_id VARCHAR(50) REFERENCES quests(id) ON DELETE SET NULL,
        amount NUMERIC(10, 2) NOT NULL,
        currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
        type VARCHAR(20) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """)

    import bcrypt
    import os
    import secrets

    # Seed passwords from environment variables; generate random if not set (never use weak defaults).
    _default_freelancer_pwd = os.environ.get("SEED_FREELANCER_PASSWORD") or secrets.token_urlsafe(24)
    _default_client_pwd = os.environ.get("SEED_CLIENT_PASSWORD") or secrets.token_urlsafe(24)

    pwd_freelancer = bcrypt.hashpw(_default_freelancer_pwd.encode(), bcrypt.gensalt()).decode("utf-8")
    pwd_client = bcrypt.hashpw(_default_client_pwd.encode(), bcrypt.gensalt()).decode("utf-8")

    # NOTE: Seed users are for development/testing only.
    # Skipped when APP_ENV=production.
    _app_env = os.environ.get("APP_ENV", "development").lower()
    if _app_env not in ("production", "prod"):
        op.execute(
            sa.text("""
        INSERT INTO users (id, username, email, password_hash, role, level, grade, xp, xp_to_next, stats_int, stats_dex, stats_cha, badges, bio, skills, created_at, updated_at)
        VALUES
        ('user_123456', 'novice_dev', 'novice@example.com', :pwd_freelancer, 'freelancer', 1, 'novice', 0, 100, 10, 10, 10, '[]', NULL, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
        ('user_client_001', 'client_user', 'client@example.com', :pwd_client, 'client', 1, 'novice', 0, 100, 10, 10, 10, '[]', NULL, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT DO NOTHING;
        """).bindparams(pwd_freelancer=pwd_freelancer, pwd_client=pwd_client)
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS transactions;")
    op.execute("DROP TABLE IF EXISTS applications;")
    op.execute("DROP TABLE IF EXISTS quests;")
    op.execute("DROP TABLE IF EXISTS users;")
