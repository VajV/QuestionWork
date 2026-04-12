"""Referral service — referral codes, tracking, and reward grants."""

from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.services import notification_service

logger = logging.getLogger(__name__)

_CODE_CHARS = string.ascii_uppercase + string.digits
_CODE_LEN = 8


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_CHARS) for _ in range(_CODE_LEN))


async def get_or_create_referral_code(conn: asyncpg.Connection, user_id: str) -> str:
    """Return existing referral code or create a new one. Idempotent."""
    existing = await conn.fetchval(
        "SELECT code FROM referrals WHERE referrer_id = $1 AND referred_id IS NULL LIMIT 1",
        user_id,
    )
    if existing:
        return str(existing)

    now = datetime.now(timezone.utc)
    for _ in range(5):
        code = _generate_code()
        ref_id = f"ref_{secrets.token_hex(8)}"
        try:
            await conn.execute(
                """
                INSERT INTO referrals (id, referrer_id, code, created_at)
                VALUES ($1, $2, $3, $4)
                """,
                ref_id, user_id, code, now,
            )
            return code
        except asyncpg.UniqueViolationError:
            continue
    raise ValueError("Failed to generate a unique referral code — try again later")


async def apply_referral_code(
    conn: asyncpg.Connection,
    referred_user_id: str,
    code: str,
) -> dict:
    """Link a referral code to a newly-registered user."""
    row = await conn.fetchrow(
        "SELECT id, referrer_id FROM referrals WHERE code = $1 AND referred_id IS NULL FOR UPDATE",
        code.upper().strip(),
    )
    if not row:
        raise ValueError("Referral code is invalid or already used")

    if row["referrer_id"] == referred_user_id:
        raise ValueError("You cannot use your own referral code")

    now = datetime.now(timezone.utc)
    await conn.execute(
        "UPDATE referrals SET referred_id = $1, referred_at = $2 WHERE id = $3",
        referred_user_id, now, row["id"],
    )

    # Create a fresh code for the referrer so they can keep referring
    new_ref_id = f"ref_{secrets.token_hex(8)}"
    new_code = _generate_code()
    await conn.execute(
        "INSERT INTO referrals (id, referrer_id, code, created_at) VALUES ($1, $2, $3, $4)",
        new_ref_id, row["referrer_id"], new_code, now,
    )

    return {"referrer_id": row["referrer_id"], "applied": True}


async def grant_referral_rewards(
    conn: asyncpg.Connection,
    referred_user_id: str,
    *,
    referrer_xp: int = 200,
    referred_xp: int = 100,
) -> Optional[dict]:
    """Grant XP to both referrer and referred user after first quest confirmation.

    Called once — sets reward_granted flag to avoid duplicates.
    """
    row = await conn.fetchrow(
        "SELECT id, referrer_id FROM referrals WHERE referred_id = $1 AND reward_granted = FALSE FOR UPDATE",
        referred_user_id,
    )
    if not row:
        return None

    now = datetime.now(timezone.utc)
    await conn.execute(
        "UPDATE referrals SET reward_granted = TRUE WHERE id = $1",
        row["id"],
    )

    # Grant XP to referrer
    await conn.execute(
        "UPDATE users SET xp = xp + $1, updated_at = $2 WHERE id = $3",
        referrer_xp, now, row["referrer_id"],
    )
    await notification_service.create_notification(
        conn,
        row["referrer_id"],
        title="🎁 Реферальная награда!",
        message=f"Ваш приглашённый пользователь завершил первый квест. Вы получили {referrer_xp} XP!",
        event_type="referral_reward",
    )

    # Grant XP to referred user
    await conn.execute(
        "UPDATE users SET xp = xp + $1, updated_at = $2 WHERE id = $3",
        referred_xp, now, referred_user_id,
    )
    await notification_service.create_notification(
        conn,
        referred_user_id,
        title="🎁 Реферальный бонус!",
        message=f"Вы завершили первый квест. Бонус за реферальный код: {referred_xp} XP!",
        event_type="referral_reward",
    )

    logger.info("Referral reward granted: referrer=%s, referred=%s", row["referrer_id"], referred_user_id)
    return {
        "referrer_id": row["referrer_id"],
        "referrer_xp": referrer_xp,
        "referred_xp": referred_xp,
    }


async def get_my_referral_info(conn: asyncpg.Connection, user_id: str) -> dict:
    """Get user's referral code + count of successful referrals."""
    code = await conn.fetchval(
        "SELECT code FROM referrals WHERE referrer_id = $1 AND referred_id IS NULL ORDER BY created_at DESC LIMIT 1",
        user_id,
    )
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id = $1 AND referred_id IS NOT NULL",
        user_id,
    ) or 0
    rewarded = await conn.fetchval(
        "SELECT COUNT(*) FROM referrals WHERE referrer_id = $1 AND reward_granted = TRUE",
        user_id,
    ) or 0
    return {
        "code": code,
        "total_referred": int(total),
        "rewarded_count": int(rewarded),
    }
