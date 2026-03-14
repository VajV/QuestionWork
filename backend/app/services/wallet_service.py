"""
Wallet service — balance management with transactional integrity.

Implements credit/debit with pessimistic locking (SELECT FOR UPDATE)
and records every mutation as a transaction ledger entry.
"""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)

MONEY_QUANT = Decimal("0.01")


def _to_decimal(value) -> Decimal:
    """Safely convert a value to Decimal without float precision loss."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_money(value) -> Decimal:
    """Normalize money amounts to 2 decimal places using ROUND_HALF_UP."""
    return _to_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _assert_in_transaction(conn: asyncpg.Connection) -> None:
    """Raise if the connection is not inside an explicit transaction.

    This prevents credit/debit from silently running without atomicity
    guarantees when called outside an `async with conn.transaction():`.
    """
    if not conn.is_in_transaction():
        raise RuntimeError(
            "credit/debit must be called inside an explicit DB transaction. "
            "Wrap the call in `async with conn.transaction():`."
        )


class InsufficientFundsError(Exception):
    """Balance would go below zero."""
    pass


class ConcurrentModificationError(Exception):
    """Optimistic lock conflict detected."""
    pass


class WithdrawalValidationError(Exception):
    """Withdrawal request failed business-rule validation."""
    pass


class EscrowMismatchError(ValueError):
    """Held escrow amount does not match the payout amount being settled."""
    pass


# ────────────────────────────────────────────
# Read operations
# ────────────────────────────────────────────

async def get_balance(
    conn: asyncpg.Connection,
    user_id: str,
    currency: str = "RUB",
) -> Decimal:
    """Return the current balance for a user+currency without mutating state."""
    row = await conn.fetchrow(
        "SELECT balance FROM wallets WHERE user_id = $1 AND currency = $2",
        user_id,
        currency,
    )
    if row:
        return _to_decimal(row["balance"])
    return Decimal("0")


async def get_all_balances(
    conn: asyncpg.Connection,
    user_id: str,
) -> list[dict]:
    """Return all wallets for a user."""
    rows = await conn.fetch(
        "SELECT currency, balance, version, updated_at FROM wallets WHERE user_id = $1 ORDER BY currency",
        user_id,
    )
    return [
        {
            "currency": r["currency"],
            "balance": _to_decimal(r["balance"]),
            "version": r["version"],
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]


async def get_total_earned(
    conn: asyncpg.Connection,
    user_id: str,
) -> Decimal:
    """Sum of all completed incoming transactions (income + commission)."""
    row = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = $1
          AND type IN ('income', 'commission')
          AND status = 'completed'
        """,
        user_id,
    )
    return _to_decimal(row["total"] if row else 0)


async def get_transaction_history(
    conn: asyncpg.Connection,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return recent transactions for a user."""
    rows = await conn.fetch(
        """
        SELECT id, quest_id, amount, currency, type, status, created_at
        FROM transactions
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        user_id,
        limit,
        offset,
    )
    return [
        {
            "id": r["id"],
            "quest_id": r["quest_id"],
            "amount": _to_decimal(r["amount"]),
            "currency": r["currency"],
            "type": r["type"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


# ────────────────────────────────────────────
# Write operations (require transaction context)
# ────────────────────────────────────────────

async def credit(
    conn: asyncpg.Connection,
    user_id: str,
    amount,
    currency: str = "RUB",
    quest_id: Optional[str] = None,
    tx_type: str = "income",
):
    """
    Add funds to a wallet inside an **existing** DB transaction.

    Uses SELECT FOR UPDATE (pessimistic lock) to prevent race conditions.
    Returns the new balance.
    """
    _assert_in_transaction(conn)

    amount = quantize_money(amount)
    if amount <= 0:
        raise ValueError("Credit amount must be positive after rounding")
    now = datetime.now(timezone.utc)

    # Lock the wallet row
    wallet = await conn.fetchrow(
        "SELECT id, balance FROM wallets WHERE user_id = $1 AND currency = $2 FOR UPDATE",
        user_id,
        currency,
    )

    if wallet:
        new_balance = quantize_money(_to_decimal(wallet["balance"]) + amount)
        await conn.execute(
            "UPDATE wallets SET balance = $1, version = version + 1, updated_at = $2 WHERE id = $3",
            new_balance,
            now,
            wallet["id"],
        )
    else:
        # P0-3 FIX: ON CONFLICT handles race when two concurrent credits
        # both see wallet=None and both try to INSERT.
        result = await conn.fetchrow(
            """
            INSERT INTO wallets (id, user_id, currency, balance, version, created_at, updated_at)
            VALUES ($1, $2, $3, $4, 1, $5, $5)
            ON CONFLICT (user_id, currency) DO UPDATE
                SET balance = wallets.balance + EXCLUDED.balance,
                    version = wallets.version + 1,
                    updated_at = EXCLUDED.updated_at
            RETURNING balance
            """,
            f"wallet_{uuid.uuid4().hex[:12]}",
            user_id,
            currency,
            amount,
            now,
        )
        new_balance = quantize_money(result["balance"])

    # Ledger entry
    await conn.execute(
        """
        INSERT INTO transactions (id, user_id, quest_id, amount, currency, type, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        str(uuid.uuid4()),
        user_id,
        quest_id,
        amount,
        currency,
        tx_type,
        "completed",
        now,
    )

    logger.info(f"Credit {amount} {currency} to user {user_id}. New balance: {new_balance}")
    return new_balance


async def debit(
    conn: asyncpg.Connection,
    user_id: str,
    amount,
    currency: str = "RUB",
    quest_id: Optional[str] = None,
    tx_type: str = "expense",
):
    """
    Withdraw funds from a wallet inside an **existing** DB transaction.

    Uses SELECT FOR UPDATE. Raises InsufficientFundsError if balance is too low.
    Returns the new balance.
    """
    _assert_in_transaction(conn)

    amount = quantize_money(amount)
    if amount <= 0:
        raise ValueError("Debit amount must be positive after rounding")
    now = datetime.now(timezone.utc)

    wallet = await conn.fetchrow(
        "SELECT id, balance FROM wallets WHERE user_id = $1 AND currency = $2 FOR UPDATE",
        user_id,
        currency,
    )

    if not wallet:
        raise InsufficientFundsError("Insufficient funds")

    current_balance = _to_decimal(wallet["balance"])
    if current_balance < amount:
        raise InsufficientFundsError("Insufficient funds")

    new_balance = quantize_money(current_balance - amount)
    await conn.execute(
        "UPDATE wallets SET balance = $1, version = version + 1, updated_at = $2 WHERE id = $3",
        new_balance,
        now,
        wallet["id"],
    )

    # Ledger entry
    await conn.execute(
        """
        INSERT INTO transactions (id, user_id, quest_id, amount, currency, type, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        str(uuid.uuid4()),
        user_id,
        quest_id,
        amount,
        currency,
        tx_type,
        "completed",
        now,
    )

    logger.info(f"Debit {amount} {currency} from user {user_id}. New balance: {new_balance}")
    return new_balance


# ────────────────────────────────────────────
# Escrow (hold / release / refund)
# ────────────────────────────────────────────

async def hold(
    conn: asyncpg.Connection,
    user_id: str,
    amount,
    currency: str = "RUB",
    quest_id: Optional[str] = None,
) -> Decimal:
    """Place a hold (escrow) on user funds. Deducts from balance immediately.

    Creates a transaction with type='hold' and status='held'.
    Returns the new balance.
    """
    _assert_in_transaction(conn)

    amount = quantize_money(amount)
    if amount <= 0:
        raise ValueError("Hold amount must be positive after rounding")
    now = datetime.now(timezone.utc)

    wallet = await conn.fetchrow(
        "SELECT id, balance FROM wallets WHERE user_id = $1 AND currency = $2 FOR UPDATE",
        user_id,
        currency,
    )
    if not wallet:
        raise InsufficientFundsError("Insufficient funds")

    current_balance = _to_decimal(wallet["balance"])
    if current_balance < amount:
        raise InsufficientFundsError("Insufficient funds")

    new_balance = quantize_money(current_balance - amount)
    await conn.execute(
        "UPDATE wallets SET balance = $1, version = version + 1, updated_at = $2 WHERE id = $3",
        new_balance,
        now,
        wallet["id"],
    )

    # Ledger entry with status='held' so we can find and release it later
    await conn.execute(
        """
        INSERT INTO transactions (id, user_id, quest_id, amount, currency, type, status, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        str(uuid.uuid4()),
        user_id,
        quest_id,
        amount,
        currency,
        "hold",
        "held",
        now,
    )

    logger.info(f"Hold {amount} {currency} for user {user_id} quest {quest_id}. New balance: {new_balance}")
    return new_balance


async def release_hold(
    conn: asyncpg.Connection,
    user_id: str,
    quest_id: str,
    currency: str = "RUB",
) -> Decimal:
    """Release a held escrow — mark the hold transaction as 'completed'.

    Does NOT credit back to the user: the funds are consumed (paid out).
    Returns the hold amount that was released.
    """
    _assert_in_transaction(conn)

    tx = await conn.fetchrow(
        """
        SELECT id, amount FROM transactions
        WHERE user_id = $1 AND quest_id = $2 AND type = 'hold' AND status = 'held' AND currency = $3
        FOR UPDATE
        """,
        user_id,
        quest_id,
        currency,
    )
    if not tx:
        raise ValueError(f"No active hold found for user {user_id} quest {quest_id}")

    await conn.execute(
        "UPDATE transactions SET status = 'completed' WHERE id = $1",
        tx["id"],
    )

    logger.info(f"Released hold {tx['amount']} {currency} for user {user_id} quest {quest_id}")
    return _to_decimal(tx["amount"])


async def refund_hold(
    conn: asyncpg.Connection,
    user_id: str,
    quest_id: str,
    currency: str = "RUB",
) -> Optional[Decimal]:
    """Refund a held escrow — credit funds back to user and mark hold as 'refunded'.

    Returns the new balance, or None if no active hold exists.
    """
    _assert_in_transaction(conn)

    tx = await conn.fetchrow(
        """
        SELECT id, amount FROM transactions
        WHERE user_id = $1 AND quest_id = $2 AND type = 'hold' AND status = 'held' AND currency = $3
        FOR UPDATE
        """,
        user_id,
        quest_id,
        currency,
    )
    if not tx:
        return None

    await conn.execute(
        "UPDATE transactions SET status = 'refunded' WHERE id = $1",
        tx["id"],
    )

    # Credit the held amount back
    new_balance = await credit(
        conn,
        user_id=user_id,
        amount=tx["amount"],
        currency=currency,
        quest_id=quest_id,
        tx_type="refund",
    )

    logger.info(f"Refunded hold {tx['amount']} {currency} to user {user_id} quest {quest_id}. New balance: {new_balance}")
    return new_balance


# ────────────────────────────────────────────
# Commission split — called inside a transaction
# ────────────────────────────────────────────

async def split_payment(
    conn: asyncpg.Connection,
    *,
    client_id: str,
    freelancer_id: str,
    gross_amount,
    currency: str = "RUB",
    quest_id: Optional[str] = None,
    fee_percent=None,
) -> dict:
    """Split a quest payment: freelancer gets (100 - fee)%, platform gets fee%.

    Must be called inside an existing DB transaction (asserted inside
    ``credit`` calls).

    When a hold (escrow) exists for the quest, the held funds are released
    instead of debiting the client again. If no hold exists, falls back to
    a direct debit.

    Args:
        conn: asyncpg connection already in a transaction.
        client_id: Payer (client who posted the quest).
        freelancer_id: Recipient freelancer.
        gross_amount: Full quest budget.
        currency: ISO currency code.
        quest_id: Associated quest for ledger reference.
        fee_percent: Platform fee %. Defaults to ``settings.PLATFORM_FEE_PERCENT``.

    Returns:
        Dict with keys ``freelancer_amount``, ``platform_fee``, new
        ``freelancer_balance``, and ``platform_balance``.
    """
    _assert_in_transaction(conn)

    gross_amount = quantize_money(gross_amount)

    if fee_percent is None:
        fee_percent = settings.PLATFORM_FEE_PERCENT

    fee_pct = _to_decimal(fee_percent)
    _MAX_FEE_PERCENT = Decimal("30")
    if not (Decimal("0") <= fee_pct <= _MAX_FEE_PERCENT):
        raise ValueError(f"fee_percent must be in [0, {_MAX_FEE_PERCENT}], got {fee_percent}")

    # Guard: platform user must exist to receive commission
    if fee_pct > 0:
        platform_exists = await conn.fetchval(
            "SELECT 1 FROM users WHERE id = $1", settings.PLATFORM_USER_ID
        )
        if not platform_exists:
            raise ValueError(
                f"Platform user '{settings.PLATFORM_USER_ID}' does not exist. "
                "Cannot process commission. Aborting payment."
            )

    # Use Decimal for precise financial math
    platform_fee = quantize_money(gross_amount * fee_pct / Decimal("100"))
    freelancer_amount = gross_amount - platform_fee  # NOT re-quantized — preserves fee + payout == gross invariant

    # Try to release an existing escrow hold first;
    # fall back to a fresh debit if no hold exists.
    hold_tx = await conn.fetchrow(
        """
        SELECT id, amount FROM transactions
        WHERE user_id = $1 AND quest_id = $2 AND type = 'hold' AND status = 'held' AND currency = $3
        FOR UPDATE
        """,
        client_id,
        quest_id,
        currency,
    )
    if hold_tx:
        held_amount = quantize_money(hold_tx["amount"])
        if held_amount != gross_amount:
            raise EscrowMismatchError("Escrow hold amount does not match payout amount")
        await release_hold(conn, client_id, quest_id, currency)
        # Hold already deducted the gross from client balance; read current balance
        wallet_row = await conn.fetchrow(
            "SELECT balance FROM wallets WHERE user_id = $1 AND currency = $2",
            client_id, currency,
        )
        client_balance = _to_decimal(wallet_row["balance"]) if wallet_row else Decimal("0")
    else:
        # No escrow — direct debit (legacy / admin force-complete path)
        client_balance = await debit(
            conn,
            user_id=client_id,
            amount=gross_amount,
            currency=currency,
            quest_id=quest_id,
            tx_type="expense",
        )

    # Credit freelancer
    freelancer_balance = await credit(
        conn,
        user_id=freelancer_id,
        amount=freelancer_amount,
        currency=currency,
        quest_id=quest_id,
        tx_type="income",
    )

    # Credit platform wallet (only if fee > 0)
    platform_balance: Optional[Decimal] = None
    if platform_fee > 0:
        platform_balance = await credit(
            conn,
            user_id=settings.PLATFORM_USER_ID,
            amount=platform_fee,
            currency=currency,
            quest_id=quest_id,
            tx_type="commission",
        )

    logger.info(
        f"split_payment quest={quest_id}: gross={gross_amount} {currency}, "
        f"freelancer={freelancer_id} +{freelancer_amount}, "
        f"platform +{platform_fee} (fee {fee_percent}%)"
    )

    return {
        "gross_amount": gross_amount,
        "fee_percent": fee_percent,
        "freelancer_amount": freelancer_amount,
        "platform_fee": platform_fee,
        "client_balance": client_balance,
        "freelancer_balance": freelancer_balance,
        "platform_balance": platform_balance,
    }


# ────────────────────────────────────────────
# Withdrawal — creates a pending transaction
# ────────────────────────────────────────────

async def create_withdrawal(
    conn: asyncpg.Connection,
    user_id: str,
    amount,
    currency: str = "RUB",
    idempotency_key: Optional[str] = None,
) -> dict:
    """Request a withdrawal. Deducts from balance immediately with status=pending.

    Must be called inside an existing DB transaction.

    If idempotency_key is provided and a pending withdrawal with this key already
    exists for the user, returns the existing record without creating a duplicate.

    Raises:
        WithdrawalValidationError: If amount < MIN_WITHDRAWAL_AMOUNT.
        InsufficientFundsError: If balance is too low.
    """
    _assert_in_transaction(conn)

    amount = quantize_money(amount)

    if amount < quantize_money(settings.MIN_WITHDRAWAL_AMOUNT):
        raise WithdrawalValidationError(
            f"Minimum withdrawal is {settings.MIN_WITHDRAWAL_AMOUNT} {currency}, "
            f"requested {amount}"
        )

    now = datetime.now(timezone.utc)

    # Lock the wallet FIRST — serializes all concurrent withdrawals for this user
    wallet = await conn.fetchrow(
        "SELECT id, balance FROM wallets WHERE user_id = $1 AND currency = $2 FOR UPDATE",
        user_id,
        currency,
    )
    if not wallet:
        raise InsufficientFundsError(f"No wallet found for user {user_id} / {currency}")

    # --- Idempotency check (AFTER wallet lock to prevent TOCTOU race) ---
    if idempotency_key:
        existing = await conn.fetchrow(
            """SELECT id, amount, currency, status
               FROM transactions
               WHERE user_id = $1 AND idempotency_key = $2 AND type = 'withdrawal'""",
            user_id,
            idempotency_key,
        )
        if existing:
            if existing["status"] != "pending":
                raise ValueError(
                    f"Withdrawal with this idempotency key already {existing['status']}. "
                    "Use a new idempotency_key to create a fresh request."
                )
            return {
                "transaction_id": existing["id"],
                "amount": _to_decimal(existing["amount"]),
                "currency": existing["currency"],
                "status": existing["status"],
                "new_balance": await get_balance(conn, user_id, currency),
                "idempotent": True,
            }
    # --- end idempotency check ---

    current_balance = _to_decimal(wallet["balance"])
    if current_balance < amount:
        raise InsufficientFundsError(
            f"Insufficient funds: {current_balance} < {amount} {currency}"
        )

    new_balance = quantize_money(current_balance - amount)
    await conn.execute(
        "UPDATE wallets SET balance = $1, version = version + 1, updated_at = $2 WHERE id = $3",
        new_balance,
        now,
        wallet["id"],
    )

    tx_id = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO transactions (id, user_id, quest_id, amount, currency, type, status, idempotency_key, created_at)
        VALUES ($1, $2, NULL, $3, $4, $5, $6, $7, $8)
        """,
        tx_id,
        user_id,
        amount,
        currency,
        "withdrawal",
        "pending",
        idempotency_key,
        now,
    )

    logger.info(
        f"Withdrawal requested: user={user_id}, amount={amount} {currency}, "
        f"tx={tx_id}, new_balance={new_balance}"
    )

    return {
        "transaction_id": tx_id,
        "amount": amount,
        "currency": currency,
        "status": "pending",
        "new_balance": new_balance,
    }
