"""
AdminService — administrative operations with full audit trail.

All write operations:
  - Must be called inside an existing DB transaction.
  - Automatically write an entry to admin_logs.

Read operations are transaction-free and safe to call outside a transaction.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.core.config import settings
from app.services import wallet_service

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
        SELECT id, username, email, role, grade, level, xp, created_at
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
