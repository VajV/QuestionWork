"""Shared Redis client helpers.

Provides a small cached wrapper around redis.asyncio so hot paths like rate
limiting, refresh token storage, and readiness checks do not create a new
client on every request.

P0-04 FIX: asyncio.Lock for init, health-check ping on cached client,
automatic reconnect on stale connections, structured logging.
"""

from __future__ import annotations

import asyncio
import logging
import time

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None
_last_connect_failure_at = 0.0
_RETRY_COOLDOWN_SECONDS = 5.0
_init_lock: asyncio.Lock | None = None


def _get_init_lock() -> asyncio.Lock:
    """Lazily create the init lock bound to the current event loop."""
    global _init_lock
    if _init_lock is None:
        _init_lock = asyncio.Lock()
    return _init_lock


def get_arq_redis_url() -> str:
    """Return the Redis URL used by the ARQ worker/scheduler runtime."""
    return (settings.ARQ_REDIS_URL or settings.REDIS_URL).strip()


def _is_production_env() -> bool:
    return settings.APP_ENV.lower() in {"production", "prod"}


async def get_redis_client(*, required_in_production: bool = False) -> aioredis.Redis | None:
    """Return a cached async Redis client, or ``None`` if Redis is unavailable.

    Improvements over the original implementation:
    - Health-check ping on the cached client; reconnect on failure.
    - asyncio.Lock to prevent concurrent initialization races.
    - max_connections=50 on the connection pool.
    - Structured logging for connection lifecycle events.
    """
    global _redis_client, _last_connect_failure_at

    # Fast path: cached client with health check
    if _redis_client is not None:
        try:
            await _redis_client.ping()
            return _redis_client
        except Exception:
            logger.warning("Redis connection lost, attempting reconnect")
            try:
                await _redis_client.aclose()
            except Exception:
                pass
            _redis_client = None

    lock = _get_init_lock()
    async with lock:
        # Double-check after acquiring lock
        if _redis_client is not None:
            try:
                await _redis_client.ping()
                return _redis_client
            except Exception:
                logger.warning("Redis connection lost (post-lock), attempting reconnect")
                try:
                    await _redis_client.aclose()
                except Exception:
                    pass
                _redis_client = None

        redis_url = settings.REDIS_URL.strip() if settings.REDIS_URL else ""

        if not redis_url:
            if required_in_production and _is_production_env():
                raise RuntimeError(
                    "Redis is required in production but REDIS_URL is not configured."
                )
            return None

        now = time.monotonic()
        if now - _last_connect_failure_at < _RETRY_COOLDOWN_SECONDS:
            if required_in_production and _is_production_env():
                raise RuntimeError(
                    "Redis is not available but required in production (cooldown). "
                    "Check REDIS_URL and ensure Redis is running."
                )
            return None

        try:
            client = aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=3,
                retry_on_timeout=True,
                max_connections=50,
            )
            await client.ping()
            _redis_client = client
            logger.info("Redis connected successfully to %s", redis_url.split("@")[-1])
            return client
        except Exception:
            _last_connect_failure_at = now
            _redis_client = None
            logger.error("Redis connection failed", exc_info=True)
            if required_in_production and _is_production_env():
                raise RuntimeError(
                    "Redis is not available but required in production. "
                    "Check REDIS_URL and ensure Redis is running."
                )
            return None


async def close_redis_client() -> None:
    """Close the cached Redis client if one was created."""
    global _redis_client, _last_connect_failure_at

    if _redis_client is None:
        return

    try:
        await _redis_client.aclose()
        logger.info("Redis client closed cleanly")
    except Exception:
        logger.debug("Failed to close Redis client cleanly", exc_info=True)
    finally:
        _redis_client = None
        _last_connect_failure_at = 0.0
