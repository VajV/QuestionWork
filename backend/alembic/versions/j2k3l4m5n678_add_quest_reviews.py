"""add_quest_reviews — review table for post-quest feedback

Revision ID: j2k3l4m5n678
Revises: i1j2k3l4m567
Create Date: 2026-03-05 12:00:00.000000

Changes:
- Create quest_reviews table (id, quest_id, reviewer_id, reviewee_id, rating 1-5, comment, created_at)
- Unique constraint on (quest_id, reviewer_id) — one review per participant per quest
- Indexes on reviewer_id, reviewee_id for fast lookups
- Add avg_rating / review_count columns to users table
"""

from alembic import op
import sqlalchemy as sa

revision = "j2k3l4m5n678"
down_revision = "i1j2k3l4m567"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── quest_reviews table ──────────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS quest_reviews (
        id VARCHAR(50) PRIMARY KEY,
        quest_id VARCHAR(50) NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
        reviewer_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        reviewee_id VARCHAR(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        rating SMALLINT NOT NULL CHECK (rating >= 1 AND rating <= 5),
        comment TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Unique: one review per reviewer per quest
    op.execute("""
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'uq_quest_reviews_quest_reviewer'
        ) THEN
            ALTER TABLE quest_reviews
                ADD CONSTRAINT uq_quest_reviews_quest_reviewer UNIQUE (quest_id, reviewer_id);
        END IF;
    END $$
    """)

    # Indexes for fast lookups
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_quest_reviews_reviewer ON quest_reviews (reviewer_id)
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_quest_reviews_reviewee ON quest_reviews (reviewee_id)
    """)

    # ── Add avg_rating / review_count to users ───────────────────────────
    op.execute("""
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'avg_rating'
        ) THEN
            ALTER TABLE users ADD COLUMN avg_rating DOUBLE PRECISION;
        END IF;
    END $$
    """)
    op.execute("""
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'review_count'
        ) THEN
            ALTER TABLE users ADD COLUMN review_count INTEGER NOT NULL DEFAULT 0;
        END IF;
    END $$
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS review_count")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avg_rating")
    op.execute("DROP TABLE IF EXISTS quest_reviews")
