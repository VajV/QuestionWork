"""
Wallet endpoints — balance & transaction history.

Wallet mutations (credit/debit) happen only as side-effects of quest
completion via quest_service.  These endpoints are read-only for the
authenticated user, except POST /withdraw.
"""

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import require_auth
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.services import wallet_service
from app.services.wallet_service import InsufficientFundsError, WithdrawalValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wallet", tags=["Wallet"])


class WithdrawRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount to withdraw (must be > 0)")
    currency: str = Field(default="RUB", max_length=10)


@router.get("/balance")
async def get_balance(
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return all wallet balances for the authenticated user."""
    balances = await wallet_service.get_all_balances(conn, current_user.id)
    return {"user_id": current_user.id, "balances": balances}


@router.get("/transactions")
async def get_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return paginated transaction history for the authenticated user."""
    transactions = await wallet_service.get_transaction_history(
        conn, current_user.id, limit=limit, offset=offset
    )
    return {
        "user_id": current_user.id,
        "transactions": transactions,
        "limit": limit,
        "offset": offset,
    }


@router.post("/withdraw", status_code=status.HTTP_201_CREATED)
async def withdraw(
    body: WithdrawRequest,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """
    Request a withdrawal.

    Deducts the amount from the wallet immediately and records a **pending**
    transaction in the ledger.  A background job (out of scope for MVP) is
    responsible for actually processing the payout and flipping the status to
    *completed* or *failed*.

    Raises 400 if the amount is below the platform minimum (configured via
    ``MIN_WITHDRAWAL_AMOUNT`` in settings).
    Raises 402 if the user has insufficient funds.
    """
    try:
        async with conn.transaction():
            result = await wallet_service.create_withdrawal(
                conn,
                user_id=current_user.id,
                amount=body.amount,
                currency=body.currency,
            )
    except WithdrawalValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InsufficientFundsError as e:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(e))

    logger.info(
        f"Withdrawal initiated: user={current_user.id}, "
        f"amount={body.amount} {body.currency}, tx={result['transaction_id']}"
    )
    return result
