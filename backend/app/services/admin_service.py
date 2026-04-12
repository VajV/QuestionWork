"""
AdminService — administrative operations with full audit trail.

All write operations:
  - Must be called inside an existing DB transaction.
  - Automatically write an entry to admin_logs.

Read operations are transaction-free and safe to call outside a transaction.
"""

import json
import logging
import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

import asyncpg

from app.core.config import settings
from app.core.rewards import check_level_up, calculate_xp_to_next, allocate_stat_points, GRADE_XP_THRESHOLDS
from app.core.classes import calculate_perk_points_available, get_class_config
from app.models.user import GradeEnum
from app.models.quest import QuestStatusEnum
from app.services import wallet_service, notification_service, guild_card_service, guild_economy_service, badge_service, class_service
from app.services.quest_helpers import record_quest_status_history as _record_quest_status_history

logger = logging.getLogger(__name__)

ADMIN_SKILLS_MAX_ITEMS = 20
ADMIN_SKILLS_MAX_LENGTH = 50

_ADMIN_USER_DETAIL_COLUMNS = (
    "id, username, email, role, level, grade, xp, xp_to_next, "
    "stat_points, stats_int, stats_dex, stats_cha, bio, skills, "
    "character_class, is_banned, banned_reason, banned_at, created_at, updated_at"
)
_ADMIN_USER_UPDATE_COLUMNS = (
    "id, role, level, grade, xp, xp_to_next, stat_points, "
    "stats_int, stats_dex, stats_cha, bio, skills, character_class"
)
_USER_PROGRESS_COLUMNS = (
    "id, grade, xp, level, stat_points, stats_int, stats_dex, stats_cha, character_class"
)


# ──────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _assert_in_transaction(conn: asyncpg.Connection) -> None:
    if not conn.is_in_transaction():
        raise RuntimeError(
            "This admin_service function must be called inside an explicit DB transaction."
        )


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _normalize_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _normalize_admin_skills(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("skills must be provided as a list of strings")
    if len(value) > ADMIN_SKILLS_MAX_ITEMS:
        raise ValueError(f"skills must contain at most {ADMIN_SKILLS_MAX_ITEMS} items")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("skills must contain only strings")
        skill = item.strip()
        if not skill:
            raise ValueError("skills cannot contain blank values")
        if len(skill) > ADMIN_SKILLS_MAX_LENGTH:
            raise ValueError(
                f"each skill must be at most {ADMIN_SKILLS_MAX_LENGTH} characters"
            )
        normalized.append(skill)

    return normalized


def _escape_like(value: str) -> str:
    """Escape LIKE/ILIKE special characters so they are matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# _record_quest_status_history is imported from app.services.quest_helpers


async def _cancel_quest_with_invariants(
    conn: asyncpg.Connection,
    quest_row,
    *,
    admin_id: str,
    note: str,
    user_message: str,
) -> bool:
    now = datetime.now(timezone.utc)
    await conn.execute(
        "UPDATE quests SET status = 'cancelled', updated_at = $1 WHERE id = $2",
        now,
        quest_row["id"],
    )

    refund_result = await wallet_service.refund_hold(
        conn,
        user_id=quest_row["client_id"],
        quest_id=quest_row["id"],
        currency=quest_row.get("currency", "RUB"),
    )

    await _record_quest_status_history(
        conn,
        quest_row["id"],
        quest_row.get("status"),
        "cancelled",
        changed_by=admin_id,
        note=note,
        created_at=now,
    )

    await notification_service.create_notification(
        conn,
        user_id=quest_row["client_id"],
        title="Квест отменён администратором",
        message=user_message,
        event_type="admin_quest_cancelled",
    )

    if quest_row.get("assigned_to") and quest_row["assigned_to"] != quest_row["client_id"]:
        await notification_service.create_notification(
            conn,
            user_id=quest_row["assigned_to"],
            title="Квест отменён администратором",
            message=user_message,
            event_type="admin_quest_cancelled",
        )

    return refund_result is not None


# ──────────────────────────────────────────────────────────────────────
# Audit log
# ──────────────────────────────────────────────────────────────────────

async def log_admin_action(
    conn: asyncpg.Connection,
    admin_id: str,
    action: str,
    target_type: str,
    target_id: str,
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
    ip_address: Optional[str] = None,
    command_id: Optional[str] = None,
    job_id: Optional[str] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> str:
    """Insert an immutable audit record. Must be inside a transaction."""
    _assert_in_transaction(conn)

    log_id = f"alog_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO admin_logs
            (id, admin_id, action, target_type, target_id,
             old_value, new_value, ip_address,
             command_id, job_id, request_id, trace_id, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """,
        log_id,
        admin_id,
        action,
        target_type,
        target_id,
        json.dumps(_json_safe(old_value)) if old_value is not None else None,
        json.dumps(_json_safe(new_value)) if new_value is not None else None,
        ip_address,
        command_id,
        job_id,
        request_id,
        trace_id,
        now,
    )

    logger.info(
        f"[AUDIT] admin={admin_id} action={action} "
        f"target={target_type}/{target_id}"
    )
    return log_id


# ──────────────────────────────────────────────────────────────────────
# User management (read-only)
# ──────────────────────────────────────────────────────────────────────

async def list_users(
    conn: asyncpg.Connection,
    page: int = 1,
    page_size: int = 50,
    role_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """Return paginated list of users for the admin dashboard."""
    base = "FROM users WHERE 1=1"
    args: list = []
    idx = 1

    if role_filter:
        base += f" AND role = ${idx}"
        args.append(role_filter)
        idx += 1

    if search and search.strip():
        base += f" AND (username ILIKE ${idx} OR email ILIKE ${idx})"
        args.append(f"%{_escape_like(search.strip())}%")
        idx += 1

    total = await conn.fetchval(f"SELECT COUNT(*) {base}", *args)

    rows = await conn.fetch(
        f"""
        SELECT id, username, email, role, grade, level, xp, is_banned, banned_reason, created_at
        {base}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *args,
        page_size,
        (page - 1) * page_size,
    )

    return {
        "users": [dict(r) for r in rows],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < (total or 0),
    }


async def list_quests(
    conn: asyncpg.Connection,
    page: int = 1,
    page_size: int = 50,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """Return paginated list of quests for the admin dashboard."""
    base = "FROM quests WHERE 1=1"
    args: list = []
    idx = 1

    if status_filter:
        base += f" AND status = ${idx}"
        args.append(status_filter)
        idx += 1

    if search and search.strip():
        base += f" AND (title ILIKE ${idx} OR id ILIKE ${idx})"
        args.append(f"%{_escape_like(search.strip())}%")
        idx += 1

    total = await conn.fetchval(f"SELECT COUNT(*) {base}", *args)

    rows = await conn.fetch(
        f"""
        SELECT id, title, status, budget, currency, required_grade, is_urgent,
               client_id, assigned_to, created_at, updated_at
        {base}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *args,
        page_size,
        (page - 1) * page_size,
    )

    return {
        "quests": [dict(r) for r in rows],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < (total or 0),
    }


# ──────────────────────────────────────────────────────────────────────
# Transaction history (read-only)
# ──────────────────────────────────────────────────────────────────────

async def list_transactions(
    conn: asyncpg.Connection,
    page: int = 1,
    page_size: int = 50,
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
    user_id_filter: Optional[str] = None,
) -> dict:
    """Return paginated transactions with optional filters."""
    base = "FROM transactions WHERE 1=1"
    args: list = []
    idx = 1

    if status_filter:
        base += f" AND status = ${idx}"
        args.append(status_filter)
        idx += 1
    if type_filter:
        base += f" AND type = ${idx}"
        args.append(type_filter)
        idx += 1
    if user_id_filter:
        base += f" AND user_id = ${idx}"
        args.append(user_id_filter)
        idx += 1

    total = await conn.fetchval(f"SELECT COUNT(*) {base}", *args)

    rows = await conn.fetch(
        f"""
        SELECT id, user_id, type, amount, currency, status, quest_id, created_at
        {base}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *args,
        page_size,
        (page - 1) * page_size,
    )

    return {
        "transactions": [dict(r) for r in rows],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < (total or 0),
    }


async def list_pending_withdrawals(
    conn: asyncpg.Connection,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Shortcut to list only pending withdrawal transactions."""
    return await list_transactions(
        conn,
        page=page,
        page_size=page_size,
        status_filter="pending",
        type_filter="withdrawal",
    )


# ──────────────────────────────────────────────────────────────────────
# Withdrawal management (write — requires transaction)
# ──────────────────────────────────────────────────────────────────────

async def approve_withdrawal(
    conn: asyncpg.Connection,
    transaction_id: str,
    admin_id: str,
    ip_address: Optional[str] = None,
    command_id: Optional[str] = None,
    job_id: Optional[str] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> dict:
    """
    Mark a pending withdrawal as completed.

    NOTE: Funds were already deducted from the user's wallet when the
    withdrawal was *requested* (create_withdrawal). Approval here is
    an operational/compliance step only — it does NOT move money again.

    Must be inside an existing DB transaction.
    """
    _assert_in_transaction(conn)

    tx = await conn.fetchrow(
        "SELECT id, type, status FROM transactions WHERE id = $1 FOR UPDATE",
        transaction_id,
    )
    if not tx:
        raise ValueError(f"Transaction {transaction_id} not found")
    if tx["type"] != "withdrawal":
        raise ValueError(f"Transaction {transaction_id} is not a withdrawal")
    if tx["status"] != "pending":
        raise ValueError(
            f"Withdrawal {transaction_id} is already {tx['status']}; expected 'pending'"
        )

    await conn.execute(
        "UPDATE transactions SET status = 'completed' WHERE id = $1",
        transaction_id,
    )

    await log_admin_action(
        conn,
        admin_id=admin_id,
        action="withdrawal_approved",
        target_type="transaction",
        target_id=transaction_id,
        old_value={"status": "pending"},
        new_value={"status": "completed"},
        ip_address=ip_address,
        command_id=command_id,
        job_id=job_id,
        request_id=request_id,
        trace_id=trace_id,
    )

    logger.info(
        f"Withdrawal {transaction_id} approved by admin {admin_id}. "
        f"Amount: {tx['amount']} {tx['currency']} for user {tx['user_id']}"
    )

    return {
        "transaction_id": transaction_id,
        "status": "completed",
        "user_id": tx["user_id"],
        "amount": tx["amount"],
        "currency": tx["currency"],
    }


async def reject_withdrawal(
    conn: asyncpg.Connection,
    transaction_id: str,
    admin_id: str,
    reason: str,
    ip_address: Optional[str] = None,
    command_id: Optional[str] = None,
    job_id: Optional[str] = None,
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> dict:
    """
    Reject a pending withdrawal and **refund** the amount back to the user.

    When a withdrawal is *requested* the funds are immediately deducted
    (pessimistic). Rejection must reverse that deduction.

    Must be inside an existing DB transaction.
    """
    _assert_in_transaction(conn)

    tx = await conn.fetchrow(
        "SELECT id, type, status FROM transactions WHERE id = $1 FOR UPDATE",
        transaction_id,
    )
    if not tx:
        raise ValueError(f"Transaction {transaction_id} not found")
    if tx["type"] != "withdrawal":
        raise ValueError(f"Transaction {transaction_id} is not a withdrawal")
    if tx["status"] != "pending":
        raise ValueError(
            f"Withdrawal {transaction_id} is already {tx['status']}; expected 'pending'"
        )

    await conn.execute(
        "UPDATE transactions SET status = 'rejected' WHERE id = $1",
        transaction_id,
    )

    # Refund — credit amount back to user's wallet
    new_balance = await wallet_service.credit(
        conn,
        user_id=tx["user_id"],
        amount=tx["amount"],
        currency=tx["currency"],
        tx_type="refund",
    )

    await log_admin_action(
        conn,
        admin_id=admin_id,
        action="withdrawal_rejected",
        target_type="transaction",
        target_id=transaction_id,
        old_value={"status": "pending"},
        new_value={"status": "rejected", "reason": reason, "refunded_amount": str(tx["amount"])},
        ip_address=ip_address,
        command_id=command_id,
        job_id=job_id,
        request_id=request_id,
        trace_id=trace_id,
    )

    logger.info(
        f"Withdrawal {transaction_id} rejected by admin {admin_id}. "
        f"Reason: {reason}. Refunded {tx['amount']} {tx['currency']} to user {tx['user_id']}"
    )

    return {
        "transaction_id": transaction_id,
        "status": "rejected",
        "user_id": tx["user_id"],
        "amount": tx["amount"],
        "currency": tx["currency"],
        "reason": reason,
        "new_balance": new_balance,
    }


# ──────────────────────────────────────────────────────────────────────
# Admin logs (read-only)
# ──────────────────────────────────────────────────────────────────────

async def get_admin_logs(
    conn: asyncpg.Connection,
    page: int = 1,
    page_size: int = 50,
    admin_id_filter: Optional[str] = None,
) -> dict:
    """Return paginated admin audit log entries."""
    base = "FROM admin_logs WHERE 1=1"
    args: list = []
    idx = 1

    if admin_id_filter:
        base += f" AND admin_id = ${idx}"
        args.append(admin_id_filter)
        idx += 1

    total = await conn.fetchval(f"SELECT COUNT(*) {base}", *args)

    rows = await conn.fetch(
        f"""
        SELECT id, admin_id, action, target_type, target_id,
               old_value, new_value, ip_address, created_at
        {base}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *args,
        page_size,
        (page - 1) * page_size,
    )

    return {
        "logs": [dict(r) for r in rows],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
    }


# ──────────────────────────────────────────────────────────────────────
# Data hygiene
# ──────────────────────────────────────────────────────────────────────

async def cleanup_old_notifications(conn: asyncpg.Connection) -> int:
    """
    Delete read notifications older than NOTIFICATION_RETENTION_DAYS days.

    Safe to run outside a transaction (single-statement DELETE).
    Returns the number of rows deleted.
    """
    # P1 H-01 FIX: Use parameterized query instead of f-string for SQL safety
    result = await conn.execute(
        """
        DELETE FROM notifications
        WHERE is_read = TRUE
          AND created_at < NOW() - make_interval(days => $1)
        """,
        settings.NOTIFICATION_RETENTION_DAYS,
    )
    try:
        count = int(result.split()[-1])
    except (IndexError, ValueError):
        count = 0

    logger.info(f"Notification cleanup: deleted {count} old read notifications")
    return count


# ──────────────────────────────────────────────────────────────────────
# GOD MODE — User detail
# ──────────────────────────────────────────────────────────────────────

async def get_user_detail(conn: asyncpg.Connection, user_id: str) -> dict:
    """Full user profile + wallets + class info + badges for admin view."""
    user = await conn.fetchrow(
        f"SELECT {_ADMIN_USER_DETAIL_COLUMNS} FROM users WHERE id = $1",
        user_id,
    )
    if not user:
        raise ValueError(f"User {user_id} not found")

    user_dict = dict(user)
    user_dict["skills"] = _normalize_json_list(user_dict.get("skills"))

    # Wallets
    wallets = await conn.fetch(
        "SELECT id, currency, balance, updated_at FROM wallets WHERE user_id = $1", user_id
    )
    user_dict["wallets"] = [dict(w) for w in wallets]

    # Badges
    badges = await conn.fetch(
        """
        SELECT ub.badge_id, b.name, b.description, b.icon, ub.earned_at
        FROM user_badges ub JOIN badges b ON ub.badge_id = b.id
        WHERE ub.user_id = $1
        ORDER BY ub.earned_at DESC
        """,
        user_id,
    )
    user_dict["badges_list"] = [dict(b) for b in badges]

    # Class progress
    cp = await conn.fetchrow(
        "SELECT * FROM user_class_progress WHERE user_id = $1", user_id
    )
    if cp:
        cp_dict = dict(cp)
        cfg = get_class_config(cp_dict["class_id"])
        bonus_perk_points = cp_dict.get("bonus_perk_points", 0)
        perk_points_total = bonus_perk_points
        if cfg is not None:
            perk_points_total += calculate_perk_points_available(
                cp_dict.get("class_level", 1),
                cfg.perk_points_per_level,
            )
        cp_dict["bonus_perk_points"] = bonus_perk_points
        cp_dict["perk_points_total"] = perk_points_total
        cp_dict["perk_points_available"] = perk_points_total - cp_dict.get("perk_points_spent", 0)
        user_dict["class_progress"] = cp_dict
    else:
        user_dict["class_progress"] = None

    # Perks
    perks = await conn.fetch(
        "SELECT perk_id, class_id, unlocked_at FROM user_perks WHERE user_id = $1", user_id
    )
    user_dict["perks"] = [dict(p) for p in perks]

    return user_dict


# ──────────────────────────────────────────────────────────────────────
# GOD MODE — Update user fields
# ──────────────────────────────────────────────────────────────────────

# Allowed fields for partial update (column → SQL type cast or None)
_USER_UPDATABLE_FIELDS = {
    "role": None,
    "level": "::INTEGER",
    "grade": None,
    "xp": "::INTEGER",
    "xp_to_next": "::INTEGER",
    "stat_points": "::INTEGER",
    "stats_int": "::INTEGER",
    "stats_dex": "::INTEGER",
    "stats_cha": "::INTEGER",
    "bio": None,
    "skills": "::JSONB",
    "character_class": None,
}


async def update_user(
    conn: asyncpg.Connection,
    user_id: str,
    fields: Dict[str, Any],
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """
    Partial update of user fields. Only updates provided keys.
    Must be inside a transaction.
    """
    _assert_in_transaction(conn)

    # P0 F-03: prevent self-modification
    if user_id == admin_id:
        raise ValueError("Cannot modify your own account")

    # P0 F-04: block role escalation to admin
    if fields.get("role") == "admin":
        raise ValueError("Cannot set role to admin via update_user")

    # Fetch old values
    old_row = await conn.fetchrow(
        f"SELECT {_ADMIN_USER_UPDATE_COLUMNS} FROM users WHERE id = $1 FOR UPDATE",
        user_id,
    )
    if not old_row:
        raise ValueError(f"User {user_id} not found")

    old_values = {}
    new_values = {}
    set_clauses = []
    args = []
    idx = 1

    for key, value in fields.items():
        if key not in _USER_UPDATABLE_FIELDS:
            continue
        old_val = old_row.get(key)
        if key == "skills":
            value = _normalize_admin_skills(value)
            value = json.dumps(value)
        old_values[key] = old_val if not isinstance(old_val, (datetime,)) else str(old_val)
        new_values[key] = json.loads(value) if key == "skills" else value
        set_clauses.append(f"{key} = ${idx}")
        args.append(value)
        idx += 1

    if not set_clauses:
        raise ValueError("No valid fields to update")

    set_clauses.append(f"updated_at = ${idx}")
    args.append(datetime.now(timezone.utc))
    idx += 1

    args.append(user_id)
    await conn.execute(
        f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ${idx}",
        *args,
    )

    await log_admin_action(
        conn, admin_id=admin_id, action="user_updated",
        target_type="user", target_id=user_id,
        old_value=old_values, new_value=new_values,
        ip_address=ip_address,
    )

    logger.info(f"Admin {admin_id} updated user {user_id}: {list(new_values.keys())}")
    return {"user_id": user_id, "updated_fields": list(new_values.keys())}


# ──────────────────────────────────────────────────────────────────────
# GOD MODE — Ban / Unban
# ──────────────────────────────────────────────────────────────────────

async def ban_user(
    conn: asyncpg.Connection,
    user_id: str,
    reason: str,
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Ban a user: set is_banned, cancel their active quests, notify."""
    _assert_in_transaction(conn)

    row = await conn.fetchrow("SELECT id, username, role, is_banned FROM users WHERE id = $1 FOR UPDATE", user_id)
    if not row:
        raise ValueError(f"User {user_id} not found")
    if row["is_banned"]:
        raise ValueError(f"User {user_id} is already banned")
    if row["role"] == "admin":
        raise ValueError("Cannot ban an admin user")

    now = datetime.now(timezone.utc)
    await conn.execute(
        "UPDATE users SET is_banned = TRUE, banned_reason = $1, banned_at = $2, updated_at = $2 WHERE id = $3",
        reason, now, user_id,
    )

    quests_to_cancel = await conn.fetch(
        """
        SELECT id, title, client_id, assigned_to, status, currency
        FROM quests
        WHERE (assigned_to = $1 OR client_id = $1)
          AND status IN ('open', 'assigned', 'in_progress', 'revision_requested')
        FOR UPDATE
        """,
        user_id,
    )
    cancelled_count = 0
    for quest in quests_to_cancel:
        await _cancel_quest_with_invariants(
            conn,
            quest,
            admin_id=admin_id,
            note=f"Quest cancelled because user {user_id} was banned: {reason}",
            user_message=f"Квест «{quest['title']}» был отменён администратором. Причина: {reason}",
        )
        cancelled_count += 1

    await log_admin_action(
        conn, admin_id=admin_id, action="user_banned",
        target_type="user", target_id=user_id,
        old_value={"is_banned": False},
        new_value={"is_banned": True, "reason": reason, "quests_cancelled": cancelled_count},
        ip_address=ip_address,
    )

    # Notify user
    await notification_service.create_notification(
        conn, user_id=user_id,
        title="Аккаунт заблокирован",
        message=f"Ваш аккаунт был заблокирован администратором. Причина: {reason}",
        event_type="account_banned",
    )

    logger.warning(f"Admin {admin_id} banned user {user_id}: {reason}")
    return {
        "user_id": user_id,
        "username": row["username"],
        "is_banned": True,
        "reason": reason,
        "quests_cancelled": cancelled_count,
    }


async def unban_user(
    conn: asyncpg.Connection,
    user_id: str,
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Unban a user: clear ban fields, notify."""
    _assert_in_transaction(conn)

    row = await conn.fetchrow("SELECT id, username, is_banned, banned_reason FROM users WHERE id = $1 FOR UPDATE", user_id)
    if not row:
        raise ValueError(f"User {user_id} not found")
    if not row["is_banned"]:
        raise ValueError(f"User {user_id} is not banned")

    now = datetime.now(timezone.utc)
    await conn.execute(
        "UPDATE users SET is_banned = FALSE, banned_reason = NULL, banned_at = NULL, updated_at = $1 WHERE id = $2",
        now, user_id,
    )

    await log_admin_action(
        conn, admin_id=admin_id, action="user_unbanned",
        target_type="user", target_id=user_id,
        old_value={"is_banned": True, "reason": row["banned_reason"]},
        new_value={"is_banned": False},
        ip_address=ip_address,
    )

    await notification_service.create_notification(
        conn, user_id=user_id,
        title="Аккаунт разблокирован",
        message="Ваш аккаунт был разблокирован администратором.",
        event_type="account_unbanned",
    )

    logger.info(f"Admin {admin_id} unbanned user {user_id}")
    return {"user_id": user_id, "username": row["username"], "is_banned": False}


# ──────────────────────────────────────────────────────────────────────
# GOD MODE — Delete user (hard)
# ──────────────────────────────────────────────────────────────────────

async def delete_user(
    conn: asyncpg.Connection,
    user_id: str,
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Hard delete a user. Safeguards: no self-delete, no admin delete."""
    _assert_in_transaction(conn)

    if user_id == admin_id:
        raise ValueError("Cannot delete yourself")

    row = await conn.fetchrow("SELECT id, username, email, role FROM users WHERE id = $1 FOR UPDATE", user_id)
    if not row:
        raise ValueError(f"User {user_id} not found")
    if row["role"] == "admin":
        raise ValueError("Cannot delete an admin account")

    quests_to_cancel = await conn.fetch(
        """
        SELECT id, title, client_id, assigned_to, status, currency
        FROM quests
        WHERE (assigned_to = $1 OR client_id = $1)
          AND status IN ('open', 'assigned', 'in_progress', 'revision_requested')
        FOR UPDATE
        """,
        user_id,
    )
    for quest in quests_to_cancel:
        await _cancel_quest_with_invariants(
            conn,
            quest,
            admin_id=admin_id,
            note=f"Quest cancelled because user {user_id} is being deleted",
            user_message=f"Квест «{quest['title']}» был отменён администратором из-за удаления пользователя.",
        )

    client_quest_transaction_tail = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM transactions t
        JOIN quests q ON q.id = t.quest_id
        WHERE q.client_id = $1
        """,
        user_id,
    )
    if int(client_quest_transaction_tail or 0) > 0:
        raise ValueError("Cannot delete user with client-owned quests that have financial transaction history")

    # Remove quests owned by user (client_id ON DELETE RESTRICT requires explicit cleanup).
    # CASCADE will handle applications, messages, reviews linked to these quests.
    await conn.execute("DELETE FROM quests WHERE client_id = $1", user_id)

    # P0 D-04 FIX: Preserve audit trail — set target_id to NULL instead of deleting
    await conn.execute(
        "UPDATE admin_logs SET target_id = NULL WHERE target_type = 'user' AND target_id = $1",
        user_id,
    )

    # P0 D-04 FIX: Preserve financial records — set user_id to NULL instead of cascade-deleting
    await conn.execute(
        "UPDATE transactions SET user_id = NULL WHERE user_id = $1",
        user_id,
    )

    # Delete cascaded data (wallets, notifications, badges, perks, abilities handled by FK CASCADE)
    await conn.execute("DELETE FROM users WHERE id = $1", user_id)

    await log_admin_action(
        conn, admin_id=admin_id, action="user_deleted",
        target_type="user", target_id=user_id,
        old_value={"username": row["username"], "email": row["email"], "role": row["role"]},
        new_value=None,
        ip_address=ip_address,
    )

    logger.warning(f"Admin {admin_id} deleted user {user_id} ({row['username']})")
    return {"user_id": user_id, "username": row["username"], "deleted": True}


# ──────────────────────────────────────────────────────────────────────
# GOD MODE — Grant XP
# ──────────────────────────────────────────────────────────────────────

async def grant_xp(
    conn: asyncpg.Connection,
    user_id: str,
    amount: int,
    reason: str,
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Grant XP to a user. Triggers level-up and grade promotion checks."""
    _assert_in_transaction(conn)

    # P0 F-03: prevent self-XP-grant
    if user_id == admin_id:
        raise ValueError("Cannot grant XP to yourself")

    row = await conn.fetchrow(
        "SELECT id, username, xp, level, grade, stats_int, stats_dex, stats_cha FROM users WHERE id = $1 FOR UPDATE",
        user_id,
    )
    if not row:
        raise ValueError(f"User {user_id} not found")

    old_xp = row["xp"]
    old_level = row["level"]
    old_grade = row["grade"]

    new_xp = max(0, old_xp + amount)  # allow negative (revoke XP) but floor at 0

    # Check level-up
    grade_enum = GradeEnum(old_grade)
    level_up, new_grade_enum, new_level, _ = check_level_up(new_xp, grade_enum)
    new_grade = new_grade_enum.value
    xp_to_next_val = calculate_xp_to_next(new_xp, new_grade_enum)

    # Stat growth if leveled up
    stat_delta = {"int": 0, "dex": 0, "cha": 0}
    levels_gained = max(0, new_level - old_level)
    if levels_gained > 0:
        stat_delta = allocate_stat_points(levels_gained)

    await conn.execute(
        """
        UPDATE users
        SET xp = $1, level = $2, grade = $3, xp_to_next = $4,
            stats_int = LEAST(stats_int + $5, 100), stats_dex = LEAST(stats_dex + $6, 100), stats_cha = LEAST(stats_cha + $7, 100),
            updated_at = $8
        WHERE id = $9
        """,
        new_xp, new_level, new_grade, xp_to_next_val,
        stat_delta.get("int", 0), stat_delta.get("dex", 0), stat_delta.get("cha", 0),
        datetime.now(timezone.utc), user_id,
    )

    await log_admin_action(
        conn, admin_id=admin_id, action="xp_granted",
        target_type="user", target_id=user_id,
        old_value={"xp": old_xp, "level": old_level, "grade": old_grade},
        new_value={"xp": new_xp, "level": new_level, "grade": new_grade, "amount": amount, "reason": reason},
        ip_address=ip_address,
    )

    action_verb = "начислено" if amount >= 0 else "снято"
    await notification_service.create_notification(
        conn, user_id=user_id,
        title=f"XP {action_verb} администратором",
        message=f"Вам {action_verb} {abs(amount)} XP. Причина: {reason}",
        event_type="admin_xp_grant",
    )

    result = {
        "user_id": user_id, "username": row["username"],
        "old_xp": old_xp, "new_xp": new_xp, "amount": amount,
        "old_level": old_level, "new_level": new_level,
        "old_grade": old_grade, "new_grade": new_grade,
        "level_up": level_up, "levels_gained": levels_gained,
    }
    logger.info(f"Admin {admin_id} granted {amount} XP to {user_id}: {result}")
    return result


# ──────────────────────────────────────────────────────────────────────
# GOD MODE — Adjust wallet
# ──────────────────────────────────────────────────────────────────────

async def adjust_wallet(
    conn: asyncpg.Connection,
    user_id: str,
    amount: Decimal,
    currency: str,
    reason: str,
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """
    Credit (positive amount) or debit (negative amount) a user's wallet.
    Uses wallet_service for atomic balance updates.
    """
    _assert_in_transaction(conn)

    # P0 F-03: prevent self-wallet-adjustment
    if user_id == admin_id:
        raise ValueError("Cannot adjust your own wallet")

    amount = wallet_service.quantize_money(amount)

    row = await conn.fetchrow("SELECT id, username FROM users WHERE id = $1", user_id)
    if not row:
        raise ValueError(f"User {user_id} not found")

    old_balance = await wallet_service.get_balance(conn, user_id, currency)

    if amount > 0:
        new_balance = await wallet_service.credit(
            conn, user_id=user_id, amount=amount, currency=currency, tx_type="admin_adjust",
        )
    elif amount < 0:
        new_balance = await wallet_service.debit(
            conn, user_id=user_id, amount=abs(amount), currency=currency, tx_type="admin_adjust",
        )
    else:
        raise ValueError("Amount must be non-zero")

    await log_admin_action(
        conn, admin_id=admin_id, action="wallet_adjusted",
        target_type="user", target_id=user_id,
        old_value={"balance": old_balance, "currency": currency},
        new_value={"balance": new_balance, "currency": currency, "adjustment": amount, "reason": reason},
        ip_address=ip_address,
    )

    action_verb = "начислено" if amount > 0 else "снято"
    await notification_service.create_notification(
        conn, user_id=user_id,
        title=f"Баланс изменён администратором",
        message=f"На ваш кошелёк {action_verb} {abs(amount)} {currency}. Причина: {reason}",
        event_type="admin_wallet_adjust",
    )

    logger.info(f"Admin {admin_id} adjusted wallet for {user_id}: {amount} {currency}")
    return {
        "user_id": user_id, "username": row["username"],
        "old_balance": old_balance, "new_balance": new_balance,
        "amount": amount, "currency": currency, "reason": reason,
    }


# ──────────────────────────────────────────────────────────────────────
# GOD MODE — Quest management
# ──────────────────────────────────────────────────────────────────────

async def get_quest_detail(conn: asyncpg.Connection, quest_id: str) -> dict:
    """Full quest detail with applications for admin view."""
    quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise ValueError(f"Quest {quest_id} not found")

    quest_dict = dict(quest)
    quest_dict["skills"] = _normalize_json_list(quest_dict.get("skills"))

    apps = await conn.fetch(
        "SELECT * FROM applications WHERE quest_id = $1 ORDER BY created_at DESC", quest_id
    )
    quest_dict["applications"] = [dict(a) for a in apps]

    return quest_dict


async def update_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    fields: Dict[str, Any],
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Partial update of quest fields."""
    _assert_in_transaction(conn)

    allowed_fields = {"title", "description", "budget", "xp_reward", "required_grade", "status", "assigned_to", "is_urgent", "deadline", "required_portfolio"}
    protected_financial_fields = {"budget", "status", "assigned_to"}

    old_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id)
    if not old_row:
        raise ValueError(f"Quest {quest_id} not found")

    requested_fields = {key for key in fields if key in allowed_fields}
    if requested_fields & protected_financial_fields:
        hold_row = await conn.fetchrow(
            """
            SELECT id FROM transactions
            WHERE quest_id = $1 AND type = 'hold' AND status = 'held'
            LIMIT 1
            """,
            quest_id,
        )
        financialized = bool(hold_row) or bool(old_row.get("assigned_to")) or old_row.get("status") not in {"draft", "open"}
        if financialized:
            blocked = ", ".join(sorted(requested_fields & protected_financial_fields))
            raise ValueError(f"Cannot update {blocked} after escrow hold exists or quest is already financialized")

    # Validate status transitions
    if "status" in fields and fields["status"] in allowed_fields:
        pass  # field is in allowed_fields — checked below
    if "status" in fields:
        new_status = fields["status"]
        if new_status not in QuestStatusEnum.__members__:
            raise ValueError(f"Invalid status: {new_status}")
        current_status = old_row["status"]
        _ALLOWED_TRANSITIONS: Dict[str, set] = {
            "draft": {"open", "cancelled"},
            "open": {"draft", "assigned", "cancelled"},
            "assigned": {"in_progress", "open", "cancelled"},
            "in_progress": {"completed", "cancelled"},
            "completed": {"confirmed", "revision_requested", "cancelled"},
            "revision_requested": {"in_progress", "completed", "cancelled"},
            "confirmed": set(),
            "cancelled": set(),
        }
        allowed_next = _ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed_next:
            raise ValueError(f"Cannot transition quest from '{current_status}' to '{new_status}'")

    old_values = {}
    new_values = {}
    set_clauses = []
    args = []
    idx = 1

    for key, value in fields.items():
        if key not in allowed_fields:
            continue
        old_val = old_row.get(key)
        old_values[key] = str(old_val) if isinstance(old_val, (datetime,)) else old_val
        new_values[key] = value
        set_clauses.append(f"{key} = ${idx}")
        args.append(value)
        idx += 1

    if not set_clauses:
        raise ValueError("No valid fields to update")

    set_clauses.append(f"updated_at = ${idx}")
    args.append(datetime.now(timezone.utc))
    idx += 1

    args.append(quest_id)
    await conn.execute(
        f"UPDATE quests SET {', '.join(set_clauses)} WHERE id = ${idx}",
        *args,
    )

    await log_admin_action(
        conn, admin_id=admin_id, action="quest_updated",
        target_type="quest", target_id=quest_id,
        old_value=old_values, new_value=new_values,
        ip_address=ip_address,
    )

    # Notify quest client
    await notification_service.create_notification(
        conn, user_id=old_row["client_id"],
        title="Квест обновлён администратором",
        message=f"Квест «{old_row['title']}» был изменён администратором. Поля: {', '.join(new_values.keys())}",
        event_type="admin_quest_update",
    )

    logger.info(f"Admin {admin_id} updated quest {quest_id}: {list(new_values.keys())}")
    return {"quest_id": quest_id, "updated_fields": list(new_values.keys())}


async def force_cancel_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    reason: str,
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Force-cancel a quest regardless of current status."""
    _assert_in_transaction(conn)

    row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id)
    if not row:
        raise ValueError(f"Quest {quest_id} not found")
    if row["status"] == "cancelled":
        raise ValueError(f"Quest {quest_id} is already cancelled")

    old_status = row["status"]
    refund_result = await _cancel_quest_with_invariants(
        conn,
        row,
        admin_id=admin_id,
        note=f"Quest force-cancelled by admin: {reason}",
        user_message=f"Квест «{row['title']}» был принудительно отменён. Причина: {reason}",
    )

    await log_admin_action(
        conn, admin_id=admin_id, action="quest_force_cancelled",
        target_type="quest", target_id=quest_id,
        old_value={"status": old_status},
        new_value={"status": "cancelled", "reason": reason, "escrow_refunded": refund_result},
        ip_address=ip_address,
    )

    logger.warning(f"Admin {admin_id} force-cancelled quest {quest_id}: {reason}")
    return {
        "quest_id": quest_id, "old_status": old_status,
        "new_status": "cancelled", "reason": reason,
    }


async def force_complete_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    reason: str,
    admin_id: str,
    ip_address: Optional[str] = None,
    skip_escrow: bool = False,
) -> dict:
    """Force-complete a quest: set status to 'confirmed' AND trigger payment + XP.

    P2 Q-01 FIX: Previously skipped payment/XP, leaving the freelancer unpaid.
    Now performs the same reward logic as confirm_quest_completion.
    """
    _assert_in_transaction(conn)

    row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id)
    if not row:
        raise ValueError(f"Quest {quest_id} not found")
    if row["status"] in ("confirmed", "cancelled"):
        raise ValueError(f"Quest {quest_id} is already {row['status']}")

    # P1 Q-06: only allow force-complete for quests that have work in progress
    if row["status"] in ("draft", "open"):
        raise ValueError(f"Cannot force-complete quest in '{row['status']}' status — no work has been done")

    old_status = row["status"]
    now = datetime.now(timezone.utc)

    await conn.execute(
        "UPDATE quests SET status = 'confirmed', completed_at = $1, updated_at = $1 WHERE id = $2",
        now, quest_id,
    )

    # Trigger payment + XP if freelancer is assigned
    split_result = None
    xp_reward = 0
    guild_economy_result = None
    if row["assigned_to"]:
        hold_row = await conn.fetchrow(
            """
            SELECT id FROM transactions
            WHERE user_id = $1 AND quest_id = $2 AND type = 'hold' AND status = 'held' AND currency = $3
            FOR UPDATE
            """,
            row["client_id"],
            quest_id,
            row.get("currency", "RUB"),
        )
        if not hold_row:
            if not skip_escrow:
                raise ValueError(
                    "Admin force-complete requires an active escrow hold. "
                    "Pass skip_escrow=True to override (no payment will be made to freelancer)."
                )
            logger.warning(
                f"[AUDIT] Admin force-complete with no escrow hold: "
                f"quest={quest_id}, admin action, skip_escrow=True"
            )

        # XP reward for freelancer
        freelancer_row = await conn.fetchrow(
            f"SELECT {_USER_PROGRESS_COLUMNS} FROM users WHERE id = $1 FOR UPDATE",
            row["assigned_to"],
        )
        if freelancer_row:
            from app.core.rewards import calculate_quest_rewards as _calc_rewards
            quest_grade = GradeEnum(row["required_grade"])
            freelancer_grade = GradeEnum(freelancer_row["grade"])
            xp_reward = _calc_rewards(
                budget=row["budget"], quest_grade=quest_grade,
                user_grade=freelancer_grade,
            )
            new_xp = freelancer_row["xp"] + xp_reward
            level_up, new_grade, new_level, _ = check_level_up(new_xp, freelancer_grade)
            new_xp_to_next = calculate_xp_to_next(new_xp, new_grade)
            levels_gained = new_level - freelancer_row["level"]
            stat_delta = allocate_stat_points(levels_gained) if levels_gained > 0 else {"int": 0, "dex": 0, "cha": 0, "unspent": 0}
            _STAT_CAP = 100
            new_stats_int = min(_STAT_CAP, freelancer_row["stats_int"] + stat_delta["int"])
            new_stats_dex = min(_STAT_CAP, freelancer_row["stats_dex"] + stat_delta["dex"])
            new_stats_cha = min(_STAT_CAP, freelancer_row["stats_cha"] + stat_delta["cha"])
            new_stat_points = freelancer_row.get("stat_points", 0) + stat_delta["unspent"]
            await conn.execute(
                """UPDATE users SET xp=$1, level=$2, grade=$3, xp_to_next=$4,
                       stats_int=$5, stats_dex=$6, stats_cha=$7,
                       stat_points=stat_points+$8, updated_at=$9
                   WHERE id=$10""",
                new_xp, new_level, new_grade.value, new_xp_to_next,
                new_stats_int, new_stats_dex, new_stats_cha, stat_delta["unspent"],
                now, row["assigned_to"],
            )

            # Badge check (matching confirm_quest_completion)
            badge_event_data = {
                "quests_completed": await conn.fetchval(
                    "SELECT COUNT(*) FROM quests WHERE assigned_to = $1 AND status = 'confirmed'",
                    row["assigned_to"],
                ),
                "xp": new_xp,
                "level": new_level,
                "grade": new_grade.value,
                "earnings": row["budget"],
            }
            await badge_service.check_and_award(
                conn, row["assigned_to"], "quest_completed", badge_event_data
            )

            # Class XP (matching confirm_quest_completion)
            await class_service.add_class_xp(
                conn, row["assigned_to"],
                xp_reward,
                is_urgent=bool(row["is_urgent"]) if "is_urgent" in row.keys() else False,
                required_portfolio=bool(row.get("required_portfolio", False)),
            )

        # Payment split — only if escrow hold exists
        if hold_row:
            split_result = await wallet_service.split_payment(
                conn,
                client_id=row["client_id"],
                freelancer_id=row["assigned_to"],
                gross_amount=row["budget"],
                currency=row.get("currency", "RUB"),
                quest_id=quest_id,
                fee_percent=row.get("platform_fee_percent"),
            )
            guild_economy_result = await guild_economy_service.apply_quest_completion_rewards(
                conn,
                quest_id=quest_id,
                freelancer_id=row["assigned_to"],
                gross_amount=row["budget"],
                platform_fee=split_result["platform_fee"],
                xp_reward=xp_reward,
                is_urgent=bool(row["is_urgent"]) if "is_urgent" in row else False,
                confirmed_at=now,
                source="admin_force_complete",
            )
            if guild_economy_result is None:
                await guild_economy_service.award_solo_artifact_drop(
                    conn,
                    quest_id=quest_id,
                    freelancer_id=row["assigned_to"],
                    gross_amount=row["budget"],
                    platform_fee=split_result["platform_fee"],
                    xp_reward=xp_reward,
                    is_urgent=bool(row["is_urgent"]) if "is_urgent" in row else False,
                    confirmed_at=now,
                )

    await log_admin_action(
        conn, admin_id=admin_id, action="quest_force_completed",
        target_type="quest", target_id=quest_id,
        old_value={"status": old_status},
        new_value={"status": "confirmed", "reason": reason, "payment_triggered": split_result is not None},
        ip_address=ip_address,
    )

    # Notify client
    await notification_service.create_notification(
        conn, user_id=row["client_id"],
        title="Квест завершён администратором",
        message=f"Квест «{row['title']}» был принудительно завершён. Причина: {reason}",
        event_type="admin_quest_completed",
    )

    if row["assigned_to"]:
        await notification_service.create_notification(
            conn, user_id=row["assigned_to"],
            title="Квест завершён администратором",
            message=f"Квест «{row['title']}» был принудительно завершён. Причина: {reason}",
            event_type="admin_quest_completed",
        )

    logger.warning(f"Admin {admin_id} force-completed quest {quest_id}: {reason}")
    return {
        "quest_id": quest_id, "old_status": old_status,
        "new_status": "confirmed", "reason": reason,
        "payment_triggered": split_result is not None,
        "xp_reward": xp_reward,
        "guild_economy": None if not guild_economy_result else {
            "guild_id": guild_economy_result["guild_id"],
            "guild_name": guild_economy_result["guild_name"],
            "treasury_delta": wallet_service.quantize_money(guild_economy_result["treasury_delta"]),
            "guild_tokens_delta": guild_economy_result["guild_tokens_delta"],
            "contribution_delta": guild_economy_result["contribution_delta"],
            "card_drop": guild_economy_result.get("card_drop"),
        },
    }


async def delete_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Hard delete a quest (CASCADE removes applications)."""
    _assert_in_transaction(conn)

    row = await conn.fetchrow("SELECT id, title, client_id, status FROM quests WHERE id = $1 FOR UPDATE", quest_id)
    if not row:
        raise ValueError(f"Quest {quest_id} not found")

    active_hold_count = await conn.fetchval(
        """
        SELECT COUNT(*) FROM transactions
        WHERE quest_id = $1 AND type = 'hold' AND status = 'held'
        """,
        quest_id,
    )
    if int(active_hold_count or 0) > 0:
        raise ValueError("Cannot delete quest with active escrow hold; cancel and unwind funds first")

    transaction_count = await conn.fetchval(
        "SELECT COUNT(*) FROM transactions WHERE quest_id = $1",
        quest_id,
    )
    if int(transaction_count or 0) > 0:
        raise ValueError("Cannot delete financialized quest with transaction history")

    await conn.execute("DELETE FROM quests WHERE id = $1", quest_id)

    await log_admin_action(
        conn, admin_id=admin_id, action="quest_deleted",
        target_type="quest", target_id=quest_id,
        old_value={"title": row["title"], "status": row["status"], "client_id": row["client_id"]},
        new_value=None,
        ip_address=ip_address,
    )

    await notification_service.create_notification(
        conn, user_id=row["client_id"],
        title="Квест удалён администратором",
        message=f"Квест «{row['title']}» был удалён администратором.",
        event_type="admin_quest_deleted",
    )

    logger.warning(f"Admin {admin_id} deleted quest {quest_id} ({row['title']})")
    return {"quest_id": quest_id, "title": row["title"], "deleted": True}


# ──────────────────────────────────────────────────────────────────────
# GOD MODE — Badge management
# ──────────────────────────────────────────────────────────────────────

async def grant_badge(
    conn: asyncpg.Connection,
    user_id: str,
    badge_id: str,
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Award a badge to a user."""
    _assert_in_transaction(conn)

    user = await conn.fetchrow("SELECT id, username FROM users WHERE id = $1", user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    badge = await conn.fetchrow("SELECT id, name, icon FROM badges WHERE id = $1", badge_id)
    if not badge:
        raise ValueError(f"Badge {badge_id} not found")

    # Check duplicate
    existing = await conn.fetchval(
        "SELECT id FROM user_badges WHERE user_id = $1 AND badge_id = $2", user_id, badge_id
    )
    if existing:
        raise ValueError(f"User {user_id} already has badge {badge_id}")

    ub_id = f"ub_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    await conn.execute(
        "INSERT INTO user_badges (id, user_id, badge_id, earned_at) VALUES ($1, $2, $3, $4)",
        ub_id, user_id, badge_id, now,
    )

    await log_admin_action(
        conn, admin_id=admin_id, action="badge_granted",
        target_type="user", target_id=user_id,
        old_value=None,
        new_value={"badge_id": badge_id, "badge_name": badge["name"]},
        ip_address=ip_address,
    )

    await notification_service.create_notification(
        conn, user_id=user_id,
        title="Новый бейдж!",
        message=f"Администратор наградил вас бейджем {badge['icon']} «{badge['name']}».",
        event_type="admin_badge_grant",
    )

    return {"user_id": user_id, "badge_id": badge_id, "badge_name": badge["name"]}


async def revoke_badge(
    conn: asyncpg.Connection,
    user_id: str,
    badge_id: str,
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Revoke a badge from a user."""
    _assert_in_transaction(conn)

    badge = await conn.fetchrow("SELECT id, name FROM badges WHERE id = $1", badge_id)
    result = await conn.execute(
        "DELETE FROM user_badges WHERE user_id = $1 AND badge_id = $2", user_id, badge_id
    )
    if result == "DELETE 0":
        raise ValueError(f"User {user_id} does not have badge {badge_id}")

    await log_admin_action(
        conn, admin_id=admin_id, action="badge_revoked",
        target_type="user", target_id=user_id,
        old_value={"badge_id": badge_id, "badge_name": badge["name"] if badge else badge_id},
        new_value=None,
        ip_address=ip_address,
    )

    return {"user_id": user_id, "badge_id": badge_id, "revoked": True}


async def upsert_guild_season_reward_config(
    conn: asyncpg.Connection,
    payload: dict[str, Any],
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict[str, Any]:
    _assert_in_transaction(conn)

    season_code = str(payload["season_code"]).strip()
    family = str(payload["family"]).strip()
    family_meta = guild_card_service.SEASONAL_FAMILY_SETS.get(family)
    if not family_meta:
        raise ValueError(f"Unknown guild seasonal family: {family}")

    treasury_bonus = wallet_service.quantize_money(payload["treasury_bonus"])
    now = datetime.now(timezone.utc)
    existing = await conn.fetchrow(
        """
        SELECT id, season_code, family, label, accent, treasury_bonus, guild_tokens_bonus, badge_name, is_active
        FROM guild_season_reward_configs
        WHERE season_code = $1 AND family = $2
        """,
        season_code,
        family,
    )

    config_id = str(existing["id"]) if existing else f"gsrc_{uuid.uuid4().hex[:12]}"
    row = await conn.fetchrow(
        """
        INSERT INTO guild_season_reward_configs (
            id, season_code, family, label, accent, treasury_bonus,
            guild_tokens_bonus, badge_name, is_active, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $10)
        ON CONFLICT (season_code, family) DO UPDATE
            SET label = EXCLUDED.label,
                accent = EXCLUDED.accent,
                treasury_bonus = EXCLUDED.treasury_bonus,
                guild_tokens_bonus = EXCLUDED.guild_tokens_bonus,
                badge_name = EXCLUDED.badge_name,
                is_active = EXCLUDED.is_active,
                updated_at = EXCLUDED.updated_at
        RETURNING id, season_code, family, label, accent, treasury_bonus, guild_tokens_bonus, badge_name, is_active, created_at, updated_at
        """,
        config_id,
        season_code,
        family,
        str(payload["label"]).strip(),
        str(payload["accent"]).strip(),
        treasury_bonus,
        int(payload["guild_tokens_bonus"]),
        str(payload["badge_name"]).strip(),
        bool(payload.get("is_active", True)),
        now,
    )

    await log_admin_action(
        conn,
        admin_id=admin_id,
        action="guild_season_reward_config_upserted",
        target_type="guild_season_reward_config",
        target_id=f"{season_code}:{family}",
        old_value=dict(existing) if existing else None,
        new_value={
            "season_code": row["season_code"],
            "family": row["family"],
            "label": row["label"],
            "accent": row["accent"],
            "treasury_bonus": row["treasury_bonus"],
            "guild_tokens_bonus": row["guild_tokens_bonus"],
            "badge_name": row["badge_name"],
            "is_active": row["is_active"],
        },
        ip_address=ip_address,
    )

    return dict(row)


# ──────────────────────────────────────────────────────────────────────
# GOD MODE — Class override
# ──────────────────────────────────────────────────────────────────────

async def change_user_class(
    conn: asyncpg.Connection,
    user_id: str,
    class_id: Optional[str],
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """
    Force set or reset a user's class.
    class_id=None means reset (clear class).
    """
    _assert_in_transaction(conn)

    row = await conn.fetchrow("SELECT id, username, character_class FROM users WHERE id = $1 FOR UPDATE", user_id)
    if not row:
        raise ValueError(f"User {user_id} not found")

    old_class = row["character_class"]
    now = datetime.now(timezone.utc)

    if class_id:
        # Set new class
        await conn.execute(
            "UPDATE users SET character_class = $1, class_selected_at = $2, class_trial_expires_at = NULL, updated_at = $2 WHERE id = $3",
            class_id, now, user_id,
        )
        # Upsert class progress
        existing = await conn.fetchval(
            "SELECT user_id FROM user_class_progress WHERE user_id = $1", user_id
        )
        if existing:
            await conn.execute(
                "UPDATE user_class_progress SET class_id = $1, updated_at = $2 WHERE user_id = $3",
                class_id, now, user_id,
            )
        else:
            await conn.execute(
                """
                INSERT INTO user_class_progress (user_id, class_id, class_xp, class_level, quests_completed, consecutive_quests, updated_at)
                VALUES ($1, $2, 0, 1, 0, 0, $3)
                """,
                user_id, class_id, now,
            )
    else:
        # Reset class
        await conn.execute(
            "UPDATE users SET character_class = NULL, class_selected_at = NULL, class_trial_expires_at = NULL, updated_at = $1 WHERE id = $2",
            now, user_id,
        )
        await conn.execute("DELETE FROM user_class_progress WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM user_perks WHERE user_id = $1", user_id)
        await conn.execute("DELETE FROM user_abilities WHERE user_id = $1", user_id)

    await log_admin_action(
        conn, admin_id=admin_id, action="class_changed",
        target_type="user", target_id=user_id,
        old_value={"character_class": old_class},
        new_value={"character_class": class_id},
        ip_address=ip_address,
    )

    class_label = class_id or "нет (сброс)"
    await notification_service.create_notification(
        conn, user_id=user_id,
        title="Класс изменён администратором",
        message=f"Ваш класс был изменён на: {class_label}.",
        event_type="admin_class_change",
    )

    return {"user_id": user_id, "old_class": old_class, "new_class": class_id}


async def grant_class_perk_points(
    conn: asyncpg.Connection,
    user_id: str,
    amount: int,
    reason: str,
    admin_id: str,
    ip_address: Optional[str] = None,
) -> dict:
    """Grant bonus perk points for a user's class tree without changing class level."""
    _assert_in_transaction(conn)

    if amount <= 0:
        raise ValueError("Количество очков должно быть больше 0")

    user_row = await conn.fetchrow(
        "SELECT id, username, character_class FROM users WHERE id = $1 FOR UPDATE",
        user_id,
    )
    if not user_row:
        raise ValueError(f"User {user_id} not found")

    class_id = user_row["character_class"]
    if not class_id:
        raise ValueError("У пользователя нет активного класса")

    cfg = get_class_config(class_id)
    if cfg is None:
        raise ValueError(f"Неизвестный класс: {class_id}")

    now = datetime.now(timezone.utc)
    progress = await conn.fetchrow(
        "SELECT class_level, perk_points_spent, bonus_perk_points FROM user_class_progress WHERE user_id = $1 FOR UPDATE",
        user_id,
    )

    if progress:
        old_bonus = progress.get("bonus_perk_points", 0)
        class_level = progress.get("class_level", 1)
        perk_points_spent = progress.get("perk_points_spent", 0)
        new_bonus = old_bonus + amount
        await conn.execute(
            "UPDATE user_class_progress SET bonus_perk_points = $1, updated_at = $2 WHERE user_id = $3",
            new_bonus,
            now,
            user_id,
        )
    else:
        old_bonus = 0
        class_level = 1
        perk_points_spent = 0
        new_bonus = amount
        await conn.execute(
            """
            INSERT INTO user_class_progress (
                user_id, class_id, class_xp, class_level, quests_completed,
                consecutive_quests, perk_points_spent, bonus_perk_points, updated_at
            )
            VALUES ($1, $2, 0, 1, 0, 0, 0, $3, $4)
            """,
            user_id,
            class_id,
            new_bonus,
            now,
        )

    perk_points_total = calculate_perk_points_available(class_level, cfg.perk_points_per_level) + new_bonus
    perk_points_available = perk_points_total - perk_points_spent

    await log_admin_action(
        conn,
        admin_id=admin_id,
        action="class_perk_points_granted",
        target_type="user",
        target_id=user_id,
        old_value={"bonus_perk_points": old_bonus},
        new_value={
            "bonus_perk_points": new_bonus,
            "granted": amount,
            "reason": reason,
            "class_id": class_id,
        },
        ip_address=ip_address,
    )

    await notification_service.create_notification(
        conn,
        user_id=user_id,
        title="Очки перков начислены администратором",
        message=f"Вам начислено {amount} доп. очков перков для класса {cfg.name_ru}. Причина: {reason}",
        event_type="admin_perk_points_granted",
    )

    return {
        "user_id": user_id,
        "class_id": class_id,
        "granted": amount,
        "old_bonus_perk_points": old_bonus,
        "new_bonus_perk_points": new_bonus,
        "perk_points_total": perk_points_total,
        "perk_points_available": perk_points_available,
    }


# ──────────────────────────────────────────────────────────────────────
# GOD MODE — Broadcast notification
# ──────────────────────────────────────────────────────────────────────

async def broadcast_notification(
    conn: asyncpg.Connection,
    user_ids: List[str],
    title: str,
    message: str,
    event_type: str,
    admin_id: str,
    ip_address: Optional[str] = None,
    dry_run: bool = False,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Send a notification to multiple users.

    dry_run=True returns a preview of affected users without sending.
    idempotency_key prevents duplicate broadcasts.
    """
    _assert_in_transaction(conn)

    # ── Idempotency check ─────────────────────────────────────────────
    if idempotency_key:
        existing = await conn.fetchrow(
            """
            SELECT new_value FROM admin_logs
            WHERE action = 'notification_broadcast'
              AND new_value::jsonb ->> 'idempotency_key' = $1
            ORDER BY created_at DESC LIMIT 1
            """,
            idempotency_key,
        )
        if existing:
            prev = json.loads(existing["new_value"]) if existing["new_value"] else {}
            return {
                "total_recipients": prev.get("recipients", 0),
                "sent": prev.get("sent", 0),
                "title": prev.get("title", title),
                "duplicate": True,
                "idempotency_key": idempotency_key,
                "message": "Broadcast with this idempotency_key was already sent.",
            }

    recipient_ids = user_ids
    if not recipient_ids:
        rows = await conn.fetch("SELECT id FROM users")
        recipient_ids = [str(row["id"]) for row in rows]

    # P1-2 FIX: Batch-validate all user IDs in one query instead of N+1
    valid_ids_rows = await conn.fetch(
        "SELECT id, username FROM users WHERE id = ANY($1::text[])",
        recipient_ids,
    )
    valid_ids = {str(row["id"]) for row in valid_ids_rows}

    # ── Dry-run: preview without sending ──────────────────────────────
    if dry_run:
        preview_users = [
            {"id": str(row["id"]), "username": row["username"]}
            for row in valid_ids_rows
        ]
        return {
            "dry_run": True,
            "total_recipients": len(recipient_ids),
            "valid_recipients": len(valid_ids),
            "invalid_ids": [uid for uid in recipient_ids if uid not in valid_ids],
            "affected_users": preview_users[:50],
            "title": title,
            "message": message,
            "event_type": event_type,
        }

    # ── Actual send ───────────────────────────────────────────────────
    sent = 0
    for uid in recipient_ids:
        if uid in valid_ids:
            await notification_service.create_notification(
                conn, user_id=uid, title=title, message=message, event_type=event_type,
            )
            sent += 1

    log_new_value: Dict[str, Any] = {
        "recipients": len(recipient_ids),
        "sent": sent,
        "title": title,
    }
    if idempotency_key:
        log_new_value["idempotency_key"] = idempotency_key

    await log_admin_action(
        conn, admin_id=admin_id, action="notification_broadcast",
        target_type="system", target_id="broadcast",
        old_value=None,
        new_value=log_new_value,
        ip_address=ip_address,
    )

    result: Dict[str, Any] = {
        "total_recipients": len(recipient_ids),
        "sent": sent,
        "title": title,
    }
    if idempotency_key:
        result["idempotency_key"] = idempotency_key
        result["duplicate"] = False
    return result


# ──────────────────────────────────────────────────────────────────────
# GOD MODE — Platform stats
# ──────────────────────────────────────────────────────────────────────

async def get_platform_stats(conn: asyncpg.Connection) -> dict:
    """Aggregate platform-wide statistics for admin dashboard."""
    total_users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
    users_by_role = await conn.fetch(
        "SELECT role, COUNT(*) as cnt FROM users GROUP BY role"
    )
    banned_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_banned = TRUE") or 0

    total_quests = await conn.fetchval("SELECT COUNT(*) FROM quests") or 0
    quests_by_status = await conn.fetch(
        "SELECT status, COUNT(*) as cnt FROM quests GROUP BY status"
    )

    total_transactions = await conn.fetchval("SELECT COUNT(*) FROM transactions") or 0
    pending_withdrawals = await conn.fetchval(
        "SELECT COUNT(*) FROM transactions WHERE type = 'withdrawal' AND status = 'pending'"
    ) or 0
    total_revenue = await conn.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'commission' AND status = 'completed'"
    ) or 0

    today = datetime.now(timezone.utc).date()
    users_today = await conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE created_at::date = $1", today
    ) or 0
    quests_today = await conn.fetchval(
        "SELECT COUNT(*) FROM quests WHERE created_at::date = $1", today
    ) or 0

    return {
        "total_users": total_users,
        "users_by_role": {r["role"]: r["cnt"] for r in users_by_role},
        "banned_users": banned_users,
        "total_quests": total_quests,
        "quests_by_status": {r["status"]: r["cnt"] for r in quests_by_status},
        "total_transactions": total_transactions,
        "pending_withdrawals": pending_withdrawals,
        "total_revenue": total_revenue,
        "users_today": users_today,
        "quests_today": quests_today,
    }
