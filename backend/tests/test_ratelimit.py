import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.ratelimit import check_rate_limit, get_client_ip, _RATELIMIT_LUA
from app.core.config import settings


# ── get_client_ip tests ──────────────────────────────────────────────


def _mock_request(xff: str | None = None, client_host: str | None = "127.0.0.1"):
    """Build a minimal mock Request with optional X-Forwarded-For header."""
    req = MagicMock()
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    req.headers = headers
    if client_host:
        req.client = MagicMock(host=client_host)
    else:
        req.client = None
    return req


def test_xff_ignored_without_trusted_proxy(monkeypatch):
    """Without trusted proxies configured, XFF is ignored entirely."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "")
    req = _mock_request(xff="203.0.113.5", client_host="198.51.100.10")
    assert get_client_ip(req) == "198.51.100.10"


def test_spoofed_xff_from_untrusted_peer_is_ignored(monkeypatch):
    """A direct client cannot influence effective IP with a spoofed XFF header."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "10.0.0.0/24")
    req = _mock_request(xff="10.0.0.42", client_host="198.51.100.10")
    assert get_client_ip(req) == "198.51.100.10"


def test_trusted_proxy_uses_forwarded_client_ip(monkeypatch):
    """If the immediate peer is trusted, the first non-trusted hop becomes the client."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "10.0.0.0/24")
    req = _mock_request(xff="203.0.113.5", client_host="10.0.0.20")
    assert get_client_ip(req) == "203.0.113.5"


def test_trusted_proxy_chain_returns_first_untrusted_hop(monkeypatch):
    """Multiple trusted proxies are stripped from the right side of the chain."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "10.0.0.0/24")
    req = _mock_request(
        xff="198.51.100.1, 10.0.0.11",
        client_host="10.0.0.12",
    )
    assert get_client_ip(req) == "198.51.100.1"


def test_xff_all_malformed_falls_to_client(monkeypatch):
    """Malformed XFF entries never override the transport peer."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "10.0.0.0/24")
    req = _mock_request(xff="not_an_ip, also_bad", client_host="10.0.0.20")
    assert get_client_ip(req) == "10.0.0.20"


def test_no_xff_uses_client_host():
    """No XFF header → request.client.host."""
    assert get_client_ip(_mock_request(xff=None, client_host="10.0.0.1")) == "10.0.0.1"


def test_no_xff_no_client_returns_unique_key():
    """No XFF, no client → per-request unique key (P2-24: not shared 'unknown')."""
    result = get_client_ip(_mock_request(xff=None, client_host=None))
    assert result.startswith("unknown-")
    # Each call should produce a distinct key
    result2 = get_client_ip(_mock_request(xff=None, client_host=None))
    assert result != result2


def test_xff_ipv6_via_trusted_proxy(monkeypatch):
    """IPv6 addresses should work in the same trusted-proxy flow."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_CIDRS", "fd00::/8")
    req = _mock_request(
        xff="2607:f8b0:4004:800::200e",
        client_host="fd00::1",
    )
    assert get_client_ip(req) == "2607:f8b0:4004:800::200e"


# ── Rate limit in-memory tests ───────────────────────────────────────


@pytest.mark.asyncio
async def test_ratelimit_in_memory(monkeypatch):
    # Ensure Redis is disabled so test exercises in-memory fallback
    monkeypatch.setattr(settings, "REDIS_URL", None)

    ip = "10.0.0.1"
    limit = 3

    # Calls within limit should pass
    for _ in range(limit):
        await check_rate_limit(ip, action="test", limit=limit, window_seconds=60)

    # Next call should raise HTTPException (429)
    with pytest.raises(Exception) as excinfo:
        await check_rate_limit(ip, action="test", limit=limit, window_seconds=60)

    # Ensure it's a FastAPI HTTPException with 429 status
    err = excinfo.value
    assert hasattr(err, "status_code") and err.status_code == 429


@pytest.mark.asyncio
async def test_ratelimit_uses_lua_eval_not_pipeline(monkeypatch):
    """P1-01: Redis path must use Lua eval (atomic) instead of pipeline INCR+EXPIRE."""
    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(return_value=1)  # first call, under limit

    with patch("app.core.ratelimit._get_redis_async", new=AsyncMock(return_value=mock_redis)):
        await check_rate_limit("10.0.0.2", action="lua_test", limit=5, window_seconds=30)

    # eval was called with the Lua script and the correct args
    mock_redis.eval.assert_awaited_once_with(_RATELIMIT_LUA, 1, "ratelimit:lua_test:10.0.0.2", 30)
    # pipeline must NOT be called
    mock_redis.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_ratelimit_lua_blocks_when_over_limit(monkeypatch):
    """P1-01: 429 raised when Lua returns value > limit."""
    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(return_value=6)  # exceeds limit of 5

    with patch("app.core.ratelimit._get_redis_async", new=AsyncMock(return_value=mock_redis)):
        with pytest.raises(Exception) as excinfo:
            await check_rate_limit("10.0.0.3", action="lua_block", limit=5, window_seconds=30)

    assert excinfo.value.status_code == 429


# ── E2E bypass tests ─────────────────────────────────────────────────


def _mock_request_with_bypass(secret: str, client_host: str = "127.0.0.1"):
    """Build a mock Request carrying the X-E2E-Bypass header."""
    req = MagicMock()
    headers = {"x-e2e-bypass": secret}
    req.headers = headers
    if client_host:
        req.client = MagicMock(host=client_host)
    else:
        req.client = None
    return req


@pytest.mark.asyncio
async def test_e2e_bypass_skips_rate_limit(monkeypatch):
    """When E2E secret matches and env is dev, rate limit is skipped entirely."""
    monkeypatch.setattr(settings, "E2E_RATE_LIMIT_BYPASS_SECRET", "test-secret-123")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "REDIS_URL", None)

    req = _mock_request_with_bypass("test-secret-123")

    # Should NOT raise even after exceeding the limit
    for _ in range(20):
        await check_rate_limit("10.0.0.99", action="e2e_bypass_test", limit=1, window_seconds=60, request=req)


@pytest.mark.asyncio
async def test_e2e_bypass_blocked_in_production(monkeypatch):
    """Bypass must NEVER work in production, even with correct secret."""
    monkeypatch.setattr(settings, "E2E_RATE_LIMIT_BYPASS_SECRET", "test-secret-123")
    monkeypatch.setattr(settings, "APP_ENV", "production")

    # Use a mock Redis that tracks calls to prove bypass didn't skip the check
    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(return_value=6)  # exceeds limit=5

    req = _mock_request_with_bypass("test-secret-123")

    with patch("app.core.ratelimit._get_redis_async", new=AsyncMock(return_value=mock_redis)):
        with pytest.raises(Exception) as excinfo:
            await check_rate_limit("10.0.0.100", action="e2e_prod_test", limit=5, window_seconds=60, request=req)

    # Bypass was NOT honoured — the rate limit still enforced
    assert excinfo.value.status_code == 429
    mock_redis.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_e2e_bypass_wrong_secret_still_rate_limited(monkeypatch):
    """Wrong header value should not bypass rate limit."""
    monkeypatch.setattr(settings, "E2E_RATE_LIMIT_BYPASS_SECRET", "correct-secret")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "REDIS_URL", None)

    req = _mock_request_with_bypass("wrong-secret")

    await check_rate_limit("10.0.0.101", action="e2e_wrong_test", limit=1, window_seconds=60, request=req)

    with pytest.raises(Exception) as excinfo:
        await check_rate_limit("10.0.0.101", action="e2e_wrong_test", limit=1, window_seconds=60, request=req)
    assert excinfo.value.status_code == 429


@pytest.mark.asyncio
async def test_e2e_bypass_no_secret_configured_still_rate_limited(monkeypatch):
    """When E2E secret is empty, bypass header is ignored."""
    monkeypatch.setattr(settings, "E2E_RATE_LIMIT_BYPASS_SECRET", "")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "REDIS_URL", None)

    req = _mock_request_with_bypass("any-value")

    await check_rate_limit("10.0.0.102", action="e2e_empty_test", limit=1, window_seconds=60, request=req)

    with pytest.raises(Exception) as excinfo:
        await check_rate_limit("10.0.0.102", action="e2e_empty_test", limit=1, window_seconds=60, request=req)
    assert excinfo.value.status_code == 429
