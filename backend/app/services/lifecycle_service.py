"""Lifecycle CRM service — enqueue and process lifecycle nudges.

Lifecycle messages are persisted in `lifecycle_messages` with an
idempotency key so re-entrancy or re-triggered conditions never
produce duplicate sends.

Trigger patterns:
  - incomplete_profile:      user has no bio/skills N days after registration
  - incomplete_quest_draft:  quest stuck in draft status for N days
  - stale_shortlist:         client has shortlisted talent but no quest assigned
  - unreviewed_completion:   quest confirmed but client left no review
  - dormant_client:          no quest activity at 7/14/30 days after completion
  - lead_no_register:        lead captured but user never registered
  - lead_no_quest:           client registered but no quest posted
"""

import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)

# How many messages to process per batch to avoid long-running DB transactions
PROCESS_BATCH_SIZE = 50

_LifecycleTemplate = tuple[str, Callable[[dict[str, Any]], str]]

CAMPAIGN_TEMPLATES: dict[str, _LifecycleTemplate] = {
    "incomplete_profile": (
        "[QuestionWork] Дополните свой профиль",
        lambda _trigger_data: (
            "<p>Вы зарегистрировались, но ваш профиль ещё не заполнен.</p>"
            "<p><a href='__FRONTEND_URL__/profile/edit' style='color:#7c3aed;'>Заполнить профиль</a>"
            " — это займёт всего 2 минуты!</p>"
        ),
    ),
    "incomplete_quest_draft": (
        "[QuestionWork] У вас есть незавершённый квест-черновик",
        lambda trigger_data: (
            f"<p>Квест <strong>#{trigger_data.get('quest_id', '')}</strong> остался черновиком.</p>"
            "<p><a href='__FRONTEND_URL__/quests/create' style='color:#7c3aed;'>Завершить создание</a></p>"
        ),
    ),
    "stale_shortlist": (
        "[QuestionWork] Ваш шортлист ждёт действия",
        lambda _trigger_data: (
            "<p>Вы добавили фрилансеров в шортлист, но ещё не назначили квест.</p>"
            "<p><a href='__FRONTEND_URL__/shortlists' style='color:#7c3aed;'>Посмотреть шортлист</a></p>"
        ),
    ),
    "unreviewed_completion": (
        "[QuestionWork] Оцените выполненный квест",
        lambda trigger_data: (
            f"<p>Квест <strong>#{trigger_data.get('quest_id', '')}</strong> завершён, но вы ещё не оставили отзыв.</p>"
            "<p><a href='__FRONTEND_URL__/quests' style='color:#7c3aed;'>Оставить отзыв</a></p>"
        ),
    ),
    "dormant_client": (
        "[QuestionWork] Мы скучаем по вам!",
        lambda trigger_data: (
            f"<p>Прошло {trigger_data.get('days_dormant', '?')} дней с момента вашего последнего квеста.</p>"
            "<p><a href='__FRONTEND_URL__/quests/create' style='color:#7c3aed;'>Разместить новый квест</a></p>"
        ),
    ),
    "lead_no_register": (
        "[QuestionWork] Завершите регистрацию",
        lambda _trigger_data: (
            "<p>Вы оставили заявку, но так и не зарегистрировались.</p>"
            "<p><a href='__FRONTEND_URL__/auth/register' style='color:#7c3aed;'>Зарегистрироваться</a></p>"
        ),
    ),
    "lead_no_quest": (
        "[QuestionWork] Разместите свой первый квест",
        lambda _trigger_data: (
            "<p>Вы зарегистрировались как клиент, но ещё не разместили ни одного квеста.</p>"
            "<p><a href='__FRONTEND_URL__/quests/create' style='color:#7c3aed;'>Создать квест</a></p>"
        ),
    ),
}


# ── Enqueue helpers ───────────────────────────────────────────────────────────


async def enqueue(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    campaign_key: str,
    trigger_data: Optional[Dict[str, Any]] = None,
    send_after: Optional[datetime] = None,
    idempotency_key: str,
) -> bool:
    """Enqueue a lifecycle message, skipping duplicates via idempotency_key.

    Returns True if a new row was inserted, False if it was a duplicate.
    Must be called inside an existing transaction.
    """
    if not conn.is_in_transaction():
        raise RuntimeError("enqueue must be called inside an existing DB transaction.")

    now = datetime.now(timezone.utc)
    due = send_after or now

    result = await conn.execute(
        """
        INSERT INTO lifecycle_messages
            (user_id, campaign_key, trigger_data, status, send_after, idempotency_key, created_at)
        VALUES ($1, $2, $3::jsonb, 'pending', $4, $5, $6)
        ON CONFLICT (idempotency_key) DO NOTHING
        """,
        user_id,
        campaign_key,
        json.dumps(trigger_data or {}),
        due,
        idempotency_key,
        now,
    )
    # asyncpg returns "INSERT 0 N"; N=0 means conflict
    return result.endswith("1")


async def enqueue_incomplete_profile(conn: asyncpg.Connection, user_id: str) -> bool:
    key = f"incomplete_profile:{user_id}:v1"
    return await enqueue(conn, user_id=user_id, campaign_key="incomplete_profile",
                         send_after=datetime.now(timezone.utc) + timedelta(days=1),
                         idempotency_key=key)


async def enqueue_incomplete_quest_draft(conn: asyncpg.Connection, user_id: str, quest_id: str) -> bool:
    key = f"incomplete_quest_draft:{user_id}:{quest_id}:v1"
    return await enqueue(conn, user_id=user_id, campaign_key="incomplete_quest_draft",
                         trigger_data={"quest_id": quest_id},
                         send_after=datetime.now(timezone.utc) + timedelta(days=2),
                         idempotency_key=key)


async def enqueue_stale_shortlist(conn: asyncpg.Connection, user_id: str) -> bool:
    # One reminder per user per 14-day window
    window = datetime.now(timezone.utc).strftime("%Y-W%W")
    key = f"stale_shortlist:{user_id}:{window}"
    return await enqueue(conn, user_id=user_id, campaign_key="stale_shortlist",
                         send_after=datetime.now(timezone.utc) + timedelta(days=3),
                         idempotency_key=key)


async def enqueue_unreviewed_completion(conn: asyncpg.Connection, user_id: str, quest_id: str) -> bool:
    key = f"unreviewed_completion:{user_id}:{quest_id}:v1"
    return await enqueue(conn, user_id=user_id, campaign_key="unreviewed_completion",
                         trigger_data={"quest_id": quest_id},
                         send_after=datetime.now(timezone.utc) + timedelta(days=3),
                         idempotency_key=key)


async def enqueue_dormant_client(conn: asyncpg.Connection, user_id: str, *, days: int, last_quest_id: str) -> bool:
    """days should be 7, 14, or 30."""
    key = f"dormant_client:{user_id}:{last_quest_id}:d{days}"
    return await enqueue(conn, user_id=user_id, campaign_key="dormant_client",
                         trigger_data={"days_dormant": days, "last_quest_id": last_quest_id},
                         send_after=datetime.now(timezone.utc) + timedelta(days=days),
                         idempotency_key=key)


async def enqueue_lead_no_register(conn: asyncpg.Connection, lead_id: str, email: str) -> bool:
    key = f"lead_no_register:{lead_id}:v1"
    return await enqueue(conn, user_id=lead_id, campaign_key="lead_no_register",
                         trigger_data={"email": email},
                         send_after=datetime.now(timezone.utc) + timedelta(days=1),
                         idempotency_key=key)


async def enqueue_lead_no_quest(conn: asyncpg.Connection, user_id: str) -> bool:
    key = f"lead_no_quest:{user_id}:v1"
    return await enqueue(conn, user_id=user_id, campaign_key="lead_no_quest",
                         send_after=datetime.now(timezone.utc) + timedelta(days=3),
                         idempotency_key=key)


# ── Query helpers ─────────────────────────────────────────────────────────────


async def get_pending_messages(
    conn: asyncpg.Connection,
    limit: int = PROCESS_BATCH_SIZE,
) -> List[asyncpg.Record]:
    """Fetch pending messages that are due for delivery."""
    return await conn.fetch(
        """
        SELECT id, user_id, campaign_key, trigger_data, idempotency_key
        FROM lifecycle_messages
        WHERE status = 'pending' AND send_after <= NOW()
        ORDER BY send_after ASC
        LIMIT $1
        """,
        limit,
    )


async def mark_sent(conn: asyncpg.Connection, message_id: str) -> None:
    await conn.execute(
        """
        UPDATE lifecycle_messages
        SET status = 'sent', sent_at = NOW()
        WHERE id = $1
        """,
        message_id,
    )


async def mark_failed(conn: asyncpg.Connection, message_id: str, error: str) -> None:
    await conn.execute(
        """
        UPDATE lifecycle_messages
        SET status = 'failed', error_message = $2
        WHERE id = $1
        """,
        message_id,
        error[:500],
    )


async def suppress(conn: asyncpg.Connection, message_id: str) -> None:
    await conn.execute(
        "UPDATE lifecycle_messages SET status = 'suppressed' WHERE id = $1",
        message_id,
    )


async def record_delivery_error(conn: asyncpg.Connection, message_id: str, error: str) -> None:
    await conn.execute(
        "UPDATE lifecycle_messages SET error_message = $2 WHERE id = $1",
        message_id,
        error[:500],
    )


def build_lifecycle_email(campaign_key: str, trigger_data: Optional[Dict[str, Any]] = None) -> tuple[str, str]:
    template = CAMPAIGN_TEMPLATES.get(campaign_key)
    if template is None:
        return (
            "[QuestionWork] Уведомление",
            "<p>У вас есть новое уведомление от QuestionWork.</p>",
        )

    subject, body_builder = template
    body_html = body_builder(trigger_data or {}).replace("__FRONTEND_URL__", settings.FRONTEND_URL)
    return subject, body_html


async def resolve_delivery_recipient(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    campaign_key: str,
    trigger_data: Optional[Dict[str, Any]] = None,
) -> dict[str, str] | None:
    payload = trigger_data or {}
    if campaign_key == "lead_no_register":
        email = str(payload.get("email") or "").strip().lower()
        if not email:
            return None
        username = str(payload.get("company_name") or payload.get("contact_name") or "there").strip() or "there"
        return {"email": email, "username": username}

    row = await conn.fetchrow(
        "SELECT email, username FROM users WHERE id = $1",
        user_id,
    )
    if row is None or not row.get("email"):
        return None

    return {
        "email": str(row["email"]),
        "username": str(row.get("username") or "User"),
    }


# ── Scan triggers (called by background workers) ──────────────────────────────


async def scan_and_enqueue_dormant_clients(conn: asyncpg.Connection) -> int:
    """Find clients dormant at 7/14/30 days and enqueue nudges."""
    count = 0
    for days in (7, 14, 30):
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        window_start = cutoff - timedelta(hours=12)  # ±12h window to avoid missing by seconds
        rows = await conn.fetch(
            """
            SELECT q.client_id, q.id AS quest_id
            FROM quests q
            WHERE q.status = 'confirmed'
              AND q.updated_at BETWEEN $1 AND $2
              -- Only clients with no newer activity
              AND NOT EXISTS (
                  SELECT 1 FROM quests q2
                  WHERE q2.client_id = q.client_id
                    AND q2.updated_at > q.updated_at
              )
            """,
            window_start,
            cutoff,
        )
        for row in rows:
            try:
                async with conn.transaction():
                    inserted = await enqueue_dormant_client(
                        conn,
                        user_id=row["client_id"],
                        days=days,
                        last_quest_id=row["quest_id"],
                    )
                    if inserted:
                        count += 1
            except Exception as exc:
                logger.warning("Failed to enqueue dormant_client for %s: %s", row["client_id"], exc)
    return count


async def scan_and_enqueue_stale_shortlists(conn: asyncpg.Connection) -> int:
    """Find clients with shortlists older than 7 days but no recent quest activity."""
    count = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    rows = await conn.fetch(
        """
        SELECT DISTINCT s.user_id
        FROM shortlists s
        WHERE s.created_at < $1
          AND NOT EXISTS (
              SELECT 1 FROM quests q
              WHERE q.client_id = s.user_id
                AND q.created_at > $1
          )
        """,
        cutoff,
    )
    for row in rows:
        try:
            async with conn.transaction():
                inserted = await enqueue_stale_shortlist(conn, user_id=row["user_id"])
                if inserted:
                    count += 1
        except Exception as exc:
            logger.warning("Failed to enqueue stale_shortlist for %s: %s", row["user_id"], exc)
    return count
