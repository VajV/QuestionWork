"""add_indexes

Revision ID: b1c2d3e4f567
Revises: 0a14b7f67d64
Create Date: 2026-03-02 10:00:00.000000

"""

from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f567"
down_revision: Union[str, None] = "0a14b7f67d64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Quests indexes for common filters and lookups
    op.execute("CREATE INDEX IF NOT EXISTS idx_quests_status ON quests (status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_quests_client_id ON quests (client_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_quests_assigned_to ON quests (assigned_to);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_quests_required_grade ON quests (required_grade);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_quests_created_at ON quests (created_at DESC);")

    # Applications indexes for JOIN and uniqueness lookups
    op.execute("CREATE INDEX IF NOT EXISTS idx_applications_quest_id ON applications (quest_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_applications_freelancer_id ON applications (freelancer_id);")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_applications_quest_freelancer "
        "ON applications (quest_id, freelancer_id);"
    )

    # Transactions indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions (user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_quest_id ON transactions (quest_id);")

    # Users indexes for filtering
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_grade ON users (grade);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_role;")
    op.execute("DROP INDEX IF EXISTS idx_users_grade;")
    op.execute("DROP INDEX IF EXISTS idx_transactions_quest_id;")
    op.execute("DROP INDEX IF EXISTS idx_transactions_user_id;")
    op.execute("DROP INDEX IF EXISTS idx_applications_quest_freelancer;")
    op.execute("DROP INDEX IF EXISTS idx_applications_freelancer_id;")
    op.execute("DROP INDEX IF EXISTS idx_applications_quest_id;")
    op.execute("DROP INDEX IF EXISTS idx_quests_created_at;")
    op.execute("DROP INDEX IF EXISTS idx_quests_required_grade;")
    op.execute("DROP INDEX IF EXISTS idx_quests_assigned_to;")
    op.execute("DROP INDEX IF EXISTS idx_quests_client_id;")
    op.execute("DROP INDEX IF EXISTS idx_quests_status;")
