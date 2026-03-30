"""
Tests for security hardening: admin IP allowlist, TOTP dependency check,
and TOTP setup/enable/disable endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from fastapi import HTTPException


# ──────────────────────────────────────────────────────────────────────
# Helpers shared with test_admin_endpoints
# ──────────────────────────────────────────────────────────────────────

def _make_admin():
    from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats
    return UserProfile(
        id="admin_test",
        username="test_admin",
        role=UserRoleEnum.admin,
        level=1,
        grade=GradeEnum.novice,
        xp=0,
        xp_to_next=100,
        stats=UserStats(),
        badges=[],
        skills=[],
    )


class _MockConn:
    def __init__(self):
        self._in_txn = False

    def is_in_transaction(self):
        return self._in_txn

    async def fetchrow(self, *a, **kw):
        return None

    async def fetch(self, *a, **kw):
        return []

    async def fetchval(self, *a, **kw):
        return None

    async def execute(self, *a, **kw):
        return "UPDATE 0"

    def transaction(self):
        outer = self
        class _Tx:
            async def __aenter__(self_):
                outer._in_txn = True
                return self_
            async def __aexit__(self_, *args):
                outer._in_txn = False
                return False
        return _Tx()


async def _mock_conn_dep():
    yield _MockConn()


# ──────────────────────────────────────────────────────────────────────
# TestClient fixture
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with (
        patch("app.main.init_db_pool", new_callable=AsyncMock),
        patch("app.main.close_db_pool", new_callable=AsyncMock),
    ):
        from app.main import app
        from app.db.session import get_db_connection
        app.dependency_overrides[get_db_connection] = _mock_conn_dep
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
        app.dependency_overrides.pop(get_db_connection, None)


# ──────────────────────────────────────────────────────────────────────
# IP Allowlist tests
# ──────────────────────────────────────────────────────────────────────

class TestIPAllowlist:
    """Unit tests for the IP allowlist logic inside require_admin."""

    @pytest.mark.asyncio
    async def test_empty_allowlist_permits_all(self):
        """ADMIN_IP_ALLOWLIST='' → any IP is allowed."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()

        request = MagicMock()
        request.client.host = "192.168.99.1"

        conn = _MockConn()

        original = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""
            cfg_module.settings.ADMIN_TOTP_REQUIRED = False

            user = await require_admin(
                request=request,
                current_user=admin_user,
                conn=conn,
                x_totp_token=None,
            )
            assert user.id == "admin_test"
        finally:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original

    @pytest.mark.asyncio
    async def test_allowlist_rejects_unlisted_ip(self):
        """An IP not in the allowlist receives a 403."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "10.0.0.50"

        conn = _MockConn()

        original = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = "10.0.0.1,10.0.0.2"
            cfg_module.settings.ADMIN_TOTP_REQUIRED = False

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin_user,
                    conn=conn,
                    x_totp_token=None,
                )
            assert exc_info.value.status_code == 403
            assert "IP" in exc_info.value.detail
        finally:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original

    @pytest.mark.asyncio
    async def test_allowlist_accepts_cidr(self):
        """CIDR notation e.g. 10.0.0.0/24 should match any IP in subnet."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "10.0.0.123"

        conn = _MockConn()

        original = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = "10.0.0.0/24"
            cfg_module.settings.ADMIN_TOTP_REQUIRED = False

            user = await require_admin(
                request=request,
                current_user=admin_user,
                conn=conn,
                x_totp_token=None,
            )
            assert user.id == "admin_test"
        finally:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original

    @pytest.mark.asyncio
    async def test_allowlist_ignores_spoofed_xff_without_trusted_proxy(self):
        """An untrusted peer cannot bypass admin allowlist with X-Forwarded-For."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "198.51.100.77"
        request.headers = {"x-forwarded-for": "10.0.0.42"}

        conn = _MockConn()

        original_allowlist = cfg_module.settings.ADMIN_IP_ALLOWLIST
        original_trusted = getattr(cfg_module.settings, "TRUSTED_PROXY_CIDRS", "")
        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        try:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = "10.0.0.0/24"
            cfg_module.settings.TRUSTED_PROXY_CIDRS = ""
            cfg_module.settings.ADMIN_TOTP_REQUIRED = False

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin_user,
                    conn=conn,
                    x_totp_token=None,
                )
            assert exc_info.value.status_code == 403
        finally:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_allowlist
            cfg_module.settings.TRUSTED_PROXY_CIDRS = original_trusted
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp

    @pytest.mark.asyncio
    async def test_allowlist_uses_xff_only_for_trusted_proxy_chain(self):
        """Admin allowlist should evaluate the first non-trusted hop in the proxy chain."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "10.0.0.20"
        request.headers = {"x-forwarded-for": "203.0.113.10, 10.0.0.11"}

        conn = _MockConn()

        original_allowlist = cfg_module.settings.ADMIN_IP_ALLOWLIST
        original_trusted = getattr(cfg_module.settings, "TRUSTED_PROXY_CIDRS", "")
        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        try:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = "203.0.113.0/24"
            cfg_module.settings.TRUSTED_PROXY_CIDRS = "10.0.0.0/24"
            cfg_module.settings.ADMIN_TOTP_REQUIRED = False

            user = await require_admin(
                request=request,
                current_user=admin_user,
                conn=conn,
                x_totp_token=None,
            )
            assert user.id == "admin_test"
        finally:
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_allowlist
            cfg_module.settings.TRUSTED_PROXY_CIDRS = original_trusted
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp


# ──────────────────────────────────────────────────────────────────────
# TOTP dependency check tests
# ──────────────────────────────────────────────────────────────────────

class TestTotpDependency:
    @pytest.mark.asyncio
    async def test_totp_not_required_skips_check(self):
        """When ADMIN_TOTP_REQUIRED=False the TOTP header is not validated."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "127.0.0.1"

        conn = _MockConn()

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = False
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

            user = await require_admin(
                request=request,
                current_user=admin_user,
                conn=conn,
                x_totp_token=None,
            )
            assert user.id == "admin_test"
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip

    @pytest.mark.asyncio
    async def test_totp_required_but_not_configured_returns_403(self):
        """User without totp_secret but TOTP required → 403."""
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "127.0.0.1"

        conn = _MockConn()
        conn.fetchval = AsyncMock(return_value=None)  # no totp_secret

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin_user,
                    conn=conn,
                    x_totp_token=None,
                )
            assert exc_info.value.status_code == 403
            assert "not configured" in exc_info.value.detail
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip

    @pytest.mark.asyncio
    async def test_totp_required_missing_header(self):
        """totp_secret set but no header → 403."""
        import pyotp
        from app.api.deps import require_admin
        from app.core import config as cfg_module

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "127.0.0.1"

        secret = pyotp.random_base32()
        conn = _MockConn()
        conn.fetchval = AsyncMock(return_value=secret)

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin_user,
                    conn=conn,
                    x_totp_token=None,  # no token
                )
            assert exc_info.value.status_code == 403
            assert "X-TOTP-Token" in exc_info.value.detail
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip

    @pytest.mark.asyncio
    async def test_totp_required_valid_token_passes(self):
        """Correct TOTP token → user returned."""
        import pyotp
        from app.api.deps import require_admin
        from app.core import config as cfg_module
        from app.core.security import encrypt_totp_secret

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "127.0.0.1"

        secret = pyotp.random_base32()
        valid_token = pyotp.TOTP(secret).now()

        conn = _MockConn()
        conn.fetchval = AsyncMock(return_value=encrypt_totp_secret(secret))

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

            user = await require_admin(
                request=request,
                current_user=admin_user,
                conn=conn,
                x_totp_token=valid_token,
            )
            assert user.id == "admin_test"
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip

    @pytest.mark.asyncio
    async def test_totp_required_wrong_token_403(self):
        """Wrong token → 403."""
        import pyotp
        from app.api.deps import require_admin
        from app.core import config as cfg_module
        from app.core.security import encrypt_totp_secret

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "127.0.0.1"

        secret = pyotp.random_base32()
        conn = _MockConn()
        conn.fetchval = AsyncMock(return_value=encrypt_totp_secret(secret))

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin_user,
                    conn=conn,
                    x_totp_token="000000",
                )
            assert exc_info.value.status_code == 403
            assert "Invalid" in exc_info.value.detail
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip


# ──────────────────────────────────────────────────────────────────────
# TOTP HTTP endpoint tests
# ──────────────────────────────────────────────────────────────────────

class TestTotpEndpoints:
    def test_setup_returns_secret_and_uri(self, client):
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection

        class _ConnTotp(_MockConn):
            def __init__(self):
                super().__init__()
                self.stored_secret = None

            async def execute(self, *a, **kw):
                return "UPDATE 1"

            async def fetchval(self, sql, *a, **kw):
                # No existing active TOTP
                return None

        async def _ok_conn():
            yield _ConnTotp()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _ok_conn
        try:
            r = client.post("/api/v1/admin/auth/totp/setup")
            assert r.status_code == 200
            body = r.json()
            assert "secret" in body
            assert "otpauth_uri" in body
            assert "otpauth://totp/" in body["otpauth_uri"]
            # Verify the returned secret is a valid base32 TOTP key
            assert len(body["secret"]) >= 16
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_enable_with_valid_token(self, client):
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection
        from app.core.security import encrypt_totp_secret

        secret = pyotp.random_base32()
        valid_token = pyotp.TOTP(secret).now()
        encrypted_secret = encrypt_totp_secret(secret)

        class _ConnWithSecret(_MockConn):
            async def fetchval(self, sql, *a, **kw):
                if "pending_totp_secret" in sql:
                    return encrypted_secret
                return None

            async def execute(self, *a, **kw):
                return "UPDATE 1"

        async def _ok_conn():
            yield _ConnWithSecret()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _ok_conn
        try:
            r = client.post("/api/v1/admin/auth/totp/enable", json={"token": valid_token})
            assert r.status_code == 200
            assert r.json()["ok"] is True
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_enable_with_wrong_token_returns_400(self, client):
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection
        from app.core.security import encrypt_totp_secret

        secret = pyotp.random_base32()
        encrypted_secret = encrypt_totp_secret(secret)

        class _ConnWithSecret(_MockConn):
            async def fetchval(self, sql, *a, **kw):
                if "pending_totp_secret" in sql:
                    return encrypted_secret
                return None

            async def execute(self, *a, **kw):
                return "UPDATE 1"

        async def _ok_conn():
            yield _ConnWithSecret()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _ok_conn
        try:
            r = client.post("/api/v1/admin/auth/totp/enable", json={"token": "000000"})
            assert r.status_code == 400
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_enable_without_setup_returns_400(self, client):
        from app.api.deps import require_admin_role_only
        from app.main import app

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        try:
            r = client.post("/api/v1/admin/auth/totp/enable", json={"token": "123456"})
            assert r.status_code == 400
            assert "setup" in r.json()["detail"].lower() or "pending" in r.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)

    def test_disable_clears_secret(self, client):
        from app.api.deps import require_admin
        from app.main import app

        app.dependency_overrides[require_admin] = lambda: _make_admin()
        try:
            r = client.delete("/api/v1/admin/auth/totp")
            assert r.status_code == 200
            assert r.json()["ok"] is True
        finally:
            app.dependency_overrides.pop(require_admin, None)

    def test_totp_disable_requires_full_admin_auth(self, client):
        """P1-3: DELETE /admin/auth/totp without auth → 401 (require_admin gate)."""
        r = client.delete("/api/v1/admin/auth/totp")
        assert r.status_code == 401

    def test_totp_disable_rejects_freelancer(self, client):
        """P1-3: Freelancer cannot disable admin TOTP."""
        from app.api.deps import require_auth
        from app.main import app
        from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats

        freelancer = UserProfile(
            id="fl_test", username="test_fl", role=UserRoleEnum.freelancer,
            level=1, grade=GradeEnum.novice, xp=0, xp_to_next=100,
            stats=UserStats(), badges=[], skills=[],
        )
        app.dependency_overrides[require_auth] = lambda: freelancer
        try:
            r = client.delete("/api/v1/admin/auth/totp")
            assert r.status_code == 403
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_totp_disable_logged_in_admin_logs(self, client):
        """P1-3: TOTP disable writes audit log via log_admin_action."""
        from app.api.deps import require_admin
        from app.main import app

        executed_sqls = []
        original_admin = _make_admin()

        class _AuditConn(_MockConn):
            async def execute(self, sql, *a, **kw):
                executed_sqls.append(sql)
                return "INSERT 0 1"

        async def _audit_conn():
            yield _AuditConn()

        from app.db.session import get_db_connection
        app.dependency_overrides[require_admin] = lambda: original_admin
        app.dependency_overrides[get_db_connection] = _audit_conn
        try:
            r = client.delete("/api/v1/admin/auth/totp")
            assert r.status_code == 200
            # Verify audit log INSERT was executed
            assert any("admin_logs" in sql for sql in executed_sqls)
        finally:
            app.dependency_overrides.pop(require_admin, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_setup_requires_admin_role(self, client):
        """Unauthenticated → 401."""
        r = client.post("/api/v1/admin/auth/totp/setup")
        assert r.status_code == 401


# ──────────────────────────────────────────────────────────────────────
# TOTP Replay prevention tests
# ──────────────────────────────────────────────────────────────────────

class TestTotpReplay:
    """Verify that a TOTP code cannot be reused within the same time window."""

    def test_metrics_requires_totp_header_when_enabled(self, client):
        import pyotp
        from app.api.deps import require_auth
        from app.core import config as cfg_module
        from app.core.security import encrypt_totp_secret
        from app.db.session import get_db_connection
        from app.main import app

        secret = pyotp.random_base32()
        encrypted_secret = encrypt_totp_secret(secret)

        class _ConnWithSecret(_MockConn):
            async def fetchval(self, query, *args, **kwargs):
                if "totp_secret" in query:
                    return encrypted_secret
                return None

        async def _ok_conn():
            yield _ConnWithSecret()

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        original_env = cfg_module.settings.APP_ENV

        app.dependency_overrides[require_auth] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _ok_conn
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""
            cfg_module.settings.APP_ENV = "development"

            response = client.get("/metrics")

            assert response.status_code == 403
            assert "X-TOTP-Token" in response.json()["detail"]
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip
            cfg_module.settings.APP_ENV = original_env
            app.dependency_overrides.pop(require_auth, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_metrics_accepts_valid_totp_once_and_rejects_replay(self, client, monkeypatch):
        import pyotp
        from app.api.deps import require_auth
        from app.core import config as cfg_module
        from app.core.security import encrypt_totp_secret
        from app.db.session import get_db_connection
        from app.main import app

        class _RedisStub:
            def __init__(self):
                self.values = {}

            async def get(self, key):
                return self.values.get(key)

            async def setex(self, key, ttl, value):
                self.values[key] = value

        secret = pyotp.random_base32()
        valid_token = pyotp.TOTP(secret).now()
        encrypted_secret = encrypt_totp_secret(secret)
        redis_stub = _RedisStub()

        class _ConnWithSecret(_MockConn):
            async def fetchval(self, query, *args, **kwargs):
                if "totp_secret" in query:
                    return encrypted_secret
                return None

        async def _ok_conn():
            yield _ConnWithSecret()

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        original_env = cfg_module.settings.APP_ENV

        app.dependency_overrides[require_auth] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _ok_conn
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""
            cfg_module.settings.APP_ENV = "development"
            async def _fake_get_redis(*, required_in_production=False):
                return redis_stub
            monkeypatch.setattr("app.api.deps.get_redis_client", _fake_get_redis)

            first_response = client.get("/metrics", headers={"X-TOTP-Token": valid_token})
            second_response = client.get("/metrics", headers={"X-TOTP-Token": valid_token})

            assert first_response.status_code == 200
            assert second_response.status_code == 403
            assert "already used" in second_response.json()["detail"].lower()
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip
            cfg_module.settings.APP_ENV = original_env
            app.dependency_overrides.pop(require_auth, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    @pytest.mark.asyncio
    async def test_totp_replay_blocked(self):
        """Same TOTP code submitted twice via require_admin → second raises 403."""
        import pyotp
        from app.api.deps import require_admin
        from app.core.security import encrypt_totp_secret
        from app.core import redis_client as redis_module
        from app.core import config as cfg_module

        # Reset cached Redis client to avoid stale event-loop references
        # from earlier TestClient-based tests.
        redis_module._redis_client = None

        secret = pyotp.random_base32()
        valid_token = pyotp.TOTP(secret).now()
        encrypted = encrypt_totp_secret(secret)

        admin = _make_admin()

        conn = _MockConn()
        # Mock fetchval to return the encrypted TOTP secret
        async def _fetchval(query, *args, **kwargs):
            if "totp_secret" in query:
                return encrypted
            return None
        conn.fetchval = _fetchval

        request = MagicMock()
        request.client.host = "127.0.0.1"

        orig_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        orig_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        cfg_module.settings.ADMIN_TOTP_REQUIRED = True
        cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

        redis = await redis_module.get_redis_client()
        replay_key = f"totp_used:{admin.id}:{valid_token}"
        if redis:
            await redis.delete(replay_key)

        try:
            # First call — should succeed
            result = await require_admin(
                request=request,
                current_user=admin,
                conn=conn,
                x_totp_token=valid_token,
            )
            assert result.id == admin.id

            # Second call with same code — should raise 403
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin,
                    conn=conn,
                    x_totp_token=valid_token,
                )
            assert exc_info.value.status_code == 403
            assert "already used" in exc_info.value.detail.lower()
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = orig_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = orig_ip
            if redis:
                await redis.delete(replay_key)

    @pytest.mark.asyncio
    async def test_totp_replay_without_redis_fails_closed_in_production(self, monkeypatch):
        """Production admin auth must not fall back to in-memory replay protection."""
        import pyotp
        from app.api.deps import require_admin
        from app.core.security import encrypt_totp_secret
        from app.core import config as cfg_module

        secret = pyotp.random_base32()
        valid_token = pyotp.TOTP(secret).now()
        encrypted = encrypt_totp_secret(secret)

        admin = _make_admin()

        conn = _MockConn()

        async def _fetchval(query, *args, **kwargs):
            if "totp_secret" in query:
                return encrypted
            return None

        conn.fetchval = _fetchval

        request = MagicMock()
        request.client.host = "127.0.0.1"

        orig_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        orig_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        orig_env = cfg_module.settings.APP_ENV
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""
            cfg_module.settings.APP_ENV = "production"

            async def _fake_get_redis_none(*, required_in_production=False):
                return None
            monkeypatch.setattr(
                "app.api.deps.get_redis_client",
                _fake_get_redis_none,
            )

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin,
                    conn=conn,
                    x_totp_token=valid_token,
                )

            assert exc_info.value.status_code == 503
            assert "redis" in exc_info.value.detail.lower()
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = orig_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = orig_ip
            cfg_module.settings.APP_ENV = orig_env


class TestRedisProductionAlias:
    @pytest.mark.asyncio
    async def test_required_redis_uses_prod_alias(self):
        from app.core import redis_client as redis_module
        from app.core import config as cfg_module

        orig_env = cfg_module.settings.APP_ENV
        orig_url = cfg_module.settings.REDIS_URL
        orig_client = redis_module._redis_client
        orig_failure_at = redis_module._last_connect_failure_at

        try:
            cfg_module.settings.APP_ENV = "prod"
            cfg_module.settings.REDIS_URL = None
            redis_module._redis_client = None
            redis_module._last_connect_failure_at = 0.0

            with pytest.raises(RuntimeError, match="Redis is required in production"):
                await redis_module.get_redis_client(required_in_production=True)
        finally:
            cfg_module.settings.APP_ENV = orig_env
            cfg_module.settings.REDIS_URL = orig_url
            redis_module._redis_client = orig_client
            redis_module._last_connect_failure_at = orig_failure_at

    @pytest.mark.asyncio
    async def test_totp_replay_without_redis_uses_memory_in_development(self, monkeypatch):
        """Development admin auth may still use in-memory replay fallback."""
        import pyotp
        from app.api.deps import require_admin, _TOTP_REPLAY_STORE
        from app.core.security import encrypt_totp_secret
        from app.core import config as cfg_module

        secret = pyotp.random_base32()
        valid_token = pyotp.TOTP(secret).now()
        encrypted = encrypt_totp_secret(secret)

        admin = _make_admin()

        conn = _MockConn()

        async def _fetchval(query, *args, **kwargs):
            if "totp_secret" in query:
                return encrypted
            return None

        conn.fetchval = _fetchval

        request = MagicMock()
        request.client.host = "127.0.0.1"

        orig_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        orig_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        orig_env = cfg_module.settings.APP_ENV
        _TOTP_REPLAY_STORE.clear()
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""
            cfg_module.settings.APP_ENV = "development"

            async def _fake_get_redis_none(*, required_in_production=False):
                return None
            monkeypatch.setattr(
                "app.api.deps.get_redis_client",
                _fake_get_redis_none,
            )

            user = await require_admin(
                request=request,
                current_user=admin,
                conn=conn,
                x_totp_token=valid_token,
            )

            assert user.id == admin.id
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = orig_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = orig_ip
            cfg_module.settings.APP_ENV = orig_env
            _TOTP_REPLAY_STORE.clear()


# ──────────────────────────────────────────────────────────────────────
# Global 500 exception handler tests
# ──────────────────────────────────────────────────────────────────────

class TestGlobal500Handler:
    """Verify the global exception handler returns sanitized 500 without leaking internals."""

    @pytest.mark.asyncio
    async def test_global_handler_returns_generic_500(self):
        """global_exception_handler() returns generic JSON 500, never leaking exception details."""
        import json
        from app.main import global_exception_handler

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/api/v1/_test"

        exc = RuntimeError("secret internal details")
        response = await global_exception_handler(request, exc)

        assert response.status_code == 500
        body = json.loads(response.body)
        assert body == {"detail": "Internal server error"}
        assert "secret" not in response.body.decode()
        assert "RuntimeError" not in response.body.decode()


# ──────────────────────────────────────────────────────────────────────
# AssignQuestRequest body validation tests
# ──────────────────────────────────────────────────────────────────────

class TestAssignQuestBody:
    """Verify that assign endpoint accepts body or legacy query param."""

    def test_assign_without_body_returns_422(self, client):
        """POST /quests/{id}/assign without body or query param → 422."""
        from app.api.deps import require_auth
        from app.main import app

        app.dependency_overrides[require_auth] = lambda: _make_admin()
        try:
            r = client.post("/api/v1/quests/quest_123/assign")
            assert r.status_code == 422
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_assign_with_empty_freelancer_id_returns_422(self, client):
        """POST /quests/{id}/assign with empty freelancer_id → 422."""
        from app.api.deps import require_auth
        from app.main import app

        app.dependency_overrides[require_auth] = lambda: _make_admin()
        try:
            r = client.post("/api/v1/quests/quest_123/assign", json={"freelancer_id": ""})
            assert r.status_code == 422
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_assign_query_param_ignored(self, client):
        """Old-style query param remains supported for backward compatibility."""
        from app.api.deps import require_auth
        from app.main import app

        app.dependency_overrides[require_auth] = lambda: _make_admin()
        try:
            with patch("app.api.v1.endpoints.quests.quest_service.assign_freelancer", new=AsyncMock(return_value={"id": "quest_123", "status": "assigned"})) as mock_assign:
                r = client.post("/api/v1/quests/quest_123/assign?freelancer_id=user_abc")
            assert r.status_code == 200
            assert r.json()["quest"]["status"] == "assigned"
            mock_assign.assert_awaited_once()
        finally:
            app.dependency_overrides.pop(require_auth, None)


# ──────────────────────────────────────────────────────────────────────
# P0: Admin TOTP staged activation — bypass prevention tests
# ──────────────────────────────────────────────────────────────────────

class TestTotpStagedActivation:
    """Verify that setup writes only a pending secret, rotation requires
    current TOTP, and enable is the only path that activates a secret."""

    def test_setup_first_time_does_not_activate_secret(self, client):
        """First-time setup stores pending_totp_secret, NOT totp_secret."""
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection

        executed_updates = []

        class _TrackingConn(_MockConn):
            async def execute(self, sql, *a, **kw):
                executed_updates.append((sql, a))
                return "UPDATE 1"

            async def fetchval(self, sql, *a, **kw):
                # No existing active TOTP
                return None

        async def _conn():
            yield _TrackingConn()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _conn
        try:
            r = client.post("/api/v1/admin/auth/totp/setup")
            assert r.status_code == 200
            body = r.json()
            assert "secret" in body
            # Verify we wrote to pending_totp_secret, not totp_secret
            assert any("pending_totp_secret" in sql for sql, _ in executed_updates)
            assert not any(
                "SET totp_secret" in sql for sql, _ in executed_updates
                if "pending" not in sql
            )
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_setup_rotation_rejected_without_current_totp(self, client):
        """Admin with active TOTP cannot call setup without X-TOTP-Token."""
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection
        from app.core.security import encrypt_totp_secret

        existing_secret = pyotp.random_base32()
        encrypted = encrypt_totp_secret(existing_secret)

        class _ConnWithActive(_MockConn):
            async def fetchval(self, sql, *a, **kw):
                if "totp_secret" in sql and "pending" not in sql:
                    return encrypted
                return None

        async def _conn():
            yield _ConnWithActive()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _conn
        try:
            r = client.post("/api/v1/admin/auth/totp/setup")
            assert r.status_code == 403
            assert "current" in r.json()["detail"].lower() or "rotate" in r.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_setup_rotation_accepted_with_valid_current_totp(self, client):
        """Admin with active TOTP can rotate when providing a valid code."""
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection
        from app.core.security import encrypt_totp_secret

        existing_secret = pyotp.random_base32()
        encrypted = encrypt_totp_secret(existing_secret)
        valid_token = pyotp.TOTP(existing_secret).now()

        class _ConnWithActive(_MockConn):
            async def fetchval(self, sql, *a, **kw):
                if "totp_secret" in sql and "pending" not in sql:
                    return encrypted
                return None

            async def execute(self, sql, *a, **kw):
                return "UPDATE 1"

        async def _conn():
            yield _ConnWithActive()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _conn
        try:
            r = client.post(
                "/api/v1/admin/auth/totp/setup",
                headers={"X-TOTP-Token": valid_token},
            )
            assert r.status_code == 200
            assert "secret" in r.json()
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_setup_rotation_rejected_with_wrong_totp(self, client):
        """Admin with active TOTP providing wrong code gets 403."""
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection
        from app.core.security import encrypt_totp_secret

        existing_secret = pyotp.random_base32()
        encrypted = encrypt_totp_secret(existing_secret)

        class _ConnWithActive(_MockConn):
            async def fetchval(self, sql, *a, **kw):
                if "totp_secret" in sql and "pending" not in sql:
                    return encrypted
                return None

        async def _conn():
            yield _ConnWithActive()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _conn
        try:
            r = client.post(
                "/api/v1/admin/auth/totp/setup",
                headers={"X-TOTP-Token": "000000"},
            )
            assert r.status_code == 403
            assert "invalid" in r.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_enable_promotes_pending_to_active(self, client):
        """Enable verifies against pending secret and promotes it to active."""
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection
        from app.core.security import encrypt_totp_secret

        pending_secret = pyotp.random_base32()
        encrypted_pending = encrypt_totp_secret(pending_secret)
        valid_token = pyotp.TOTP(pending_secret).now()
        executed_updates = []

        class _ConnWithPending(_MockConn):
            async def fetchval(self, sql, *a, **kw):
                if "pending_totp_secret" in sql:
                    return encrypted_pending
                return None

            async def execute(self, sql, *a, **kw):
                executed_updates.append(sql)
                return "UPDATE 1"

        async def _conn():
            yield _ConnWithPending()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _conn
        try:
            r = client.post(
                "/api/v1/admin/auth/totp/enable",
                json={"token": valid_token},
            )
            assert r.status_code == 200
            assert r.json()["ok"] is True
            # Verify the promote SQL sets totp_secret and clears pending
            promote_sql = [s for s in executed_updates if "totp_secret" in s and "pending_totp_secret" in s]
            assert len(promote_sql) >= 1, "Expected SQL to promote pending→active"
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_enable_without_pending_returns_400(self, client):
        """Enable without a prior setup returns 400."""
        from app.api.deps import require_admin_role_only
        from app.main import app

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        try:
            r = client.post("/api/v1/admin/auth/totp/enable", json={"token": "123456"})
            assert r.status_code == 400
            assert "pending" in r.json()["detail"].lower() or "setup" in r.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)

    def test_enable_with_wrong_token_does_not_activate(self, client):
        """Wrong token against pending secret → 400, no promotion."""
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection
        from app.core.security import encrypt_totp_secret

        pending_secret = pyotp.random_base32()
        encrypted_pending = encrypt_totp_secret(pending_secret)
        executed_updates = []

        class _ConnWithPending(_MockConn):
            async def fetchval(self, sql, *a, **kw):
                if "pending_totp_secret" in sql:
                    return encrypted_pending
                return None

            async def execute(self, sql, *a, **kw):
                executed_updates.append(sql)
                return "UPDATE 1"

        async def _conn():
            yield _ConnWithPending()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _conn
        try:
            r = client.post(
                "/api/v1/admin/auth/totp/enable",
                json={"token": "000000"},
            )
            assert r.status_code == 400
            # No promotion SQL should have been executed
            promote_sql = [s for s in executed_updates if "SET totp_secret" in s]
            assert len(promote_sql) == 0, "Wrong token must not promote pending to active"
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_disable_clears_both_active_and_pending(self, client):
        """Disable clears both totp_secret and pending_totp_secret."""
        from app.api.deps import require_admin
        from app.main import app
        from app.db.session import get_db_connection

        executed_updates = []

        class _TrackingConn(_MockConn):
            async def execute(self, sql, *a, **kw):
                executed_updates.append(sql)
                return "UPDATE 1"

        async def _conn():
            yield _TrackingConn()

        app.dependency_overrides[require_admin] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _conn
        try:
            r = client.delete("/api/v1/admin/auth/totp")
            assert r.status_code == 200
            # Verify both columns are cleared
            clear_sql = [s for s in executed_updates if "pending_totp_secret" in s and "totp_secret" in s]
            assert len(clear_sql) >= 1, "Disable must clear both active and pending TOTP"
        finally:
            app.dependency_overrides.pop(require_admin, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    @pytest.mark.asyncio
    async def test_pending_secret_not_usable_for_admin_access(self):
        """A pending secret that hasn't been enabled must not grant admin access."""
        import pyotp
        from app.api.deps import require_admin
        from app.core import config as cfg_module
        from app.core.security import encrypt_totp_secret

        pending_secret = pyotp.random_base32()
        pending_token = pyotp.TOTP(pending_secret).now()
        encrypted_pending = encrypt_totp_secret(pending_secret)

        admin_user = _make_admin()
        request = MagicMock()
        request.client.host = "127.0.0.1"

        class _ConnPendingOnly(_MockConn):
            async def fetchval(self, sql, *a, **kw):
                # No active totp_secret (only pending exists, but that's a different column)
                if "totp_secret" in sql and "pending" not in sql:
                    return None
                return None

        conn = _ConnPendingOnly()

        original_totp = cfg_module.settings.ADMIN_TOTP_REQUIRED
        original_ip = cfg_module.settings.ADMIN_IP_ALLOWLIST
        try:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = True
            cfg_module.settings.ADMIN_IP_ALLOWLIST = ""

            with pytest.raises(HTTPException) as exc_info:
                await require_admin(
                    request=request,
                    current_user=admin_user,
                    conn=conn,
                    x_totp_token=pending_token,
                )
            assert exc_info.value.status_code == 403
            assert "not configured" in exc_info.value.detail.lower()
        finally:
            cfg_module.settings.ADMIN_TOTP_REQUIRED = original_totp
            cfg_module.settings.ADMIN_IP_ALLOWLIST = original_ip

    def test_setup_first_time_writes_audit_log(self, client):
        """First-time setup writes a 'totp_setup_started' audit entry."""
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection

        audit_inserts = []

        class _AuditConn(_MockConn):
            async def execute(self, sql, *a, **kw):
                if "admin_logs" in sql:
                    audit_inserts.append(a)
                return "INSERT 0 1"

            async def fetchval(self, sql, *a, **kw):
                return None  # no existing TOTP

        async def _conn():
            yield _AuditConn()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _conn
        try:
            r = client.post("/api/v1/admin/auth/totp/setup")
            assert r.status_code == 200
            assert len(audit_inserts) == 1
            # action is the 3rd positional arg (log_id, admin_id, action, ...)
            assert audit_inserts[0][2] == "totp_setup_started"
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_setup_rotation_writes_audit_log(self, client):
        """Rotation writes a 'totp_rotation_started' audit entry."""
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection
        from app.core.security import encrypt_totp_secret

        existing_secret = pyotp.random_base32()
        encrypted = encrypt_totp_secret(existing_secret)
        valid_token = pyotp.TOTP(existing_secret).now()
        audit_inserts = []

        class _AuditConn(_MockConn):
            async def execute(self, sql, *a, **kw):
                if "admin_logs" in sql:
                    audit_inserts.append(a)
                return "INSERT 0 1"

            async def fetchval(self, sql, *a, **kw):
                if "totp_secret" in sql and "pending" not in sql:
                    return encrypted
                return None

        async def _conn():
            yield _AuditConn()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _conn
        try:
            r = client.post(
                "/api/v1/admin/auth/totp/setup",
                headers={"X-TOTP-Token": valid_token},
            )
            assert r.status_code == 200
            assert len(audit_inserts) == 1
            assert audit_inserts[0][2] == "totp_rotation_started"
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep

    def test_enable_writes_audit_log(self, client):
        """Enable writes a 'totp_enabled' audit entry after activation."""
        import pyotp
        from app.api.deps import require_admin_role_only
        from app.main import app
        from app.db.session import get_db_connection
        from app.core.security import encrypt_totp_secret

        pending_secret = pyotp.random_base32()
        encrypted_pending = encrypt_totp_secret(pending_secret)
        valid_token = pyotp.TOTP(pending_secret).now()
        audit_inserts = []

        class _AuditConn(_MockConn):
            async def fetchval(self, sql, *a, **kw):
                if "pending_totp_secret" in sql:
                    return encrypted_pending
                return None

            async def execute(self, sql, *a, **kw):
                if "admin_logs" in sql:
                    audit_inserts.append(a)
                return "UPDATE 1"

        async def _conn():
            yield _AuditConn()

        app.dependency_overrides[require_admin_role_only] = lambda: _make_admin()
        app.dependency_overrides[get_db_connection] = _conn
        try:
            r = client.post(
                "/api/v1/admin/auth/totp/enable",
                json={"token": valid_token},
            )
            assert r.status_code == 200
            assert len(audit_inserts) == 1
            assert audit_inserts[0][2] == "totp_enabled"
        finally:
            app.dependency_overrides.pop(require_admin_role_only, None)
            app.dependency_overrides[get_db_connection] = _mock_conn_dep
