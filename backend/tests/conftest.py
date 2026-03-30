"""Shared test fixtures for the QuestionWork test suite."""

import pytest


@pytest.fixture(autouse=True)
def _clear_rate_limit_store():
    """Clear the in-memory rate-limit store, Redis rate-limit keys, and badge cache before each test."""
    from app.core.ratelimit import _IN_MEMORY_ATTEMPTS
    from app.services import badge_service

    _IN_MEMORY_ATTEMPTS.clear()
    badge_service._BADGE_CACHE = None
    badge_service._BADGE_CACHE_TS = 0.0

    # Also flush Redis rate-limit keys so they don't leak between tests.
    # Use a temporary sync Redis client since this fixture runs in both
    # sync and async test contexts.
    try:
        from app.core.config import settings
        redis_url = (settings.REDIS_URL or "").strip()
        if redis_url:
            import redis as _sync_redis
            _tmp = _sync_redis.from_url(redis_url, decode_responses=True)
            for key in _tmp.scan_iter("ratelimit:*"):
                _tmp.delete(key)
            for key in _tmp.scan_iter("totp_used:*"):
                _tmp.delete(key)
            _tmp.close()
    except Exception:
        pass

    yield

    _IN_MEMORY_ATTEMPTS.clear()
    badge_service._BADGE_CACHE = None
    badge_service._BADGE_CACHE_TS = 0.0
