"""Milestone escrow service — staged payment release for quests."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import asyncpg

from app.services import notification_service, wallet_service

logger = logging.getLogger(__name__)


def _assert_in_transaction(conn: asyncpg.Connection) -> None:
    if not conn.is_in_transaction():
        raise RuntimeError("milestone_service functions must run inside an explicit DB transaction.")


def _make_id() -> str:
    return f"ms_{secrets.token_hex(8)}"


ALLOWED_MILESTONE_STATUSES = ("pending", "active", "completed", "cancelled")


async def create_milestone(
    conn: asyncpg.Connection,
    *,
    quest_id: str,
    title: str,
    amount: Decimal,
    description: Optional[str] = None,
    sort_order: int = 0,
    due_at: Optional[datetime] = None,
    currency: str = "RUB",
) -> dict:
    """Add a milestone to a quest.  Quest must be open or assigned."""
    _assert_in_transaction(conn)

    if amount <= 0:
        raise ValueError("Milestone amount must be positive")
    if not title.strip():
        raise ValueError("Milestone title is required")

    quest = await conn.fetchrow(
        "SELECT id, client_id, budget, status FROM quests WHERE id = $1 FOR UPDATE",
        quest_id,
    )
    if not quest:
        raise ValueError("Quest not found")
    if quest["status"] not in ("open", "assigned", "in_progress"):
        raise ValueError("Milestones can only be added to open, assigned or in-progress quests")

    # Ensure total milestone amount does not exceed quest budget
    existing_total = await conn.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM quest_milestones WHERE quest_id = $1 AND status != 'cancelled'",
        quest_id,
    ) or Decimal("0")
    if existing_total + amount > quest["budget"]:
        raise ValueError(
            f"Total milestone amounts ({existing_total + amount}) would exceed quest budget ({quest['budget']})"
        )

    ms_id = _make_id()
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO quest_milestones
            (id, quest_id, title, description, amount, currency, sort_order, status, due_at, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', $8, $9, $9)
        """,
        ms_id, quest_id, title.strip(), description, amount, currency, sort_order, due_at, now,
    )

    return await _fetch_milestone(conn, ms_id)


async def list_milestones(conn: asyncpg.Connection, quest_id: str) -> list[dict]:
    """Return all milestones for a quest ordered by sort_order."""
    rows = await conn.fetch(
        """
        SELECT id, quest_id, title, description, amount, currency, sort_order, status,
               due_at, completed_at, release_tx_id, created_at, updated_at
        FROM quest_milestones
        WHERE quest_id = $1
        ORDER BY sort_order ASC, created_at ASC
        """,
        quest_id,
    )
    return [dict(r) for r in rows]


async def activate_milestone(
    conn: asyncpg.Connection,
    *,
    milestone_id: str,
    client_id: str,
) -> dict:
    """Set a milestone to 'active'.  Client must own the quest.

    Holding funds is done separately via wallet_service.hold() by the caller
    as part of the broader quest assignment transaction.
    """
    _assert_in_transaction(conn)

    ms = await conn.fetchrow(
        """
        SELECT m.id, m.quest_id, m.status, m.amount, q.client_id
        FROM quest_milestones m
        JOIN quests q ON q.id = m.quest_id
        WHERE m.id = $1 FOR UPDATE
        """,
        milestone_id,
    )
    if not ms:
        raise ValueError("Milestone not found")
    if ms["client_id"] != client_id:
        raise PermissionError("Only the quest owner can activate milestones")
    if ms["status"] != "pending":
        raise ValueError(f"Milestone is already {ms['status']}")

    now = datetime.now(timezone.utc)
    await conn.execute(
        "UPDATE quest_milestones SET status = 'active', updated_at = $1 WHERE id = $2",
        now, milestone_id,
    )
    return await _fetch_milestone(conn, milestone_id)


async def complete_milestone(
    conn: asyncpg.Connection,
    *,
    milestone_id: str,
    client_id: str,
) -> dict:
    """Client marks a milestone as complete and releases its escrow to the freelancer."""
    _assert_in_transaction(conn)

    ms = await conn.fetchrow(
        """
        SELECT m.id, m.quest_id, m.status, m.amount, m.currency,
               q.client_id, q.assigned_to, q.title AS quest_title
        FROM quest_milestones m
        JOIN quests q ON q.id = m.quest_id
        WHERE m.id = $1 FOR UPDATE
        """,
        milestone_id,
    )
    if not ms:
        raise ValueError("Milestone not found")
    if ms["client_id"] != client_id:
        raise PermissionError("Only the quest owner can complete milestones")
    if ms["status"] != "active":
        raise ValueError(f"Milestone must be in 'active' state to complete (current: {ms['status']})")
    if not ms["assigned_to"]:
        raise ValueError("Quest has no assigned freelancer")

    now = datetime.now(timezone.utc)

    # Release escrow: credit freelancer wallet
    await wallet_service.credit(
        conn,
        user_id=ms["assigned_to"],
        amount=ms["amount"],
        currency=ms["currency"],
        quest_id=ms["quest_id"],
        tx_type="release",
    )

    await conn.execute(
        """
        UPDATE quest_milestones
        SET status = 'completed', completed_at = $1, updated_at = $1
        WHERE id = $2
        """,
        now, milestone_id,
    )

    updated = await _fetch_milestone(conn, milestone_id)

    await notification_service.create_notification(
        conn,
        ms["assigned_to"],
        title=f"💰 Оплата выпущена: «{ms['quest_title']}»",
        message=f"Заказчик подтвердил milestone и выпустил {ms['amount']} {ms['currency']}.",
        event_type="milestone_payment_released",
    )

    return updated


async def cancel_milestone(
    conn: asyncpg.Connection,
    *,
    milestone_id: str,
    client_id: str,
) -> dict:
    """Cancel a pending or active milestone."""
    _assert_in_transaction(conn)

    ms = await conn.fetchrow(
        """
        SELECT m.id, m.quest_id, m.status, q.client_id
        FROM quest_milestones m
        JOIN quests q ON q.id = m.quest_id
        WHERE m.id = $1 FOR UPDATE
        """,
        milestone_id,
    )
    if not ms:
        raise ValueError("Milestone not found")
    if ms["client_id"] != client_id:
        raise PermissionError("Only the quest owner can cancel milestones")
    if ms["status"] == "completed":
        raise ValueError("Cannot cancel a completed milestone")
    if ms["status"] == "cancelled":
        raise ValueError("Milestone is already cancelled")

    now = datetime.now(timezone.utc)
    await conn.execute(
        "UPDATE quest_milestones SET status = 'cancelled', updated_at = $1 WHERE id = $2",
        now, milestone_id,
    )
    return await _fetch_milestone(conn, milestone_id)


async def _fetch_milestone(conn: asyncpg.Connection, milestone_id: str) -> dict:
    row = await conn.fetchrow(
        """
        SELECT id, quest_id, title, description, amount, currency, sort_order, status,
               due_at, completed_at, release_tx_id, created_at, updated_at
        FROM quest_milestones WHERE id = $1
        """,
        milestone_id,
    )
    return dict(row) if row else {}
