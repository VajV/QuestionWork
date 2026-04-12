"""Counter-offer service — allows clients to negotiate price on applications."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import asyncpg

from app.core.ratelimit import check_rate_limit
from app.services import notification_service

logger = logging.getLogger(__name__)


def _assert_in_transaction(conn: asyncpg.Connection) -> None:
    if not conn.is_in_transaction():
        raise RuntimeError("counter_offer_service functions must run inside an explicit DB transaction.")


async def make_counter_offer(
    conn: asyncpg.Connection,
    *,
    quest_id: str,
    application_id: str,
    client_id: str,
    counter_price: Decimal,
    message: Optional[str] = None,
) -> dict:
    """Client proposes an alternative price for a freelancer application.

    Raises ValueError on invalid state, PermissionError if caller is not the quest owner.
    """
    _assert_in_transaction(conn)

    if counter_price <= 0:
        raise ValueError("Counter-offer price must be positive")

    row = await conn.fetchrow(
        """
        SELECT a.id, a.quest_id, a.freelancer_id, a.freelancer_username,
               a.proposed_price, a.counter_offer_status,
               q.client_id, q.status AS quest_status, q.title AS quest_title
        FROM applications a
        JOIN quests q ON q.id = a.quest_id
        WHERE a.id = $1 AND a.quest_id = $2
        FOR UPDATE
        """,
        application_id,
        quest_id,
    )
    if not row:
        raise ValueError("Application not found")
    if row["client_id"] != client_id:
        raise PermissionError("Only the quest owner can send a counter-offer")
    if row["quest_status"] not in ("open",):
        raise ValueError("Counter-offers can only be made on open quests")
    if row["counter_offer_status"] == "pending":
        raise ValueError("A counter-offer is already pending for this application")

    now = datetime.now(timezone.utc)
    await conn.execute(
        """
        UPDATE applications
        SET counter_offer_price = $1,
            counter_offer_status = 'pending',
            counter_offer_message = $2,
            counter_offered_at = $3,
            counter_responded_at = NULL
        WHERE id = $4
        """,
        counter_price,
        message,
        now,
        application_id,
    )

    await notification_service.create_notification(
        conn,
        row["freelancer_id"],
        title=f"💬 Встречное предложение по квесту «{row['quest_title']}»",
        message=(
            f"Заказчик предлагает {counter_price} ₽. "
            + (f"Комментарий: {message}" if message else "Примите или отклоните.")
        ),
        event_type="counter_offer_received",
    )

    return {
        "id": application_id,
        "quest_id": quest_id,
        "counter_offer_price": counter_price,
        "counter_offer_status": "pending",
        "counter_offer_message": message,
        "counter_offered_at": now.isoformat(),
    }


async def respond_to_counter_offer(
    conn: asyncpg.Connection,
    *,
    quest_id: str,
    application_id: str,
    freelancer_id: str,
    accept: bool,
) -> dict:
    """Freelancer accepts or declines a pending counter-offer.

    If accepted, the application's proposed_price is updated to the
    counter_offer_price so the assignment flow reads the agreed price.
    """
    _assert_in_transaction(conn)

    row = await conn.fetchrow(
        """
        SELECT a.id, a.quest_id, a.freelancer_id,
               a.counter_offer_price, a.counter_offer_status,
               q.client_id, q.status AS quest_status, q.title AS quest_title
        FROM applications a
        JOIN quests q ON q.id = a.quest_id
        WHERE a.id = $1 AND a.quest_id = $2
        FOR UPDATE
        """,
        application_id,
        quest_id,
    )
    if not row:
        raise ValueError("Application not found")
    if row["freelancer_id"] != freelancer_id:
        raise PermissionError("Only the applicant can respond to a counter-offer")
    if row["quest_status"] not in ("open",):
        raise ValueError("Quest is no longer open")
    if row["counter_offer_status"] != "pending":
        raise ValueError("No pending counter-offer to respond to")

    new_status = "accepted" if accept else "declined"
    now = datetime.now(timezone.utc)

    if accept:
        # Update proposed_price to agreed counter price
        await conn.execute(
            """
            UPDATE applications
            SET counter_offer_status = $1,
                counter_responded_at = $2,
                proposed_price = counter_offer_price
            WHERE id = $3
            """,
            new_status,
            now,
            application_id,
        )
    else:
        await conn.execute(
            """
            UPDATE applications
            SET counter_offer_status = $1,
                counter_responded_at = $2
            WHERE id = $3
            """,
            new_status,
            now,
            application_id,
        )

    # Notify client
    verb = "принял" if accept else "отклонил"
    await notification_service.create_notification(
        conn,
        row["client_id"],
        title=f"🤝 Встречное предложение {verb} по квесту «{row['quest_title']}»",
        message=(
            f"Фрилансер {'принял' if accept else 'отклонил'} ваше предложение "
            f"{'и готов работать за ' + str(row['counter_offer_price']) + ' ₽.' if accept else '.'}"
        ),
        event_type="counter_offer_responded",
    )

    return {
        "id": application_id,
        "quest_id": quest_id,
        "counter_offer_status": new_status,
        "counter_responded_at": now.isoformat(),
    }


async def get_application_with_counter(
    conn: asyncpg.Connection,
    application_id: str,
    *,
    caller_id: str,
) -> dict:
    """Return full application row including counter-offer fields.

    Only the quest client or the applicant themselves can fetch this.
    """
    row = await conn.fetchrow(
        """
        SELECT a.id, a.quest_id, a.freelancer_id, a.freelancer_username,
               a.freelancer_grade, a.cover_letter, a.proposed_price,
               a.counter_offer_price, a.counter_offer_status,
               a.counter_offer_message, a.counter_offered_at,
               a.counter_responded_at, a.created_at,
               q.client_id
        FROM applications a
        JOIN quests q ON q.id = a.quest_id
        WHERE a.id = $1
        """,
        application_id,
    )
    if not row:
        raise ValueError("Application not found")
    if caller_id not in (row["freelancer_id"], row["client_id"]):
        raise PermissionError("Access denied")
    return dict(row)
