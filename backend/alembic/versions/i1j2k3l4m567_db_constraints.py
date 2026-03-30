"""db_constraints — CHECK constraints, NOT NULL, ON DELETE, updated_at trigger

Revision ID: i1j2k3l4m567
Revises: h9i0j1k2l345
Create Date: 2026-03-04 18:00:00.000000

Changes:
- P1-22: ADD CHECK constraints (xp >= 0, level >= 1, budget > 0, etc.)
- P1-23: Set client_id NOT NULL on quests (populate NULL rows first)
- P1-24: ADD ON DELETE CASCADE/SET NULL to foreign keys missing them
- P1-25: Create updated_at auto-update trigger function + apply to users, quests
- P2-19: ADD index on transactions.created_at
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "i1j2k3l4m567"
down_revision = "h9i0j1k2l345"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── P1-22: CHECK constraints ──────────────────────────────────────────
    # Users
    op.execute("ALTER TABLE users ADD CONSTRAINT chk_users_xp_non_negative CHECK (xp >= 0)")
    op.execute("ALTER TABLE users ADD CONSTRAINT chk_users_level_positive CHECK (level >= 1)")
    op.execute("ALTER TABLE users ADD CONSTRAINT chk_users_xp_to_next_positive CHECK (xp_to_next >= 0)")
    op.execute("ALTER TABLE users ADD CONSTRAINT chk_users_stat_points_non_negative CHECK (stat_points >= 0)")

    # Quests
    op.execute("ALTER TABLE quests ADD CONSTRAINT chk_quests_budget_positive CHECK (budget > 0)")
    op.execute("ALTER TABLE quests ADD CONSTRAINT chk_quests_xp_reward_non_negative CHECK (xp_reward >= 0)")

    # Transactions
    op.execute("ALTER TABLE transactions ADD CONSTRAINT chk_transactions_amount_positive CHECK (amount > 0)")

    # ── P1-23: quests.client_id NOT NULL ──────────────────────────────────
    # First, set any NULL client_id rows to 'platform' (the system user)
    op.execute("UPDATE quests SET client_id = 'platform' WHERE client_id IS NULL")
    op.alter_column("quests", "client_id", nullable=False)

    # ── P1-24: ON DELETE actions on foreign keys ──────────────────────────
    # quests.client_id → users.id: SET NULL is wrong since now NOT NULL, use RESTRICT
    # We need to drop + recreate the FK constraint
    op.execute("""
        DO $$
        BEGIN
            -- Drop existing FK if it has no ON DELETE action
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'quests_client_id_fkey' AND table_name = 'quests'
            ) THEN
                ALTER TABLE quests DROP CONSTRAINT quests_client_id_fkey;
            END IF;
            ALTER TABLE quests ADD CONSTRAINT quests_client_id_fkey 
                FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE RESTRICT;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'quests_assigned_to_fkey' AND table_name = 'quests'
            ) THEN
                ALTER TABLE quests DROP CONSTRAINT quests_assigned_to_fkey;
            END IF;
            ALTER TABLE quests ADD CONSTRAINT quests_assigned_to_fkey 
                FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL;
        END $$;
    """)

    # transactions → users: CASCADE
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'transactions_user_id_fkey' AND table_name = 'transactions'
            ) THEN
                ALTER TABLE transactions DROP CONSTRAINT transactions_user_id_fkey;
            END IF;
            ALTER TABLE transactions ADD CONSTRAINT transactions_user_id_fkey 
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        END $$;
    """)

    # ── P1-25: updated_at auto-update trigger ─────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION trigger_set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    for table in ("users", "quests", "wallets", "user_class_progress"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION trigger_set_updated_at()
        """)

    # ── P2-19: Index on transactions.created_at ───────────────────────────
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions (created_at DESC)")


def downgrade() -> None:
    # Drop triggers
    for table in ("users", "quests", "wallets", "user_class_progress"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS trigger_set_updated_at()")

    # Drop index
    op.execute("DROP INDEX IF EXISTS idx_transactions_created_at")

    # Revert client_id to nullable
    op.alter_column("quests", "client_id", nullable=True)

    # Drop CHECK constraints
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_xp_non_negative")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_level_positive")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_xp_to_next_positive")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_stat_points_non_negative")
    op.execute("ALTER TABLE quests DROP CONSTRAINT IF EXISTS chk_quests_budget_positive")
    op.execute("ALTER TABLE quests DROP CONSTRAINT IF EXISTS chk_quests_xp_reward_non_negative")
    op.execute("ALTER TABLE transactions DROP CONSTRAINT IF EXISTS chk_transactions_amount_positive")
