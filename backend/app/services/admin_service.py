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
from typing import Optional, List, Dict, Any

import asyncpg

from app.core.config import settings
from app.core.rewards import check_level_up, calculate_xp_to_next, allocate_stat_points, GRADE_XP_THRESHOLDS
from app.models.user import GradeEnum
from app.services import wallet_service, notification_service

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _assert_in_transaction(conn: asyncpg.Connection) -> None:
    if not conn.is_in_transaction():
        raise RuntimeError(
            "This admin_service function must be called inside an explicit DB transaction."
        )


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
) -> str:
    """Insert an immutable audit record. Must be inside a transaction."""
    _assert_in_transaction(conn)

    log_id = f"alog_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO admin_logs
            (id, admin_id, action, target_type, target_id,
             old_value, new_value, ip_address, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        log_id,
        admin_id,
        action,
        target_type,
        target_id,
        json.dumps(old_value) if old_value is not None else None,
        json.dumps(new_value) if new_value is not None else None,
        ip_address,
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
) -> dict:
    """Return paginated list of users for the admin dashboard."""
    base = "FROM users WHERE 1=1"
    args: list = []
    idx = 1

    if role_filter:
        base += f" AND role = ${idx}"
        args.append(role_filter)
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
        "SELECT * FROM transactions WHERE id = $1 FOR UPDATE",
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
    )

    logger.info(
        f"Withdrawal {transaction_id} approved by admin {admin_id}. "
        f"Amount: {tx['amount']} {tx['currency']} for user {tx['user_id']}"
    )

    return {
        "transaction_id": transaction_id,
        "status": "completed",
        "user_id": tx["user_id"],
        "amount": float(tx["amount"]),
        "currency": tx["currency"],
    }


async def reject_withdrawal(
    conn: asyncpg.Connection,
    transaction_id: str,
    admin_id: str,
    reason: str,
    ip_address: Optional[str] = None,
) -> dict:
    """
    Reject a pending withdrawal and **refund** the amount back to the user.

    When a withdrawal is *requested* the funds are immediately deducted
    (pessimistic). Rejection must reverse that deduction.

    Must be inside an existing DB transaction.
    """
    _assert_in_transaction(conn)

    tx = await conn.fetchrow(
        "SELECT * FROM transactions WHERE id = $1 FOR UPDATE",
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
        amount=float(tx["amount"]),
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
        new_value={"status": "rejected", "reason": reason, "refunded_amount": float(tx["amount"])},
        ip_address=ip_address,
    )

    logger.info(
        f"Withdrawal {transaction_id} rejected by admin {admin_id}. "
        f"Reason: {reason}. Refunded {tx['amount']} {tx['currency']} to user {tx['user_id']}"
    )

    return {
        "transaction_id": transaction_id,
        "status": "rejected",
        "user_id": tx["user_id"],
        "amount": float(tx["amount"]),
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
    result = await conn.execute(
        f"""
        DELETE FROM notifications
        WHERE is_read = TRUE
          AND created_at < NOW() - INTERVAL '{settings.NOTIFICATION_RETENTION_DAYS} days'
        """,
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
    user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    user_dict = dict(user)

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
    user_dict["class_progress"] = dict(cp) if cp else None

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

    # Fetch old values
    old_row = await conn.fetchrow("SELECT * FROM users WHERE id = $1 FOR UPDATE", user_id)
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
        if key == "skills" and isinstance(value, list):
            value = json.dumps(value)
        old_values[key] = old_val if not isinstance(old_val, (datetime,)) else str(old_val)
        new_values[key] = value
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

    # Cancel all active quests where user is assigned
    cancelled = await conn.execute(
        """
        UPDATE quests SET status = 'cancelled', updated_at = $1
        WHERE assigned_to = $2 AND status IN ('open', 'in_progress')
        """,
        now, user_id,
    )
    cancelled_count = int(cancelled.split()[-1]) if cancelled else 0

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

    # Cancel active quests
    await conn.execute(
        "UPDATE quests SET status = 'cancelled', updated_at = NOW() WHERE assigned_to = $1 AND status IN ('open', 'in_progress')",
        user_id,
    )
    await conn.execute(
        "UPDATE quests SET status = 'cancelled', updated_at = NOW() WHERE client_id = $1 AND status IN ('open', 'in_progress')",
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
    level_up, new_grade_enum, new_level = check_level_up(new_xp, grade_enum)
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
            stats_int = stats_int + $5, stats_dex = stats_dex + $6, stats_cha = stats_cha + $7,
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
    amount: float,
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

    row = await conn.fetchrow("SELECT id, username FROM users WHERE id = $1", user_id)
    if not row:
        raise ValueError(f"User {user_id} not found")

    old_balance = await wallet_service.get_balance(conn, user_id, currency)

    if amount > 0:
        new_balance = await wallet_service.credit(
            conn, user_id=user_id, amount=amount, currency=currency, tx_type="income",
        )
    elif amount < 0:
        new_balance = await wallet_service.debit(
            conn, user_id=user_id, amount=abs(amount), currency=currency, tx_type="expense",
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

    old_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id)
    if not old_row:
        raise ValueError(f"Quest {quest_id} not found")

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
    now = datetime.now(timezone.utc)

    await conn.execute(
        "UPDATE quests SET status = 'cancelled', updated_at = $1 WHERE id = $2",
        now, quest_id,
    )

    await log_admin_action(
        conn, admin_id=admin_id, action="quest_force_cancelled",
        target_type="quest", target_id=quest_id,
        old_value={"status": old_status},
        new_value={"status": "cancelled", "reason": reason},
        ip_address=ip_address,
    )

    # Notify client
    await notification_service.create_notification(
        conn, user_id=row["client_id"],
        title="Квест отменён администратором",
        message=f"Квест «{row['title']}» был принудительно отменён. Причина: {reason}",
        event_type="admin_quest_cancelled",
    )

    # Notify freelancer if assigned
    if row["assigned_to"]:
        await notification_service.create_notification(
            conn, user_id=row["assigned_to"],
            title="Квест отменён администратором",
            message=f"Квест «{row['title']}» был принудительно отменён. Причина: {reason}",
            event_type="admin_quest_cancelled",
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
) -> dict:
    """Force-complete a quest (set status to 'confirmed'). Does NOT trigger payment/XP — that's admin's choice via separate endpoints."""
    _assert_in_transaction(conn)

    row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id)
    if not row:
        raise ValueError(f"Quest {quest_id} not found")
    if row["status"] in ("confirmed", "cancelled"):
        raise ValueError(f"Quest {quest_id} is already {row['status']}")

    old_status = row["status"]
    now = datetime.now(timezone.utc)

    await conn.execute(
        "UPDATE quests SET status = 'confirmed', completed_at = $1, updated_at = $1 WHERE id = $2",
        now, quest_id,
    )

    await log_admin_action(
        conn, admin_id=admin_id, action="quest_force_completed",
        target_type="quest", target_id=quest_id,
        old_value={"status": old_status},
        new_value={"status": "confirmed", "reason": reason},
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
) -> dict:
    """Send a notification to multiple users."""
    _assert_in_transaction(conn)

    sent = 0
    for uid in user_ids:
        exists = await conn.fetchval("SELECT id FROM users WHERE id = $1", uid)
        if exists:
            await notification_service.create_notification(
                conn, user_id=uid, title=title, message=message, event_type=event_type,
            )
            sent += 1

    await log_admin_action(
        conn, admin_id=admin_id, action="notification_broadcast",
        target_type="system", target_id="broadcast",
        old_value=None,
        new_value={"recipients": len(user_ids), "sent": sent, "title": title},
        ip_address=ip_address,
    )

    return {"total_recipients": len(user_ids), "sent": sent, "title": title}


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
        "total_revenue": float(total_revenue),
        "users_today": users_today,
        "quests_today": quests_today,
    }
