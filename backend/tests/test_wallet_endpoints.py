"""Tests for wallet HTTP endpoints — auth guard and response shape."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Minimal asyncpg Connection mock
# ---------------------------------------------------------------------------


class _MockConn:
    """Asyncpg Connection mock."""

    def is_in_transaction(self):
        return True

    async def fetchrow(self, *a, **kw):
        return None

    async def fetch(self, *a, **kw):
        return []

    async def fetchval(self, *a, **kw):
        return 0

    async def execute(self, *a, **kw):
        return "INSERT 0 1"

    def transaction(self):
        """Return an async context manager (needed for withdrawal)."""
        class _Tx:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
        return _Tx()


async def _mock_conn_dep():
    yield _MockConn()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user(role="freelancer"):
    from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats

    return UserProfile(
        id=f"{role}_test",
        username=f"test_{role}",
        role=UserRoleEnum(role),
        level=1,
        grade=GradeEnum.novice,
        xp=0,
        xp_to_next=100,
        stats=UserStats(),
        badges=[],
        skills=[],
    )


@pytest.fixture(scope="module")
def client():
    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock),
        patch("app.main.close_db_pool", new_callable=AsyncMock),
        patch("app.main.engine", new_callable=AsyncMock),
    ):
        from app.main import app
        from app.db.session import get_db_connection

        app.dependency_overrides[get_db_connection] = _mock_conn_dep

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.pop(get_db_connection, None)


# ---------------------------------------------------------------------------
# GET /wallet/balance
# ---------------------------------------------------------------------------


def test_wallet_balance_requires_auth(client):
    """No auth → 401."""
    r = client.get("/api/v1/wallet/balance")
    assert r.status_code == 401


def test_wallet_balance_authenticated(client):
    """Authenticated user gets balance response."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        r = client.get("/api/v1/wallet/balance")
        assert r.status_code == 200
        body = r.json()
        assert "user_id" in body
        assert "balances" in body
        assert isinstance(body["balances"], list)
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# GET /wallet/transactions
# ---------------------------------------------------------------------------


def test_wallet_transactions_requires_auth(client):
    """No auth → 401."""
    r = client.get("/api/v1/wallet/transactions")
    assert r.status_code == 401


def test_wallet_transactions_authenticated(client):
    """Authenticated user gets transaction history."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        r = client.get("/api/v1/wallet/transactions")
        assert r.status_code == 200
        body = r.json()
        assert "user_id" in body
        assert "transactions" in body
        assert isinstance(body["transactions"], list)
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_wallet_transactions_pagination(client):
    """Pagination params accepted."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        r = client.get("/api/v1/wallet/transactions?limit=5&offset=10")
        assert r.status_code == 200
        body = r.json()
        assert body["limit"] == 5
        assert body["offset"] == 10
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_wallet_transactions_invalid_limit(client):
    """limit=0 or negative → 422."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        r = client.get("/api/v1/wallet/transactions?limit=0")
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# POST /wallet/withdraw
# ---------------------------------------------------------------------------


def test_withdraw_requires_auth(client):
    """No auth → 401."""
    r = client.post("/api/v1/wallet/withdraw", json={"amount": 50.0, "currency": "RUB"})
    assert r.status_code == 401


def test_withdraw_insufficient_funds(client, monkeypatch):
    """Wallet with 0 balance → 402."""
    from app.api.deps import require_auth
    from app.main import app
    from app.core import config as cfg
    monkeypatch.setattr(cfg.settings, "MIN_WITHDRAWAL_AMOUNT", 10.0)

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        # _MockConn.fetchrow returns None → no wallet → InsufficientFundsError
        r = client.post("/api/v1/wallet/withdraw", json={"amount": 50.0, "currency": "RUB"})
        assert r.status_code == 402
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_withdraw_below_minimum(client, monkeypatch):
    """Amount below MIN_WITHDRAWAL_AMOUNT → 400."""
    from app.api.deps import require_auth
    from app.main import app
    from app.core import config as cfg
    monkeypatch.setattr(cfg.settings, "MIN_WITHDRAWAL_AMOUNT", 100.0)

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        r = client.post("/api/v1/wallet/withdraw", json={"amount": 5.0, "currency": "RUB"})
        assert r.status_code == 400
        assert "Minimum" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_withdraw_invalid_amount_zero(client):
    """amount=0 fails pydantic validation → 422."""
    from app.api.deps import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    try:
        r = client.post("/api/v1/wallet/withdraw", json={"amount": 0.0, "currency": "RUB"})
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_withdraw_success(client, monkeypatch):
    """Successful withdrawal returns 201 with pending status."""
    from app.api.deps import require_auth
    from app.db.session import get_db_connection
    from app.main import app
    from app.core import config as cfg
    monkeypatch.setattr(cfg.settings, "MIN_WITHDRAWAL_AMOUNT", 10.0)

    class _ConnWithBalance(_MockConn):
        async def fetchrow(self, *a, **kw):
            return {"id": "wallet_test", "balance": 500.0}

    async def _rich_conn():
        yield _ConnWithBalance()

    app.dependency_overrides[require_auth] = lambda: _make_user("freelancer")
    app.dependency_overrides[get_db_connection] = _rich_conn
    try:
        r = client.post("/api/v1/wallet/withdraw", json={"amount": 50.0, "currency": "RUB"})
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "pending"
        assert body["amount"] == 50.0
        assert body["new_balance"] == 450.0
        assert "transaction_id" in body
    finally:
        app.dependency_overrides.pop(require_auth, None)
        app.dependency_overrides.pop(get_db_connection, None)
