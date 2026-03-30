"""
Redis-backed rate limiter with in-memory fallback.

Comments in Russian; code and error messages in English for consistency.

Supports both IP-based and user-based rate limiting. For authenticated
endpoints, use await check_user_rate_limit() as a complementary layer to
prevent abuse via IP rotation.
"""

import ipaddress
import time
import uuid
import logging

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.redis_client import get_redis_client

logger = logging.getLogger("questionwork.ratelimit")

# Simple in-memory fallback store: {key: [timestamps]}
_IN_MEMORY_ATTEMPTS: dict[str, list[float]] = {}
# Cap the number of tracked keys to prevent unbounded memory growth.
_MAX_IN_MEMORY_KEYS = 10_000


def _parse_ip(value: str | None):
    if not value:
        return None
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _parse_network_entries(raw_value: str) -> list[ipaddress._BaseNetwork | ipaddress._BaseAddress]:
    entries: list[ipaddress._BaseNetwork | ipaddress._BaseAddress] = []
    for part in [item.strip() for item in raw_value.split(",") if item.strip()]:
        try:
            entries.append(ipaddress.ip_network(part, strict=False))
            continue
        except ValueError:
            pass

        parsed_ip = _parse_ip(part)
        if parsed_ip is not None:
            entries.append(parsed_ip)
    return entries


def _ip_matches_entries(ip_value: str | None, raw_entries: str) -> bool:
    parsed_ip = _parse_ip(ip_value)
    if parsed_ip is None:
        return False

    for entry in _parse_network_entries(raw_entries):
        if isinstance(entry, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            if parsed_ip == entry:
                return True
            continue
        if parsed_ip in entry:
            return True
    return False


def is_trusted_proxy(ip_value: str | None) -> bool:
    trusted_raw = (settings.TRUSTED_PROXY_CIDRS or "").strip()
    if not trusted_raw:
        return False
    return _ip_matches_entries(ip_value, trusted_raw)


def ip_matches_allowlist(ip_value: str | None, allowlist_raw: str) -> bool:
    return _ip_matches_entries(ip_value, allowlist_raw)


def get_client_ip(request: Request) -> str:
    """Resolve the effective client IP using trusted proxy rules.

    X-Forwarded-For is ignored unless the immediate peer is in TRUSTED_PROXY_CIDRS.
    When trusted proxies are configured, the function walks the XFF chain from right
    to left and returns the first non-trusted hop.
    """
    peer_ip = request.client.host if request.client else None
    if not peer_ip:
        # P2-24: per-request unique key instead of shared "unknown" bucket
        return f"unknown-{uuid.uuid4().hex[:12]}"

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded or not is_trusted_proxy(peer_ip):
        return peer_ip

    forwarded_chain = [candidate.strip() for candidate in forwarded.split(",") if _parse_ip(candidate.strip())]
    if not forwarded_chain:
        return peer_ip

    full_chain = forwarded_chain + [peer_ip]
    for candidate in reversed(full_chain):
        if not is_trusted_proxy(candidate):
            return candidate
    return full_chain[0]


def get_admin_request_ip(request: Request) -> str:
    """Return the IP that should be checked against ADMIN_IP_ALLOWLIST."""
    return get_client_ip(request)


def _get_redis():
    """Marker for callers — actual Redis access is async now."""
    return None


async def _get_redis_async():
    client = await get_redis_client()
    if client is None and settings.REDIS_URL:
        logger.debug("Redis not available for rate limiting; using in-memory fallback")
    return client


# Atomic Lua script: INCR the key, set EXPIRE only on first call (cur==1).
# This prevents window extension from repeated EXPIRE calls in a non-atomic pipeline.
# P1-01 FIX: was pipe.incr(key) + pipe.expire(key, ...) — not atomic.
_RATELIMIT_LUA = """
local cur = redis.call('INCR', KEYS[1])
if cur == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
return cur
"""


def _e2e_bypass_allowed(request: Request) -> bool:
    """Return True when the request carries a valid E2E bypass header.

    Bypass is only honoured when:
    1. APP_ENV is NOT production.
    2. E2E_RATE_LIMIT_BYPASS_SECRET is set (non-empty).
    3. The request header X-E2E-Bypass matches the secret exactly.
    """
    secret = settings.E2E_RATE_LIMIT_BYPASS_SECRET
    if not secret:
        return False
    if settings.APP_ENV.lower() in ("production", "prod"):
        return False
    header_value = request.headers.get("x-e2e-bypass", "")
    if not header_value:
        return False
    return header_value == secret


async def check_rate_limit(
    ip: str,
    action: str = "global",
    limit: int = 10,
    window_seconds: int = 300,
    *,
    request: Request | None = None,
) -> None:
    """Check and enforce a rate limit for the given IP and action.

    Raises HTTPException(429) when the limit is exceeded.
    Uses a Redis Lua script for an atomic INCR+EXPIRE that never resets the
    window on repeated calls. Falls back to an in-memory sliding window when
    Redis is not available.

    If E2E_RATE_LIMIT_BYPASS_SECRET is configured (non-production only) and the
    request carries a matching X-E2E-Bypass header, the check is skipped.
    """
    if request is not None and _e2e_bypass_allowed(request):
        return

    if not ip:
        ip = "unknown"

    key = f"ratelimit:{action}:{ip}"
    client = await _get_redis_async()
    if client:
        try:
            val = await client.eval(_RATELIMIT_LUA, 1, key, window_seconds)
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

    # In production, refuse to degrade to per-process memory — it can be bypassed
    # across workers.  Return 503 so the caller knows the service is degraded.
    if settings.APP_ENV.lower() in ("production", "prod"):
        logger.error("Rate limiter: Redis unavailable in production — rejecting request")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate-limit service temporarily unavailable",
        )

    # In-memory fallback: store timestamps and evict old ones
    now = time.time()
    attempts = _IN_MEMORY_ATTEMPTS.get(key, [])
    attempts = [t for t in attempts if now - t < window_seconds]
    attempts.append(now)
    _IN_MEMORY_ATTEMPTS[key] = attempts

    # Evict stale keys if the store grows too large — single-pass O(n)
    if len(_IN_MEMORY_ATTEMPTS) > _MAX_IN_MEMORY_KEYS:
        cutoff = now - window_seconds * 2
        stale = [k for k, ts_list in _IN_MEMORY_ATTEMPTS.items() if not ts_list or ts_list[-1] < cutoff]
        for stale_key in stale:
            _IN_MEMORY_ATTEMPTS.pop(stale_key, None)

    if len(attempts) > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
        )


async def check_user_rate_limit(
    user_id: str, action: str = "global", limit: int = 10, window_seconds: int = 300
) -> None:
    """User-based rate limit complementing IP-based check_rate_limit.

    Call this for authenticated financial/mutation endpoints to prevent
    abuse via IP rotation behind NAT/VPN.
    """
    await check_rate_limit(f"user:{user_id}", action=action, limit=limit, window_seconds=window_seconds)
