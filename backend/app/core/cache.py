"""Best-effort Redis response cache for read-heavy service functions.

Usage::

    from app.core.cache import redis_cache, invalidate_cache

    @redis_cache(ttl_seconds=300, key_prefix="badges")
    async def get_all_badges(conn, ...) -> list[dict]:
        ...

    # Invalidate after mutation:
    await invalidate_cache("badges")

If Redis is unavailable the decorator falls through to the wrapped function
without raising.  Only JSON-serializable return values are cached.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
from typing import Any, Callable

from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

_CACHE_KEY_NS = "qw:cache:"


def _build_key(prefix: str, args: tuple, kwargs: dict, scope: str | None = None) -> str:
    """Deterministic cache key from prefix + hashable call arguments.

    Skip ``asyncpg.Connection`` (first positional arg in service layer) and
    any non-serializable objects.
    """
    parts: list[str] = []
    for a in args:
        if hasattr(a, "fetchrow"):  # asyncpg.Connection — skip
            continue
        parts.append(str(a))
    for k in sorted(kwargs):
        v = kwargs[k]
        if hasattr(v, "fetchrow"):
            continue
        parts.append(f"{k}={v}")
    raw = "|".join(parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    scope_prefix = f"{scope}:" if scope else ""
    return f"{_CACHE_KEY_NS}{prefix}:{scope_prefix}{digest}"


async def _delete_matching_keys(pattern: str) -> int:
    redis = await get_redis_client()
    if redis is None:
        return 0

    deleted = 0
    try:
        async for key in redis.scan_iter(match=pattern, count=100):
            await redis.delete(key)
            deleted += 1
    except Exception:
        logger.debug("Redis cache invalidation failed for %s", pattern, exc_info=True)
    return deleted


def redis_cache(
    ttl_seconds: int = 300,
    key_prefix: str = "default",
    scope_builder: Callable[..., str | None] | None = None,
) -> Callable:
    """Decorator that caches the return value in Redis for ``ttl_seconds``."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            redis = await get_redis_client()
            if redis is None:
                return await fn(*args, **kwargs)

            scope = scope_builder(*args, **kwargs) if scope_builder else None
            if scope is not None:
                scope = str(scope).strip() or None
            key = _build_key(key_prefix, args, kwargs, scope)

            # Try to read from cache
            try:
                cached = await redis.get(key)
                if cached is not None:
                    return json.loads(cached)
            except Exception:
                logger.debug("Redis cache read failed for %s", key, exc_info=True)

            # Cache miss — call real function
            result = await fn(*args, **kwargs)

            # Write to cache (best-effort)
            try:
                await redis.set(key, json.dumps(result, default=str), ex=ttl_seconds)
            except Exception:
                logger.debug("Redis cache write failed for %s", key, exc_info=True)

            return result

        return wrapper

    return decorator


async def invalidate_cache(prefix: str) -> int:
    """Delete all cache keys matching a prefix. Returns count deleted."""
    pattern = f"{_CACHE_KEY_NS}{prefix}:*"
    return await _delete_matching_keys(pattern)


async def invalidate_cache_scope(prefix: str, *scope_parts: str) -> int:
    """Delete cache keys for a semantic scope within a prefix.

    Example:
        await invalidate_cache_scope("user_rating", "user", user_id)
    """
    scope = ":".join(str(part).strip() for part in scope_parts if str(part).strip())
    if not scope:
        return await invalidate_cache(prefix)
    pattern = f"{_CACHE_KEY_NS}{prefix}:{scope}:*"
    return await _delete_matching_keys(pattern)
