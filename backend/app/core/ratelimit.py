"""
Redis-backed rate limiter with in-memory fallback.

Comments in Russian; code and error messages in English for consistency.
"""

from typing import Optional
import time
import logging

import redis as redis_lib
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger("questionwork.ratelimit")

# Simple in-memory fallback store: {key: [timestamps]}
_IN_MEMORY_ATTEMPTS = {}


def _get_redis():
    if not settings.REDIS_URL:
        return None
    try:
        client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception:
        logger.debug("Redis not available for rate limiting; using in-memory fallback")
        return None


def check_rate_limit(ip: str, action: str = "global", limit: int = 10, window_seconds: int = 300) -> None:
    """Check and enforce a rate limit for the given IP and action.

    Raises HTTPException(429) when the limit is exceeded.
    Uses Redis INCR with expiry for atomic increments across processes. Falls back
    to an in-memory sliding window when Redis is not available.
    """
    if not ip:
        ip = "unknown"

    key = f"ratelimit:{action}:{ip}"
    client = _get_redis()
    if client:
        try:
            # INCR returns the new value; set expiry when value == 1
            val = client.incr(key)
            if val == 1:
                client.expire(key, window_seconds)
            if val > limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests",
                )
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}; falling back to memory")

    # In-memory fallback: store timestamps and evict old ones
    now = time.time()
    attempts = _IN_MEMORY_ATTEMPTS.get(key, [])
    attempts = [t for t in attempts if now - t < window_seconds]
    attempts.append(now)
    _IN_MEMORY_ATTEMPTS[key] = attempts
    if len(attempts) > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )
