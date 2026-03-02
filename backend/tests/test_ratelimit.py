import pytest

from app.core.ratelimit import check_rate_limit
from app.core.config import settings


def test_ratelimit_in_memory(monkeypatch):
    # Ensure Redis is disabled so test exercises in-memory fallback
    monkeypatch.setattr(settings, "REDIS_URL", None)

    ip = "10.0.0.1"
    limit = 3

    # Calls within limit should pass
    for _ in range(limit):
        check_rate_limit(ip, action="test", limit=limit, window_seconds=60)

    # Next call should raise HTTPException (429)
    with pytest.raises(Exception) as excinfo:
        check_rate_limit(ip, action="test", limit=limit, window_seconds=60)

    # Ensure it's a FastAPI HTTPException with 429 status
    err = excinfo.value
    assert hasattr(err, "status_code") and err.status_code == 429
