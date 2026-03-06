"""
Модуль безопасности
JWT токены, хеширование паролей, TOTP encryption

Используем bcrypt напрямую для совместимости
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
import bcrypt
import base64
import hashlib
import logging
import secrets
import json
from typing import Tuple

import redis as redis_lib

from app.core.config import settings

logger = logging.getLogger(__name__)

# In-memory fallback store for refresh tokens (token -> user_id, exp)
_IN_MEMORY_REFRESH_STORE = {}
_IN_MEMORY_MAX_TOKENS = 10_000


def _get_redis_client():
    """Return a Redis client or None if REDIS_URL is not set or connection fails."""
    if not settings.REDIS_URL:
        if settings.APP_ENV.lower() == "production":
            raise RuntimeError(
                "Redis is required in production for refresh token storage. "
                "Set REDIS_URL in your environment."
            )
        return None
    try:
        client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        # simple ping to validate connection
        client.ping()
        return client
    except Exception:
        if settings.APP_ENV.lower() == "production":
            raise RuntimeError(
                "Redis is not available but required in production. "
                "Check REDIS_URL and ensure Redis is running."
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
    
    to_encode.update({"exp": expire})
    
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
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {e}")
        return None


# Refresh token helpers
def create_refresh_token(user_id: str) -> Tuple[str, int]:
    """Create a refresh token, store it (Redis if available), and return (token, expires_seconds).

    Returns a tuple of token string and expiration in seconds.
    """
    token = secrets.token_urlsafe(48)
    expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expires_seconds = int(expires.total_seconds())

    client = _get_redis_client()
    key = f"refresh:{token}"
    if client:
        client.set(key, user_id, ex=expires_seconds)
    else:
        # Evict oldest 25% if at capacity (I-10: log eviction)
        if len(_IN_MEMORY_REFRESH_STORE) >= _IN_MEMORY_MAX_TOKENS:
            evict_count = _IN_MEMORY_MAX_TOKENS // 4
            sorted_tokens = sorted(
                _IN_MEMORY_REFRESH_STORE.items(), key=lambda x: x[1].get("exp", 0)
            )
            for tok, _ in sorted_tokens[:evict_count]:
                _IN_MEMORY_REFRESH_STORE.pop(tok, None)
            logger.warning(
                "In-memory refresh token store at capacity (%d). Evicted %d oldest tokens.",
                _IN_MEMORY_MAX_TOKENS,
                evict_count,
            )
        exp_ts = int((datetime.now(timezone.utc) + expires).timestamp())
        _IN_MEMORY_REFRESH_STORE[token] = {"user_id": user_id, "exp": exp_ts}

    return token, expires_seconds


def verify_refresh_token(token: str) -> Optional[str]:
    """Verify a refresh token and return associated user_id if valid, else None."""
    if not token:
        return None
    client = _get_redis_client()
    key = f"refresh:{token}"
    if client:
        try:
            user_id = client.get(key)
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
        return entry.get("user_id")


def revoke_refresh_token(token: str) -> None:
    """Revoke/delete a refresh token from storage."""
    if not token:
        return
    client = _get_redis_client()
    key = f"refresh:{token}"
    if client:
        try:
            client.delete(key)
        except Exception:
            logger.warning("Failed to delete refresh token from Redis")
    else:
        _IN_MEMORY_REFRESH_STORE.pop(token, None)


# ── TOTP secret encryption (I-07) ─────────────────────────────────────────

def _totp_fernet_key() -> bytes:
    """Derive a 32-byte Fernet key from SECRET_KEY via SHA-256."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_totp_secret(plain_secret: str) -> str:
    """Encrypt a TOTP secret for storage in the database."""
    from cryptography.fernet import Fernet
    f = Fernet(_totp_fernet_key())
    return f.encrypt(plain_secret.encode("utf-8")).decode("utf-8")


def decrypt_totp_secret(encrypted_secret: str) -> str:
    """Decrypt a TOTP secret retrieved from the database.

    If decryption fails (e.g., legacy plaintext secret), returns the
    input as-is so existing unencrypted secrets still work during migration.
    """
    from cryptography.fernet import Fernet, InvalidToken
    try:
        f = Fernet(_totp_fernet_key())
        return f.decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        # Graceful fallback: treat as plaintext (pre-encryption secret)
        return encrypted_secret
