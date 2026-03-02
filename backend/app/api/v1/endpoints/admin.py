"""
Admin HTTP endpoints — protected by require_admin dependency.

All mutating endpoints:
  - Operate inside a DB transaction.
  - Write an audit record to admin_logs.
  - Send a notification to the affected user.
  - Rate-limited at 120 requests / 60 seconds per IP.

Routes:
  GET  /admin/users                          — list users (paginated)
  GET  /admin/transactions                   — list transactions (filtered)
  GET  /admin/withdrawals/pending            — pending withdrawal queue
  PATCH /admin/withdrawals/{id}/approve      — approve a pending withdrawal
  PATCH /admin/withdrawals/{id}/reject       — reject + refund a withdrawal
  GET  /admin/logs                           — audit log history
  POST /admin/maintenance/cleanup-notifications — prune old read notifications
"""

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.deps import require_admin, require_admin_role_only
from app.core.ratelimit import check_rate_limit
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.services import admin_service, notification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ─────────────────────────────────────────────────────────────────────
# Rate-limit helper (applied to every admin route)
# ─────────────────────────────────────────────────────────────────────

def _admin_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    check_rate_limit(ip, action="admin", limit=120, window_seconds=60)


# ─────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────

@router.get("/users", summary="List all users (admin)")
async def admin_list_users(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    role: Optional[str] = Query(default=None),
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    _admin_rate_limit(request)
    return await admin_service.list_users(conn, page=page, page_size=page_size, role_filter=role)


# ─────────────────────────────────────────────────────────────────────
# Transactions
# ─────────────────────────────────────────────────────────────────────

@router.get("/transactions", summary="List transactions (admin)")
async def admin_list_transactions(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    type_filter: Optional[str] = Query(default=None, alias="type"),
    user_id: Optional[str] = Query(default=None),
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    _admin_rate_limit(request)
    return await admin_service.list_transactions(
        conn,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        type_filter=type_filter,
        user_id_filter=user_id,
    )


@router.get("/withdrawals/pending", summary="List pending withdrawals (admin)")
async def admin_pending_withdrawals(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    _admin_rate_limit(request)
    return await admin_service.list_pending_withdrawals(conn, page=page, page_size=page_size)


# ─────────────────────────────────────────────────────────────────────
# Withdrawal approve / reject
# ─────────────────────────────────────────────────────────────────────

@router.patch("/withdrawals/{transaction_id}/approve", summary="Approve a pending withdrawal")
async def admin_approve_withdrawal(
    transaction_id: str,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    _admin_rate_limit(request)
    ip = request.client.host if request.client else None

    try:
        async with conn.transaction():
            result = await admin_service.approve_withdrawal(
                conn,
                transaction_id=transaction_id,
                admin_id=current_admin.id,
                ip_address=ip,
            )
            # Notify the user
            await notification_service.create_notification(
                conn,
                user_id=result["user_id"],
                title="Withdrawal Approved",
                message=(
                    f"Your withdrawal of {result['amount']} {result['currency']} "
                    "has been approved and is being processed."
                ),
                event_type="withdrawal_approved",
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return result


class RejectWithdrawalRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for rejection")


@router.patch("/withdrawals/{transaction_id}/reject", summary="Reject a pending withdrawal")
async def admin_reject_withdrawal(
    transaction_id: str,
    body: RejectWithdrawalRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    _admin_rate_limit(request)
    ip = request.client.host if request.client else None

    try:
        async with conn.transaction():
            result = await admin_service.reject_withdrawal(
                conn,
                transaction_id=transaction_id,
                admin_id=current_admin.id,
                reason=body.reason,
                ip_address=ip,
            )
            # Notify the user
            await notification_service.create_notification(
                conn,
                user_id=result["user_id"],
                title="Withdrawal Rejected",
                message=(
                    f"Your withdrawal of {result['amount']} {result['currency']} "
                    f"was rejected: {body.reason}. "
                    f"The amount has been returned to your wallet."
                ),
                event_type="withdrawal_rejected",
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return result


# ─────────────────────────────────────────────────────────────────────
# Audit log
# ─────────────────────────────────────────────────────────────────────

@router.get("/logs", summary="Admin audit log")
async def admin_get_logs(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    admin_id: Optional[str] = Query(default=None),
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    _admin_rate_limit(request)
    return await admin_service.get_admin_logs(
        conn, page=page, page_size=page_size, admin_id_filter=admin_id
    )


# ─────────────────────────────────────────────────────────────────────
# Admin 2FA — TOTP setup / verify / disable
# These use require_admin_role_only so they work BEFORE full TOTP gate.
# ─────────────────────────────────────────────────────────────────────

class VerifyTotpRequest(BaseModel):
    token: str = Field(..., min_length=6, max_length=8, description="6- or 8-digit TOTP token")


@router.post(
    "/auth/totp/setup",
    summary="Generate and store a TOTP secret for the calling admin",
)
async def admin_totp_setup(
    request: Request,
    current_admin: UserProfile = Depends(require_admin_role_only),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """
    Generates a new TOTP secret for the calling admin user.

    Returns the raw secret and an ``otpauth://`` URI that can be rendered
    as a QR code by any authenticator app (Google Authenticator, Authy, etc.).

    Calling this endpoint multiple times is safe — it replaces the existing secret.
    The new secret is **not active** yet: confirm it with POST /admin/auth/totp/enable.
    """
    try:
        import pyotp
    except ImportError:
        raise HTTPException(status_code=500, detail="pyotp package not installed")

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(
        name=current_admin.username,
        issuer_name="QuestionWork Admin",
    )

    await conn.execute(
        "UPDATE users SET totp_secret = $1 WHERE id = $2",
        secret,
        current_admin.id,
    )
    logger.info(f"Admin {current_admin.id} generated new TOTP secret")

    return {"secret": secret, "otpauth_uri": uri}


@router.post(
    "/auth/totp/enable",
    summary="Verify TOTP token to confirm setup is working",
)
async def admin_totp_enable(
    body: VerifyTotpRequest,
    current_admin: UserProfile = Depends(require_admin_role_only),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """
    Verifies that the caller's authenticator app produces correct tokens for
    the secret stored after /setup. Returns 200 if the token is valid.

    This is a smoke-test step before enabling ``ADMIN_TOTP_REQUIRED=True``.
    """
    try:
        import pyotp
    except ImportError:
        raise HTTPException(status_code=500, detail="pyotp package not installed")

    totp_secret = await conn.fetchval(
        "SELECT totp_secret FROM users WHERE id = $1", current_admin.id
    )
    if not totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP not set up. Call POST /admin/auth/totp/setup first.",
        )

    totp = pyotp.TOTP(totp_secret)
    if not totp.verify(body.token, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP token",
        )

    return {"ok": True, "message": "TOTP token is valid. You can now enable ADMIN_TOTP_REQUIRED=True."}


@router.delete(
    "/auth/totp",
    summary="Disable TOTP for the calling admin",
)
async def admin_totp_disable(
    current_admin: UserProfile = Depends(require_admin_role_only),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Clears the TOTP secret. If ADMIN_TOTP_REQUIRED is True this will lock out the admin."""
    await conn.execute(
        "UPDATE users SET totp_secret = NULL WHERE id = $1", current_admin.id
    )
    logger.warning(f"Admin {current_admin.id} disabled TOTP")
    return {"ok": True, "message": "TOTP disabled for this account."}


# ─────────────────────────────────────────────────────────────────────
# Maintenance
# ─────────────────────────────────────────────────────────────────────

@router.post(
    "/maintenance/cleanup-notifications",
    summary="Delete read notifications older than retention period",
)
async def admin_cleanup_notifications(
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    _admin_rate_limit(request)
    deleted = await admin_service.cleanup_old_notifications(conn)
    logger.info(
        f"Notification cleanup triggered by admin {current_admin.id}: {deleted} rows deleted"
    )
    return {
        "deleted": deleted,
        "message": f"Removed {deleted} old read notification(s).",
    }
