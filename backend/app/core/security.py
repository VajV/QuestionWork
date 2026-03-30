"""
Модуль безопасности
JWT токены, хеширование паролей, TOTP encryption

Используем bcrypt напрямую для совместимости
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from jwt.exceptions import PyJWTError
import bcrypt
import base64
import hashlib
import logging
import secrets
import json
import asyncio
from collections import OrderedDict
from typing import Tuple

from app.core.config import settings
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

ACCESS_TOKEN_ISSUER = "questionwork"
ACCESS_TOKEN_AUDIENCE = "questionwork-api"

# In-memory refresh-token store for non-production fallback (token -> user_id, exp).
# Uses OrderedDict for true LRU eviction — most-recently-used tokens are moved to end.
# Dev/staging only — production requires Redis (see _refresh_store_requires_redis).
_IN_MEMORY_REFRESH_STORE: OrderedDict[str, dict] = OrderedDict()
_IN_MEMORY_MAX_TOKENS = 10_000
_refresh_store_lock = asyncio.Lock()


class RefreshTokenStoreUnavailableError(RuntimeError):
    """Raised when refresh-token storage is unavailable in environments requiring Redis."""


def _refresh_store_requires_redis() -> bool:
    return settings.APP_ENV.lower() in {"production", "prod"}


async def _get_refresh_store_client():
    """Return the refresh-token store client or raise if production shared state is unavailable."""
    client = await get_redis_client(required_in_production=False)
    if client is not None:
        return client

    if _refresh_store_requires_redis():
        raise RefreshTokenStoreUnavailableError(
            "Refresh token storage is unavailable."
        )

    logger.warning("Redis is not available; using in-memory refresh token store")
    return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверка пароля
    
    Args:
        plain_password: Пароль в открытом виде
        hashed_password: Хешированный пароль из БД
    
    Returns:
        True если пароль верный
    """
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """
    Хеширование пароля
    
    Args:
        password: Пароль в открытом виде
    
    Returns:
        Хешированный пароль
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создание JWT access токена
    
    Args:
        data: Данные для кодирования (обычно {"sub": user_id})
        expires_delta: Время жизни токена
    
    Returns:
        JWT токен в формате строки
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    
    now = datetime.now(timezone.utc)
    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "iss": ACCESS_TOKEN_ISSUER,
            "aud": ACCESS_TOKEN_AUDIENCE,
        }
    )
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Декодирование JWT токена
    
    Args:
        token: JWT токен
    
    Returns:
        decoded данные или None если токен невалидный
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=ACCESS_TOKEN_ISSUER,
            audience=ACCESS_TOKEN_AUDIENCE,
        )
        return payload
    except PyJWTError as e:
        logger.warning("Invalid JWT token")
        return None
    except Exception as e:
        logger.error("Unexpected error decoding token: %s", type(e).__name__)
        return None


# Refresh token helpers
async def create_refresh_token(user_id: str) -> Tuple[str, int]:
    """Create a refresh token, store it (Redis if available), and return (token, expires_seconds).

    Returns a tuple of token string and expiration in seconds.
    """
    token = secrets.token_urlsafe(48)
    expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expires_seconds = int(expires.total_seconds())

    client = await _get_refresh_store_client()
    key = f"refresh:{token}"
    if client:
        await client.set(key, user_id, ex=expires_seconds)
    else:
        # Evict expired tokens first, then LRU if still at capacity
        if len(_IN_MEMORY_REFRESH_STORE) >= _IN_MEMORY_MAX_TOKENS:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            expired_keys = [
                k for k, v in _IN_MEMORY_REFRESH_STORE.items()
                if v.get("exp", 0) <= now_ts
            ]
            for k in expired_keys:
                _IN_MEMORY_REFRESH_STORE.pop(k, None)
            if expired_keys:
                logger.info("Pruned %d expired refresh tokens.", len(expired_keys))
            # If still at capacity after pruning expired, evict LRU
            if len(_IN_MEMORY_REFRESH_STORE) >= _IN_MEMORY_MAX_TOKENS:
                evict_count = _IN_MEMORY_MAX_TOKENS // 4
                for _ in range(min(evict_count, len(_IN_MEMORY_REFRESH_STORE))):
                    _IN_MEMORY_REFRESH_STORE.popitem(last=False)
                logger.warning(
                    "In-memory refresh token store at capacity (%d). Evicted %d oldest tokens.",
                    _IN_MEMORY_MAX_TOKENS,
                    evict_count,
                )
        exp_ts = int((datetime.now(timezone.utc) + expires).timestamp())
        _IN_MEMORY_REFRESH_STORE[token] = {"user_id": user_id, "exp": exp_ts}

    return token, expires_seconds


async def verify_refresh_token(token: str) -> Optional[str]:
    """Verify a refresh token and return associated user_id if valid, else None."""
    if not token:
        return None
    client = await _get_refresh_store_client()
    key = f"refresh:{token}"
    if client:
        try:
            user_id = await client.get(key)
            return user_id
        except Exception:
            return None
    else:
        entry = _IN_MEMORY_REFRESH_STORE.get(token)
        if not entry:
            return None
        if entry.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
            # expired
            _IN_MEMORY_REFRESH_STORE.pop(token, None)
            return None
        # LRU touch: move to end so it's evicted last
        _IN_MEMORY_REFRESH_STORE.move_to_end(token)
        return entry.get("user_id")


async def revoke_refresh_token(token: str) -> None:
    """Revoke/delete a refresh token from storage."""
    if not token:
        return
    client = await _get_refresh_store_client()
    key = f"refresh:{token}"
    if client:
        try:
            await client.delete(key)
        except Exception:
            logger.warning("Failed to delete refresh token from Redis")
    else:
        _IN_MEMORY_REFRESH_STORE.pop(token, None)


async def rotate_refresh_token(old_token: str) -> Tuple[Optional[str], Optional[str], int]:
    """Atomically verify old token, revoke it, and issue a new one.

    Returns (user_id, new_token, expires_seconds).
    If old_token is invalid/expired/already consumed, returns (None, None, 0).
    """
    if not old_token:
        return None, None, 0

    client = await _get_refresh_store_client()
    if client:
        # Redis: use pipeline for atomic GET+DELETE
        key = f"refresh:{old_token}"
        try:
            pipe = client.pipeline(True)
            pipe.get(key)
            pipe.delete(key)
            results = await pipe.execute()
            user_id = results[0]
        except Exception:
            return None, None, 0
        if not user_id:
            return None, None, 0
        new_token, expires_seconds = await create_refresh_token(user_id)
        return user_id, new_token, expires_seconds
    else:
        # In-memory: use async lock for atomicity (P2-01)
        async with _refresh_store_lock:
            entry = _IN_MEMORY_REFRESH_STORE.pop(old_token, None)
        if not entry:
            return None, None, 0
        if entry.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
            return None, None, 0
        user_id = entry.get("user_id")
        if not user_id:
            return None, None, 0
        new_token, expires_seconds = await create_refresh_token(user_id)
        return user_id, new_token, expires_seconds


# ── TOTP secret encryption (I-07) ─────────────────────────────────────────

def _totp_fernet_key() -> bytes:
    """Derive a 32-byte Fernet key from TOTP_ENCRYPTION_KEY using PBKDF2 (P1-03)."""
    source = settings.TOTP_ENCRYPTION_KEY or settings.SECRET_KEY
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        source.encode("utf-8"),
        b"totp_encryption",
        iterations=600_000,
    )
    return base64.urlsafe_b64encode(dk)


def _totp_fernet_key_legacy() -> bytes:
    """Legacy key derivation (SHA-256) for migration of existing encrypted secrets."""
    source = settings.TOTP_ENCRYPTION_KEY or settings.SECRET_KEY
    digest = hashlib.sha256(b"totp_encryption:" + source.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_totp_secret(plain_secret: str) -> str:
    """Encrypt a TOTP secret for storage in the database."""
    from cryptography.fernet import Fernet
    f = Fernet(_totp_fernet_key())
    return f.encrypt(plain_secret.encode("utf-8")).decode("utf-8")


def decrypt_totp_secret(encrypted_secret: str) -> str:
    """Decrypt a TOTP secret retrieved from the database.

    Tries the new PBKDF2-derived key first; falls back to legacy SHA-256 key
    for secrets encrypted before the P1-03 migration.

    Raises ValueError if decryption fails with both keys.
    """
    from cryptography.fernet import Fernet, InvalidToken

    # Try new (PBKDF2) key first
    try:
        f = Fernet(_totp_fernet_key())
        return f.decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        pass

    # Fallback to legacy (SHA-256) key
    try:
        f_legacy = Fernet(_totp_fernet_key_legacy())
        return f_legacy.decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt TOTP secret with both new and legacy keys")
        raise ValueError(
            "TOTP secret decryption failed. "
            "Re-enrol TOTP to generate a properly encrypted secret."
        )
