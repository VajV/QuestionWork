"""audit_final_fixes — H-03: fee snapshot, M-10: ENUM types, M-16: index

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-03-08

Fixes:
  H-03: Add platform_fee_percent column to quests — snapshot fee at creation.
  M-10: Create PostgreSQL ENUM types for status/role/grade columns.
  M-16: Add missing index on user_class_progress.user_id.
"""

from typing import Sequence, Union
from alembic import op

revision: str = "u6v7w8x9y0z1"
down_revision: Union[str, None] = "t5u6v7w8x9y0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── H-03: Snapshot platform fee on quest ──────────────────────────
    op.execute("""
        ALTER TABLE quests
        ADD COLUMN IF NOT EXISTS platform_fee_percent NUMERIC(5,2) DEFAULT NULL;
    """)

    # ── M-10: PostgreSQL ENUM types ───────────────────────────────────
    # Create ENUM types
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role_enum') THEN
                CREATE TYPE user_role_enum AS ENUM ('client', 'freelancer', 'admin');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'grade_enum') THEN
                CREATE TYPE grade_enum AS ENUM ('novice', 'junior', 'middle', 'senior');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'quest_status_enum') THEN
                CREATE TYPE quest_status_enum AS ENUM (
                    'draft', 'open', 'assigned', 'in_progress',
                    'completed', 'revision_requested', 'confirmed', 'cancelled'
                );
            END IF;
        END $$;
    """)

    # Normalize legacy stringified Enum values before casting to PostgreSQL ENUM.
    op.execute("""
        UPDATE users
        SET role = regexp_replace(role, '^UserRoleEnum\\.', '')
        WHERE role LIKE 'UserRoleEnum.%';
    """)
    op.execute("""
        UPDATE users
        SET grade = regexp_replace(grade, '^GradeEnum\\.', '')
        WHERE grade LIKE 'GradeEnum.%';
    """)
    op.execute("""
        UPDATE quests
        SET status = regexp_replace(status, '^QuestStatusEnum\\.', '')
        WHERE status LIKE 'QuestStatusEnum.%';
    """)
    op.execute("""
        UPDATE quests
        SET required_grade = regexp_replace(required_grade, '^GradeEnum\\.', '')
        WHERE required_grade LIKE 'GradeEnum.%';
    """)

    # Convert columns to use ENUM types
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT;")
    op.execute("ALTER TABLE users ALTER COLUMN grade DROP DEFAULT;")
    op.execute("ALTER TABLE quests ALTER COLUMN status DROP DEFAULT;")
    op.execute("ALTER TABLE quests ALTER COLUMN required_grade DROP DEFAULT;")

    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE user_role_enum USING role::user_role_enum;
    """)
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN grade TYPE grade_enum USING grade::grade_enum;
    """)
    op.execute("""
        ALTER TABLE quests DROP CONSTRAINT IF EXISTS chk_quest_status;
    """)
    op.execute("""
        ALTER TABLE quests
        ALTER COLUMN status TYPE quest_status_enum USING status::quest_status_enum;
    """)
    op.execute("""
        ALTER TABLE quests
        ALTER COLUMN required_grade TYPE grade_enum USING required_grade::grade_enum;
    """)

    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'freelancer'::user_role_enum;")
    op.execute("ALTER TABLE users ALTER COLUMN grade SET DEFAULT 'novice'::grade_enum;")
    op.execute("ALTER TABLE quests ALTER COLUMN status SET DEFAULT 'open'::quest_status_enum;")
    op.execute("ALTER TABLE quests ALTER COLUMN required_grade SET DEFAULT 'novice'::grade_enum;")

    # ── M-16: Missing index on user_class_progress.user_id ────────────
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ucp_user_id
        ON user_class_progress (user_id);
    """)


def downgrade() -> None:
    # M-16: Drop index
    op.execute("DROP INDEX IF EXISTS idx_ucp_user_id;")

    # M-10: Revert ENUM columns back to VARCHAR
    op.execute("ALTER TABLE quests ALTER COLUMN required_grade DROP DEFAULT;")
    op.execute("ALTER TABLE quests ALTER COLUMN status DROP DEFAULT;")
    op.execute("ALTER TABLE users ALTER COLUMN grade DROP DEFAULT;")
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT;")

    op.execute("""
        ALTER TABLE quests
        ALTER COLUMN required_grade TYPE VARCHAR(20) USING required_grade::text;
    """)
    op.execute("""
        ALTER TABLE quests
        ALTER COLUMN status TYPE VARCHAR(30) USING status::text;
    """)
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN grade TYPE VARCHAR(20) USING grade::text;
    """)
    op.execute("""
        ALTER TABLE users
        ALTER COLUMN role TYPE VARCHAR(20) USING role::text;
    """)

    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'freelancer';")
    op.execute("ALTER TABLE users ALTER COLUMN grade SET DEFAULT 'novice';")
    op.execute("ALTER TABLE quests ALTER COLUMN status SET DEFAULT 'open';")
    op.execute("ALTER TABLE quests ALTER COLUMN required_grade SET DEFAULT 'novice';")

    # Re-add check constraint for quest status
    op.execute("""
        ALTER TABLE quests
        ADD CONSTRAINT chk_quest_status
        CHECK (status IN ('draft', 'open', 'assigned', 'in_progress',
                          'completed', 'revision_requested', 'confirmed', 'cancelled'));
    """)

    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS quest_status_enum;")
    op.execute("DROP TYPE IF EXISTS grade_enum;")
    op.execute("DROP TYPE IF EXISTS user_role_enum;")

    # H-03: Drop column
    op.execute("ALTER TABLE quests DROP COLUMN IF EXISTS platform_fee_percent;")
