"""
Dispute resolution service.

Handles the full lifecycle:
  open → responded → escalated → resolved

All write operations must be called inside an explicit DB transaction.
Notifications are sent within the same transaction to ensure atomicity.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import asyncpg

from app.core.config import settings
from app.core.rewards import calculate_quest_rewards, calculate_xp_to_next, check_level_up, allocate_stat_points
from app.models.dispute import DisputeListResponse, DisputeOut, DisputeStatus, ResolutionType
from app.models.user import GradeEnum
from app.services import notification_service, wallet_service, badge_service, class_service, trust_score_service

logger = logging.getLogger(__name__)

# Statuses that count as "active" (prevent a second dispute on same quest)
_ACTIVE_STATUSES = ("open", "responded", "escalated")
# Quest statuses that allow opening a dispute
_DISPUTABLE_QUEST_STATUSES = ("completed", "revision_requested")
# How long the respondent has to reply before auto-escalation
AUTO_ESCALATE_HOURS = 72


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _new_dispute_id() -> str:
    return f"dis_{uuid.uuid4().hex[:14]}"


def _row_to_out(row) -> DisputeOut:
    return DisputeOut(
        id=row["id"],
        quest_id=row["quest_id"],
        initiator_id=row["initiator_id"],
        respondent_id=row["respondent_id"],
        reason=row["reason"],
        response_text=row["response_text"],
        status=DisputeStatus(row["status"]),
        resolution_type=ResolutionType(row["resolution_type"]) if row["resolution_type"] else None,
        partial_percent=float(row["partial_percent"]) if row["partial_percent"] is not None else None,
        resolution_note=row["resolution_note"],
        moderator_id=row["moderator_id"],
        auto_escalate_at=row["auto_escalate_at"],
        created_at=row["created_at"],
        responded_at=row["responded_at"],
        escalated_at=row["escalated_at"],
        resolved_at=row["resolved_at"],
    )


def _assert_in_transaction(conn: asyncpg.Connection) -> None:
    if not conn.is_in_transaction():
        raise RuntimeError("dispute_service calls must be inside an explicit DB transaction")


# ─────────────────────────────────────────────────────────────────────
# Write operations
# ─────────────────────────────────────────────────────────────────────

async def open_dispute(
    conn: asyncpg.Connection,
    *,
    quest_id: str,
    initiator_id: str,
    reason: str,
) -> DisputeOut:
    """Freelancer opens a dispute on a completed/revision_requested quest.

    Validates:
      - quest.assigned_to == initiator_id (only the freelancer may open)
      - quest.status in ('completed', 'revision_requested')
      - no active dispute already exists on this quest

    Transitions quest status to 'disputed'.
    Notifies the client.
    """
    _assert_in_transaction(conn)
    now = datetime.now(timezone.utc)

    quest = await conn.fetchrow(
        "SELECT id, title, client_id, assigned_to, status, currency FROM quests WHERE id = $1 FOR UPDATE",
        quest_id,
    )
    if quest is None:
        raise ValueError("Quest not found")
    if quest["assigned_to"] != initiator_id:
        raise PermissionError("Only the assigned freelancer can open a dispute")
    if quest["status"] not in _DISPUTABLE_QUEST_STATUSES:
        raise ValueError(
            f"Disputes can only be opened on quests with status "
            f"{_DISPUTABLE_QUEST_STATUSES}, got '{quest['status']}'"
        )

    # Check for existing active dispute (unique index covers this, but a clear error is nicer)
    existing = await conn.fetchval(
        "SELECT id FROM disputes WHERE quest_id = $1 AND status = ANY($2::text[])",
        quest_id,
        list(_ACTIVE_STATUSES),
    )
    if existing:
        raise ValueError("An active dispute already exists for this quest")

    # Flip quest status to 'disputed'
    updated = await conn.fetchval(
        "UPDATE quests SET status = 'disputed', updated_at = $1 WHERE id = $2 AND status = ANY($3::text[]) RETURNING id",
        now,
        quest_id,
        list(_DISPUTABLE_QUEST_STATUSES),
    )
    if updated is None:
        raise ValueError("Quest status changed concurrently; please retry")

    auto_escalate_at = now + timedelta(hours=AUTO_ESCALATE_HOURS)
    dispute_id = _new_dispute_id()

    row = await conn.fetchrow(
        """
        INSERT INTO disputes
            (id, quest_id, initiator_id, respondent_id, reason, status, auto_escalate_at, created_at)
        VALUES ($1, $2, $3, $4, $5, 'open', $6, $7)
        RETURNING *
        """,
        dispute_id,
        quest_id,
        initiator_id,
        quest["client_id"],
        reason,
        auto_escalate_at,
        now,
    )

    await notification_service.create_notification(
        conn,
        user_id=quest["client_id"],
        title="Открыт спор по квесту",
        message=(
            f"Фрилансер открыл спор по квесту «{quest['title']}». "
            f"У вас {AUTO_ESCALATE_HOURS} часов, чтобы ответить."
        ),
        event_type="dispute_opened",
    )

    logger.info("Dispute %s opened for quest %s by user %s", dispute_id, quest_id, initiator_id)
    return _row_to_out(row)


async def respond_dispute(
    conn: asyncpg.Connection,
    *,
    dispute_id: str,
    user_id: str,
    response_text: str,
) -> DisputeOut:
    """Client (respondent) responds to an open dispute."""
    _assert_in_transaction(conn)
    now = datetime.now(timezone.utc)

    dispute = await conn.fetchrow(
        "SELECT id, initiator_id, respondent_id, status FROM disputes WHERE id = $1 FOR UPDATE",
        dispute_id,
    )
    if dispute is None:
        raise ValueError("Dispute not found")
    if dispute["respondent_id"] != user_id:
        raise PermissionError("Only the respondent can respond to this dispute")
    if dispute["status"] != "open":
        raise ValueError(f"Dispute is not open; current status: '{dispute['status']}'")

    row = await conn.fetchrow(
        """
        UPDATE disputes
        SET status = 'responded', response_text = $1, responded_at = $2
        WHERE id = $3
        RETURNING *
        """,
        response_text,
        now,
        dispute_id,
    )

    await notification_service.create_notification(
        conn,
        user_id=dispute["initiator_id"],
        title="Клиент ответил на спор",
        message="Клиент оставил ответ на ваш спор. Вы можете эскалировать его модератору.",
        event_type="dispute_responded",
    )

    logger.info("Dispute %s responded by user %s", dispute_id, user_id)
    return _row_to_out(row)


async def escalate_dispute(
    conn: asyncpg.Connection,
    *,
    dispute_id: str,
    user_id: str,
) -> DisputeOut:
    """Either party manually escalates the dispute to moderators."""
    _assert_in_transaction(conn)
    now = datetime.now(timezone.utc)

    dispute = await conn.fetchrow(
        "SELECT id, initiator_id, respondent_id, status FROM disputes WHERE id = $1 FOR UPDATE",
        dispute_id,
    )
    if dispute is None:
        raise ValueError("Dispute not found")
    if user_id not in (dispute["initiator_id"], dispute["respondent_id"]):
        raise PermissionError("Only dispute parties can escalate")
    if dispute["status"] not in ("open", "responded"):
        raise ValueError(f"Cannot escalate dispute with status '{dispute['status']}'")

    row = await conn.fetchrow(
        """
        UPDATE disputes
        SET status = 'escalated', escalated_at = $1
        WHERE id = $2
        RETURNING *
        """,
        now,
        dispute_id,
    )

    # Notify all admins
    admin_ids = await conn.fetch(
        "SELECT id FROM users WHERE role = 'admin' AND is_banned = FALSE",
    )
    for admin_row in admin_ids:
        await notification_service.create_notification(
            conn,
            user_id=admin_row["id"],
            title="Спор эскалирован",
            message=f"Спор {dispute_id} был эскалирован и требует вашего рассмотрения.",
            event_type="dispute_escalated",
        )

    # Notify both parties
    for uid in (dispute["initiator_id"], dispute["respondent_id"]):
        await notification_service.create_notification(
            conn,
            user_id=uid,
            title="Спор передан модератору",
            message="Ваш спор был эскалирован на рассмотрение модератора.",
            event_type="dispute_escalated",
        )

    logger.info("Dispute %s escalated by user %s", dispute_id, user_id)
    return _row_to_out(row)


async def resolve_dispute(
    conn: asyncpg.Connection,
    *,
    dispute_id: str,
    moderator_id: str,
    resolution_type: ResolutionType,
    resolution_note: str,
    partial_percent: float | None = None,
) -> DisputeOut:
    """Admin/moderator resolves an escalated dispute.

    resolution_type:
      - 'refund'     → full escrow refund to client, quest cancelled
      - 'freelancer' → full payout (split_payment), quest confirmed
      - 'partial'    → partial_percent % to freelancer, remainder to client, quest confirmed
    """
    _assert_in_transaction(conn)
    now = datetime.now(timezone.utc)

    if resolution_type == ResolutionType.partial and not partial_percent:
        raise ValueError("partial_percent is required for 'partial' resolution")

    dispute = await conn.fetchrow(
        "SELECT id, quest_id, initiator_id, respondent_id, status FROM disputes WHERE id = $1 FOR UPDATE",
        dispute_id,
    )
    if dispute is None:
        raise ValueError("Dispute not found")
    if dispute["status"] != "escalated":
        raise ValueError(f"Only escalated disputes can be resolved; got '{dispute['status']}'")

    quest = await conn.fetchrow(
        "SELECT id, title, client_id, assigned_to, budget, currency, platform_fee_percent, required_grade, xp_reward FROM quests WHERE id = $1 FOR UPDATE",
        dispute["quest_id"],
    )
    if quest is None:
        raise ValueError("Quest not found")

    currency = quest["currency"]
    budget = Decimal(str(quest["budget"]))
    client_id = quest["client_id"]
    freelancer_id = quest["assigned_to"]
    fee_percent = Decimal(str(quest["platform_fee_percent"] or settings.PLATFORM_FEE_PERCENT))

    if resolution_type == ResolutionType.refund:
        # Return full escrow to client
        refunded_balance = await wallet_service.refund_hold(conn, client_id, quest["id"], currency)
        if refunded_balance is None:
            raise ValueError("No active escrow hold found for refund resolution")
        await conn.execute(
            "UPDATE quests SET status = 'cancelled', updated_at = $1 WHERE id = $2",
            now, quest["id"],
        )

    elif resolution_type == ResolutionType.freelancer:
        # Full payout to freelancer (standard split)
        await wallet_service.split_payment(
            conn,
            client_id=client_id,
            freelancer_id=freelancer_id,
            gross_amount=budget,
            currency=currency,
            quest_id=quest["id"],
            fee_percent=fee_percent,
        )
        await conn.execute(
            "UPDATE quests SET status = 'confirmed', completed_at = $1, updated_at = $1 WHERE id = $2",
            now, quest["id"],
        )
        # Grant XP to freelancer — dispute win counts as quest completion for RPG progression
        await _grant_dispute_resolution_xp(conn, freelancer_id, quest, now)

    else:  # partial
        pct = Decimal(str(partial_percent)) / Decimal("100")
        gross_freelancer = (budget * pct).quantize(Decimal("0.01"))
        client_refund = budget - gross_freelancer
        fee = (gross_freelancer * fee_percent / Decimal("100")).quantize(Decimal("0.01"))
        net_freelancer = gross_freelancer - fee

        # Check platform user existence if fee > 0
        if fee > 0:
            platform_exists = await conn.fetchval(
                "SELECT 1 FROM users WHERE id = $1", settings.PLATFORM_USER_ID
            )
            if not platform_exists:
                # Fallback: give fee to freelancer to avoid crashing
                net_freelancer += fee
                fee = Decimal("0")

        # Lock and scope the hold lookup so partial resolution cannot read stale or cross-currency escrow.
        hold_tx = await conn.fetchrow(
            """
            SELECT id FROM transactions
            WHERE user_id = $1 AND quest_id = $2 AND type = 'hold' AND status = 'held' AND currency = $3
            FOR UPDATE
            """,
            client_id,
            quest["id"],
            currency,
        )
        
        amount_owed = net_freelancer + fee

        if hold_tx:
            await wallet_service.release_hold(conn, client_id, quest["id"], currency)
            if client_refund > 0:
                await wallet_service.credit(
                    conn, client_id, client_refund, currency, quest["id"], "refund"
                )
        else:
            if amount_owed > 0:
                await wallet_service.debit(
                    conn, client_id, amount_owed, currency, quest["id"], "expense"
                )

        # Credit each recipient
        if net_freelancer > 0:
            await wallet_service.credit(
                conn, freelancer_id, net_freelancer, currency, quest["id"], "income"
            )
        if fee > 0:
            await wallet_service.credit(
                conn, settings.PLATFORM_USER_ID, fee, currency, quest["id"], "commission"
            )

        await conn.execute(
            "UPDATE quests SET status = 'confirmed', completed_at = $1, updated_at = $1 WHERE id = $2",
            now, quest["id"],
        )

    # Update dispute record
    row = await conn.fetchrow(
        """
        UPDATE disputes
        SET status = 'resolved',
            resolution_type = $1,
            partial_percent = $2,
            resolution_note = $3,
            moderator_id    = $4,
            resolved_at     = $5
        WHERE id = $6
        RETURNING *
        """,
        resolution_type.value,
        partial_percent,
        resolution_note,
        moderator_id,
        now,
        dispute_id,
    )

    # Notify both parties
    resolution_labels = {
        ResolutionType.refund: "возврат клиенту",
        ResolutionType.partial: f"частичная выплата ({partial_percent}% фрилансеру)",
        ResolutionType.freelancer: "выплата фрилансеру",
    }
    label = resolution_labels[resolution_type]
    for uid in (dispute["initiator_id"], dispute["respondent_id"]):
        await notification_service.create_notification(
            conn,
            user_id=uid,
            title="Спор разрешён",
            message=f"Модератор разрешил спор: {label}. Примечание: {resolution_note}",
            event_type="dispute_resolved",
        )

    logger.info(
        "Dispute %s resolved by moderator %s: %s", dispute_id, moderator_id, resolution_type.value
    )
    return _row_to_out(row)


async def auto_escalate_overdue(conn: asyncpg.Connection) -> int:
    """Bulk-escalate disputes that passed their auto_escalate_at deadline.

    Called periodically by the scheduler. Must be inside a transaction.
    Returns the number of disputes escalated.
    """
    _assert_in_transaction(conn)
    now = datetime.now(timezone.utc)

    rows = await conn.fetch(
        """
        UPDATE disputes
        SET status = 'escalated', escalated_at = $1
        WHERE auto_escalate_at <= $1
          AND status IN ('open', 'responded')
        RETURNING id, initiator_id, respondent_id
        """,
        now,
    )

    if not rows:
        return 0

    count = len(rows)

    # Notify each admin once with an aggregate summary (avoids O(disputes × admins) inserts)
    admin_ids = await conn.fetch(
        "SELECT id FROM users WHERE role = 'admin' AND is_banned = FALSE",
    )
    for admin_row in admin_ids:
        await notification_service.create_notification(
            conn,
            user_id=admin_row["id"],
            title=f"Споры автоэскалированы ({count})",
            message=f"{count} спор(ов) автоматически передано модератору (таймаут без ответа).",
            event_type="dispute_auto_escalated",
        )

    # Notify each party (bounded: 2 users per dispute)
    for dispute_row in rows:
        for uid in (dispute_row["initiator_id"], dispute_row["respondent_id"]):
            await notification_service.create_notification(
                conn,
                user_id=uid,
                title="Спор передан модератору",
                message="Ваш спор автоматически передан на рассмотрение модератора в связи с истечением срока ответа.",
                event_type="dispute_auto_escalated",
            )

    logger.info("Auto-escalated %d overdue dispute(s)", count)
    return count


# ─────────────────────────────────────────────────────────────────────
# Read operations
# ─────────────────────────────────────────────────────────────────────

async def get_dispute(
    conn: asyncpg.Connection,
    dispute_id: str,
    *,
    user_id: str,
    is_admin: bool = False,
) -> DisputeOut:
    """Fetch a dispute by ID. Accessible to both parties and admins."""
    row = await conn.fetchrow("SELECT * FROM disputes WHERE id = $1", dispute_id)
    if row is None:
        raise ValueError("Dispute not found")
    if not is_admin and user_id not in (row["initiator_id"], row["respondent_id"]):
        raise PermissionError("You are not a party to this dispute")
    return _row_to_out(row)


async def list_my_disputes(
    conn: asyncpg.Connection,
    user_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> DisputeListResponse:
    """List disputes where the user is either initiator or respondent."""
    rows = await conn.fetch(
        """
        SELECT * FROM disputes
        WHERE initiator_id = $1 OR respondent_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        user_id,
        limit,
        offset,
    )
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM disputes WHERE initiator_id = $1 OR respondent_id = $1",
        user_id,
    )
    return DisputeListResponse(items=[_row_to_out(r) for r in rows], total=total or 0)


async def admin_list_disputes(
    conn: asyncpg.Connection,
    *,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> DisputeListResponse:
    """List all disputes; optionally filtered by status."""
    if status_filter:
        rows = await conn.fetch(
            "SELECT * FROM disputes WHERE status = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            status_filter, limit, offset,
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM disputes WHERE status = $1", status_filter)
    else:
        rows = await conn.fetch(
            "SELECT * FROM disputes ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM disputes")
    return DisputeListResponse(items=[_row_to_out(r) for r in rows], total=total or 0)


async def _grant_dispute_resolution_xp(
    conn: asyncpg.Connection,
    freelancer_id: str,
    quest: dict,
    now: datetime,
) -> None:
    freelancer = await conn.fetchrow(
        "SELECT id, xp, level, grade, stat_points, stats_int, stats_dex, stats_cha FROM users WHERE id = $1 FOR UPDATE",
        freelancer_id,
    )
    if not freelancer:
        return

    xp_reward = quest.get("xp_reward")
    if not xp_reward or xp_reward <= 0:
        xp_reward = calculate_quest_rewards(
            budget=Decimal(str(quest["budget"])),
            quest_grade=GradeEnum(quest.get("required_grade", GradeEnum.novice.value)),
            user_grade=GradeEnum(freelancer["grade"]),
        )

    old_xp = freelancer["xp"]
    new_xp = old_xp + xp_reward
    level_up, new_grade, new_level, promoted_through = check_level_up(new_xp, GradeEnum(freelancer["grade"]))
    new_xp_to_next = calculate_xp_to_next(new_xp, new_grade)

    levels_gained = max(0, new_level - freelancer["level"])
    stat_delta = allocate_stat_points(levels_gained) if levels_gained > 0 else {"int": 0, "dex": 0, "cha": 0, "unspent": 0}

    new_int = min(100, freelancer["stats_int"] + stat_delta["int"])
    new_dex = min(100, freelancer["stats_dex"] + stat_delta["dex"])
    new_cha = min(100, freelancer["stats_cha"] + stat_delta["cha"])
    new_stat_points = freelancer["stat_points"] + stat_delta["unspent"]

    await conn.execute(
        """
        UPDATE users
        SET xp = $1, level = $2, grade = $3, xp_to_next = $4,
            stats_int = $5, stats_dex = $6, stats_cha = $7,
            stat_points = $8, updated_at = $9
        WHERE id = $10
        """,
        new_xp,
        new_level,
        new_grade.value,
        new_xp_to_next,
        new_int,
        new_dex,
        new_cha,
        new_stat_points,
        now,
        freelancer_id,
    )

    await class_service.add_class_xp(
        conn,
        freelancer_id,
        xp_reward,
        is_urgent=bool(quest.get("is_urgent", False)),
        required_portfolio=bool(quest.get("required_portfolio", False)),
    )
    await trust_score_service.refresh_trust_score(conn, freelancer_id)
    
    # Badge check
    completed_quests_count = await conn.fetchval(
        "SELECT COUNT(*) FROM quests WHERE assigned_to = $1 AND status = 'confirmed'", 
        freelancer_id
    )
    badge_data = {
        "quests_completed": completed_quests_count,
        "xp": new_xp,
        "level": new_level,
        "grade": new_grade.value,
        "earnings": Decimal(str(quest["budget"])),
    }
    
    award_result = await badge_service.check_and_award(
        conn, freelancer_id, "quest_completed", badge_data
    )
    for earned in award_result.newly_earned:
        await notification_service.create_notification(
            conn,
            user_id=freelancer_id,
            title=f"Badge Earned: {earned.badge_name}",
            message=earned.badge_description,
            event_type="badge_earned",
        )
    
    await notification_service.create_notification(
        conn,
        user_id=freelancer_id,
        title="Опыт начислен",
        message=f"Решение спора принесло вам {xp_reward} XP.",
        event_type="xp_granted",
    )
