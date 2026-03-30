"""
Integration tests — run against a real PostgreSQL database.

These tests are SKIPPED by default. To run them, start the database first:
    docker compose -f docker-compose.db.yml up -d
    cd backend && alembic upgrade head

Then run:
    pytest tests/test_integration.py -q --no-cov -m integration
"""

import os
import uuid

import pytest
import pytest_asyncio

# Skip the entire module when DATABASE_URL is not available or DB is unreachable.
_DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/questionwork")

try:
    import asyncpg
    import asyncio

    async def _ping():
        conn = await asyncpg.connect(_DB_URL, timeout=3)
        await conn.close()

    asyncio.run(_ping())
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DB_AVAILABLE, reason="PostgreSQL not reachable"),
]


@pytest_asyncio.fixture()
async def conn():
    """Yield a connection inside a transaction that is always rolled back."""
    connection = await asyncpg.connect(_DB_URL)
    tx = connection.transaction()
    await tx.start()
    try:
        yield connection
    finally:
        await tx.rollback()
        await connection.close()


# ──────────────────────────────────────────────────────
# Wallet round-trip: credit → check balance → debit
# ──────────────────────────────────────────────────────

class TestWalletRoundTrip:
    @pytest.mark.asyncio
    async def test_credit_and_debit(self, conn):
        """Credit funds, verify balance, debit, verify again."""
        from decimal import Decimal
        from app.services import wallet_service

        user_id = f"test_{uuid.uuid4().hex[:8]}"

        # Seed user + wallet
        await conn.execute(
            """
            INSERT INTO users (id, username, email, password_hash, role)
            VALUES ($1, $2, $3, 'hash', 'freelancer')
            """,
            user_id, f"u_{user_id}", f"{user_id}@test.local",
        )
        await conn.execute(
            """
            INSERT INTO wallets (id, user_id, currency, balance, version)
            VALUES ($1, $2, 'RUB', 0, 1)
            """,
            f"w_{user_id}", user_id,
        )

        # Credit
        await wallet_service.credit(conn, user_id, Decimal("500.00"), tx_type="quest_payment", quest_id=None)

        row = await conn.fetchrow("SELECT balance FROM wallets WHERE user_id = $1", user_id)
        assert row["balance"] == Decimal("500.00")

        # Debit
        await wallet_service.debit(conn, user_id, Decimal("200.00"), tx_type="withdrawal", quest_id=None)

        row = await conn.fetchrow("SELECT balance FROM wallets WHERE user_id = $1", user_id)
        assert row["balance"] == Decimal("300.00")

    @pytest.mark.asyncio
    async def test_debit_insufficient_funds(self, conn):
        """Debit more than balance should raise InsufficientFundsError."""
        from decimal import Decimal
        from app.services import wallet_service
        from app.services.wallet_service import InsufficientFundsError

        user_id = f"test_{uuid.uuid4().hex[:8]}"

        await conn.execute(
            """
            INSERT INTO users (id, username, email, password_hash, role)
            VALUES ($1, $2, $3, 'hash', 'freelancer')
            """,
            user_id, f"u_{user_id}", f"{user_id}@test.local",
        )
        await conn.execute(
            """
            INSERT INTO wallets (id, user_id, currency, balance, version)
            VALUES ($1, $2, 'RUB', 100.00, 1)
            """,
            f"w_{user_id}", user_id,
        )

        with pytest.raises(InsufficientFundsError):
            await wallet_service.debit(conn, user_id, Decimal("999.99"), tx_type="withdrawal")


# ──────────────────────────────────────────────────────
# Badge award round-trip
# ──────────────────────────────────────────────────────

class TestBadgeAward:
    @pytest.mark.asyncio
    async def test_badge_awarded_on_criteria_met(self, conn):
        """Insert a badge in catalogue, trigger check_and_award, verify it's awarded."""
        from app.services import badge_service

        user_id = f"test_{uuid.uuid4().hex[:8]}"
        badge_id = f"badge_{uuid.uuid4().hex[:8]}"

        await conn.execute(
            """
            INSERT INTO users (id, username, email, password_hash, role)
            VALUES ($1, $2, $3, 'hash', 'freelancer')
            """,
            user_id, f"u_{user_id}", f"{user_id}@test.local",
        )
        await conn.execute(
            """
            INSERT INTO badges (id, name, description, icon, criteria_type, criteria_value)
            VALUES ($1, 'Test Badge', 'First quest!', '🏆', 'quests_completed', 1)
            """,
            badge_id,
        )

        result = await badge_service.check_and_award(
            conn, user_id, "quest_completed",
            {"quests_completed": 1, "xp": 100, "level": 1, "grade": "novice", "earnings": 0},
        )
        # At least our test badge should be awarded (DB may have pre-seeded badges too)
        awarded_names = [b.badge_name for b in result.newly_earned]
        assert "Test Badge" in awarded_names

        # Second call should NOT re-award
        result2 = await badge_service.check_and_award(
            conn, user_id, "quest_completed",
            {"quests_completed": 1, "xp": 100, "level": 1, "grade": "novice", "earnings": 0},
        )
        assert len(result2.newly_earned) == 0


# ──────────────────────────────────────────────────────
# Notification create + read
# ──────────────────────────────────────────────────────

class TestNotifications:
    @pytest.mark.asyncio
    async def test_create_and_list_notifications(self, conn):
        """Create a notification, verify it appears in list."""
        from app.services import notification_service

        user_id = f"test_{uuid.uuid4().hex[:8]}"

        await conn.execute(
            """
            INSERT INTO users (id, username, email, password_hash, role)
            VALUES ($1, $2, $3, 'hash', 'freelancer')
            """,
            user_id, f"u_{user_id}", f"{user_id}@test.local",
        )

        notif = await notification_service.create_notification(
            conn, user_id=user_id, title="Test", message="Hello", event_type="test",
        )
        assert notif.user_id == user_id
        assert notif.is_read is False

        result = await notification_service.get_notifications(conn, user_id)
        assert result.total >= 1
