"""
Wallet endpoints — balance & transaction history.

Wallet mutations (credit/debit) happen only as side-effects of quest
completion via quest_service.  These endpoints are read-only for the
authenticated user, except POST /withdraw.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, check_user_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.quest import CurrencyEnum
from app.models.user import UserProfile
from app.services import invoice_service, wallet_service
from app.services.wallet_service import InsufficientFundsError, WithdrawalValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wallet", tags=["Wallet"])


class WithdrawRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, le=10_000_000, description="Amount to withdraw (must be > 0)")
    currency: CurrencyEnum = CurrencyEnum.RUB
    idempotency_key: Optional[str] = Field(
        default=None,
        min_length=4,
        max_length=64,
        description="Client-generated UUID to prevent duplicate withdrawals on retry",
    )


@router.get("/balance")
async def get_balance(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return all wallet balances for the authenticated user."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="wallet_balance", limit=30, window_seconds=60)
    balances = await wallet_service.get_all_balances(conn, current_user.id)
    total_earned = await wallet_service.get_total_earned(conn, current_user.id)
    return {
        "user_id": current_user.id,
        "balances": balances,
        "total_earned": total_earned,
    }


@router.get("/transactions")
async def get_transactions(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return paginated transaction history for the authenticated user."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="wallet_transactions", limit=30, window_seconds=60)
    transactions = await wallet_service.get_transaction_history(
        conn, current_user.id, limit=limit, offset=offset
    )
    return {
        "user_id": current_user.id,
        "transactions": transactions,
        "limit": limit,
        "offset": offset,
    }


@router.get("/transactions/{transaction_id}/receipt")
async def download_transaction_receipt(
    request: Request,
    transaction_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return a PDF receipt for a single wallet transaction."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="wallet_receipt", limit=20, window_seconds=60)
    try:
        receipt_data = await invoice_service.get_wallet_receipt_data(conn, current_user.id, transaction_id)
    except invoice_service.DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    pdf_bytes = invoice_service.generate_receipt_pdf(receipt_data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="receipt-{transaction_id}.pdf"',
        },
    )


@router.get("/statements")
async def download_wallet_statement(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    format: Literal["pdf", "csv"] = Query(default="pdf"),
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return a wallet statement for a date range in PDF or CSV format."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="wallet_statement", limit=20, window_seconds=60)
    try:
        statement_data = await invoice_service.get_wallet_statement_data(conn, current_user.id, date_from, date_to)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if format == "csv":
        content = invoice_service.generate_statement_csv(statement_data)
        media_type = "text/csv"
        filename = f"wallet-statement-{date_from.isoformat()}-{date_to.isoformat()}.csv"
    else:
        content = invoice_service.generate_statement_pdf(statement_data)
        media_type = "application/pdf"
        filename = f"wallet-statement-{date_from.isoformat()}-{date_to.isoformat()}.pdf"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/withdraw", status_code=status.HTTP_201_CREATED)
async def withdraw(
    request: Request,
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
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="wallet_withdraw", limit=10, window_seconds=60)
    await check_user_rate_limit(current_user.id, action="wallet_withdraw", limit=10, window_seconds=60)
    try:
        async with conn.transaction():
            result = await wallet_service.create_withdrawal(
                conn,
                user_id=current_user.id,
                amount=body.amount,
                currency=body.currency,
                idempotency_key=body.idempotency_key,
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
