"""Persistent email outbox service.

Emails are enqueued to `email_outbox` table and delivered by a background
worker (`process_lifecycle_messages.py`). This ensures delivery survives
process restarts and provides a retry mechanism.

Template keys map to email_service rendering functions.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import asyncpg

from app.services import email_service

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


# ── Enqueue ───────────────────────────────────────────────────────────────────


async def enqueue_email(
    conn: asyncpg.Connection,
    *,
    email_address: str,
    template_key: str,
    template_params: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    send_after: Optional[datetime] = None,
) -> str:
    """Insert a pending email into the outbox. Returns the new row id.

    Must be called inside an existing transaction so the email enqueue is
    atomic with the event that triggered it.
    """
    if not conn.is_in_transaction():
        raise RuntimeError("enqueue_email must be called inside an existing DB transaction.")

    now = datetime.now(timezone.utc)
    row = await conn.fetchrow(
        """
        INSERT INTO email_outbox
            (user_id, email_address, template_key, template_params, status, send_after, created_at)
        VALUES ($1, $2, $3, $4::jsonb, 'pending', $5, $6)
        RETURNING id
        """,
        user_id,
        email_address,
        template_key,
        json.dumps(template_params or {}),
        send_after or now,
        now,
    )
    return str(row["id"])


# ── Process ───────────────────────────────────────────────────────────────────


async def process_due_emails(conn: asyncpg.Connection, limit: int = 50) -> Dict[str, int]:
    """Fetch and deliver due emails from the outbox.

    Uses FOR UPDATE SKIP LOCKED to prevent concurrent workers from
    processing the same email row (avoids duplicate delivery).

    Returns counts: {"sent": N, "failed": N, "skipped": N}.
    """
    sent = failed = skipped = 0

    # Process each email in its own transaction so a single failure
    # does not roll back the entire batch.
    rows = await conn.fetch(
        """
        SELECT id
        FROM email_outbox
        WHERE status = 'pending'
          AND send_after <= NOW()
          AND attempt_count < $1
        ORDER BY send_after ASC
        LIMIT $2
        """,
        MAX_ATTEMPTS,
        limit,
    )

    for id_row in rows:
        outbox_id = str(id_row["id"])
        try:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT id, user_id, email_address, template_key, template_params, attempt_count
                    FROM email_outbox
                    WHERE id = $1 AND status = 'pending'
                    FOR UPDATE SKIP LOCKED
                    """,
                    outbox_id,
                )
                if row is None:
                    # Already claimed by another worker
                    skipped += 1
                    continue

                template_key = row["template_key"]
                params = dict(row["template_params"]) if row["template_params"] else {}
                email_address = row["email_address"]

                try:
                    _deliver(template_key=template_key, email_address=email_address, params=params)
                    await conn.execute(
                        """
                        UPDATE email_outbox
                        SET status = 'sent', sent_at = NOW(), attempt_count = attempt_count + 1
                        WHERE id = $1
                        """,
                        outbox_id,
                    )
                    sent += 1
                except Exception as exc:
                    attempt = row["attempt_count"] + 1
                    new_status = "failed" if attempt >= MAX_ATTEMPTS else "pending"
                    await conn.execute(
                        """
                        UPDATE email_outbox
                        SET attempt_count = $2, status = $3, error_message = $4
                        WHERE id = $1
                        """,
                        outbox_id,
                        attempt,
                        new_status,
                        str(exc)[:500],
                    )
                    if new_status == "failed":
                        failed += 1
                    else:
                        skipped += 1
                    logger.warning("Email outbox delivery failed (id=%s, attempt=%d): %s", outbox_id, attempt, exc)
        except Exception as exc:
            logger.error("Unexpected error processing outbox id=%s: %s", outbox_id, exc)
            failed += 1

    return {"sent": sent, "failed": failed, "skipped": skipped}


# ── Template dispatch ─────────────────────────────────────────────────────────


def _deliver(*, template_key: str, email_address: str, params: Dict[str, Any]) -> None:
    """Dispatch to the appropriate email_service render function."""
    if not email_service._enabled():
        logger.debug("Emails disabled — skipping delivery of template %r to %s", template_key, email_address)
        return

    # Dispatch table: template_key → email_service function
    dispatcher = {
        "quest_assigned": lambda: email_service.send_quest_assigned(
            to=email_address,
            username=params.get("username", "User"),
            quest_title=params.get("quest_title", ""),
        ),
        "quest_completed": lambda: email_service.send_quest_completed(
            to=email_address,
            username=params.get("username", "User"),
            quest_title=params.get("quest_title", ""),
            xp_gained=params.get("xp_gained", 0),
        ),
        "welcome": lambda: email_service.send_welcome(
            to=email_address,
            username=params.get("username", "User"),
        ),
        "password_reset": lambda: email_service.send_password_reset(
            to=email_address,
            username=params.get("username", "User"),
            reset_link=params.get("reset_link", ""),
        ),
        "review_received": lambda: email_service.send_review_received(
            to=email_address,
            username=params.get("username", "User"),
            reviewer_username=params.get("reviewer_username", ""),
            rating=params.get("rating", 5),
            comment=params.get("comment"),
        ),
        "withdrawal_status": lambda: email_service.send_withdrawal_status(
            to=email_address,
            username=params.get("username", "User"),
            amount=params.get("amount", "0"),
            currency=params.get("currency", "RUB"),
            status=params.get("withdrawal_status", "processing"),
        ),
        "lifecycle_nudge": lambda: email_service.send_lifecycle_nudge(
            to=email_address,
            username=params.get("username", "User"),
            subject=params.get("subject", "A note from QuestionWork"),
            body_html=params.get("body_html", ""),
        ),
    }

    handler = dispatcher.get(template_key)
    if handler is None:
        logger.warning("Unknown email template key: %r — skipping delivery", template_key)
        return

    handler()
