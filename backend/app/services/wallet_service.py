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


def _to_decimal(value) -> Decimal:
    """Safely convert a value to Decimal without float precision loss."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


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


# ────────────────────────────────────────────
# Read operations
# ────────────────────────────────────────────

async def get_balance(
    conn: asyncpg.Connection,
    user_id: str,
    currency: str = "RUB",
) -> float:
    """Return the current balance for a user+currency. Creates wallet if absent."""
    row = await conn.fetchrow(
        "SELECT balance FROM wallets WHERE user_id = $1 AND currency = $2",
        user_id,
        currency,
    )
    if row:
        return _to_decimal(row["balance"])
    # Auto-create with zero balance
    await conn.execute(
        """
        INSERT INTO wallets (id, user_id, currency, balance, version, created_at, updated_at)
        VALUES ($1, $2, $3, 0, 1, $4, $4)
        ON CONFLICT (user_id, currency) DO NOTHING
        """,
        f"wallet_{uuid.uuid4().hex[:12]}",
        user_id,
        currency,
        datetime.now(timezone.utc),
    )
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


async def get_transaction_history(
    conn: asyncpg.Connection,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return recent transactions for a user."""
    rows = await conn.fetch(
        """
        SELECT id, quest_id, amount, currency, type, created_at
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
    amount: float,
    currency: str = "RUB",
    quest_id: Optional[str] = None,
    tx_type: str = "income",
) -> float:
    """
    Add funds to a wallet inside an **existing** DB transaction.

    Uses SELECT FOR UPDATE (pessimistic lock) to prevent race conditions.
    Returns the new balance.
    """
    if amount <= 0:
        raise ValueError("Credit amount must be positive")

    _assert_in_transaction(conn)

    amount = _to_decimal(amount)
    now = datetime.now(timezone.utc)

    # Lock the wallet row
    wallet = await conn.fetchrow(
        "SELECT id, balance FROM wallets WHERE user_id = $1 AND currency = $2 FOR UPDATE",
        user_id,
        currency,
    )

    if wallet:
        new_balance = _to_decimal(wallet["balance"]) + amount
        await conn.execute(
            "UPDATE wallets SET balance = $1, version = version + 1, updated_at = $2 WHERE id = $3",
            new_balance,
            now,
            wallet["id"],
        )
    else:
        new_balance = amount
        await conn.execute(
            """
            INSERT INTO wallets (id, user_id, currency, balance, version, created_at, updated_at)
            VALUES ($1, $2, $3, $4, 1, $5, $5)
            """,
            f"wallet_{uuid.uuid4().hex[:12]}",
            user_id,
            currency,
            amount,
            now,
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

    logger.info(f"Credit {amount} {currency} to user {user_id}. New balance: {new_balance}")
    return new_balance


async def debit(
    conn: asyncpg.Connection,
    user_id: str,
    amount: float,
    currency: str = "RUB",
    quest_id: Optional[str] = None,
    tx_type: str = "expense",
) -> float:
    """
    Withdraw funds from a wallet inside an **existing** DB transaction.

    Uses SELECT FOR UPDATE. Raises InsufficientFundsError if balance is too low.
    Returns the new balance.
    """
    if amount <= 0:
        raise ValueError("Debit amount must be positive")

    _assert_in_transaction(conn)

    amount = _to_decimal(amount)
    now = datetime.now(timezone.utc)

    wallet = await conn.fetchrow(
        "SELECT id, balance FROM wallets WHERE user_id = $1 AND currency = $2 FOR UPDATE",
        user_id,
        currency,
    )

    if not wallet:
        raise InsufficientFundsError(f"No wallet found for user {user_id} / {currency}")

    current_balance = _to_decimal(wallet["balance"])
    if current_balance < amount:
        raise InsufficientFundsError(
            f"Insufficient funds: {current_balance} < {amount} {currency}"
        )

    new_balance = current_balance - amount
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
# Commission split — called inside a transaction
# ────────────────────────────────────────────

async def split_payment(
    conn: asyncpg.Connection,
    *,
    client_id: str,
    freelancer_id: str,
    gross_amount: float,
    currency: str = "RUB",
    quest_id: Optional[str] = None,
    fee_percent: Optional[float] = None,
) -> dict:
    """Split a quest payment: freelancer gets (100 - fee)%, platform gets fee%.

    Must be called inside an existing DB transaction (asserted inside
    ``credit`` calls).

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

    gross_amount = _to_decimal(gross_amount)

    if fee_percent is None:
        fee_percent = settings.PLATFORM_FEE_PERCENT

    fee_pct = _to_decimal(fee_percent)
    if not (Decimal("0") <= fee_pct < Decimal("100")):
        raise ValueError(f"fee_percent must be in [0, 100), got {fee_percent}")

    # Use Decimal for precise financial math
    platform_fee = (gross_amount * fee_pct / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    freelancer_amount = gross_amount - platform_fee

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
        "freelancer_balance": freelancer_balance,
        "platform_balance": platform_balance,
    }


# ────────────────────────────────────────────
# Withdrawal — creates a pending transaction
# ────────────────────────────────────────────

async def create_withdrawal(
    conn: asyncpg.Connection,
    user_id: str,
    amount: float,
    currency: str = "RUB",
) -> dict:
    """Request a withdrawal. Deducts from balance immediately with status=pending.

    Must be called inside an existing DB transaction.

    Raises:
        WithdrawalValidationError: If amount < MIN_WITHDRAWAL_AMOUNT.
        InsufficientFundsError: If balance is too low.
    """
    _assert_in_transaction(conn)

    if amount < settings.MIN_WITHDRAWAL_AMOUNT:
        raise WithdrawalValidationError(
            f"Minimum withdrawal is {settings.MIN_WITHDRAWAL_AMOUNT} {currency}, "
            f"requested {amount}"
        )

    now = datetime.now(timezone.utc)

    # Lock the wallet
    wallet = await conn.fetchrow(
        "SELECT id, balance FROM wallets WHERE user_id = $1 AND currency = $2 FOR UPDATE",
        user_id,
        currency,
    )
    if not wallet:
        raise InsufficientFundsError(f"No wallet found for user {user_id} / {currency}")

    current_balance = _to_decimal(wallet["balance"])
    if current_balance < amount:
        raise InsufficientFundsError(
            f"Insufficient funds: {current_balance} < {amount} {currency}"
        )

    new_balance = (current_balance - _to_decimal(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    await conn.execute(
        "UPDATE wallets SET balance = $1, version = version + 1, updated_at = $2 WHERE id = $3",
        new_balance,
        now,
        wallet["id"],
    )

    tx_id = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO transactions (id, user_id, quest_id, amount, currency, type, status, created_at)
        VALUES ($1, $2, NULL, $3, $4, $5, $6, $7)
        """,
        tx_id,
        user_id,
        amount,
        currency,
        "withdrawal",
        "pending",
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
