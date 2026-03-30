"""
Admin HTTP endpoints — protected by require_admin dependency.

SECURITY NOTE: Two guard dependencies exist — choose carefully:
  - require_admin          → FULL guard: role check + IP allowlist + TOTP verification.
                             Use for ALL new admin endpoints without exception.
  - require_admin_role_only → Role-only (no IP/TOTP check).
                             ONLY for /totp/setup and /totp/enable (chicken-and-egg:
                             these endpoints configure TOTP, so TOTP can't be checked yet).
                             Never use require_admin_role_only for any other endpoint.

All mutating endpoints:
  - Operate inside a DB transaction.
  - Write an audit record to admin_logs.
  - Send a notification to the affected user.
  - Rate-limited at 120 requests / 60 seconds per IP.

Routes (existing):
  GET  /admin/users                          — list users (paginated)
  GET  /admin/transactions                   — list transactions (filtered)
  GET  /admin/withdrawals/pending            — pending withdrawal queue
  PATCH /admin/withdrawals/{id}/approve      — approve a pending withdrawal
  PATCH /admin/withdrawals/{id}/reject       — reject + refund a withdrawal
  GET  /admin/logs                           — audit log history
  POST /admin/maintenance/cleanup-notifications — prune old read notifications

Routes (God Mode):
  GET    /admin/stats                        — platform-wide statistics
  GET    /admin/users/{user_id}              — full user detail
  PATCH  /admin/users/{user_id}              — edit user fields
  POST   /admin/users/{user_id}/ban          — ban user
  POST   /admin/users/{user_id}/unban        — unban user
  DELETE /admin/users/{user_id}              — hard delete user
  POST   /admin/users/{user_id}/grant-xp     — grant/revoke XP
  POST   /admin/users/{user_id}/adjust-wallet — credit/debit wallet
  POST   /admin/users/{user_id}/grant-badge  — award badge
  DELETE /admin/users/{user_id}/badges/{badge_id} — revoke badge
  POST   /admin/users/{user_id}/change-class — force class change/reset
  GET    /admin/quests/{quest_id}            — full quest detail
  PATCH  /admin/quests/{quest_id}            — edit quest fields
  POST   /admin/quests/{quest_id}/force-cancel   — force cancel
  POST   /admin/quests/{quest_id}/force-complete — force complete
  DELETE /admin/quests/{quest_id}            — hard delete quest
  POST   /admin/notifications/broadcast      — send to multiple users
"""

import logging
from decimal import Decimal
from typing import Annotated, Literal, Optional, List

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, StringConstraints

from app.api.deps import require_admin, require_admin_role_only
from app.core.classes import ClassId
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.admin import (
    AdminGuildSeasonRewardConfigResponse,
    AdminLogsListResponse,
    AdminPlatformStatsResponse,
    AdminQuestDetailResponse,
    AdminTransactionsListResponse,
    AdminUserDetailResponse,
    AdminUsersListResponse,
)
from app.models.user import GradeEnum, UserProfile
from app.services import admin_service, notification_service
from app.services.wallet_service import EscrowMismatchError, InsufficientFundsError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

AdminSkill = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50, strict=True),
]

ESCROW_CONFLICT_DETAIL = "Quest payment state is inconsistent. Please contact support."


# ─────────────────────────────────────────────────────────────────────
# Rate-limit helper (applied to every admin route)
# ─────────────────────────────────────────────────────────────────────

async def _admin_rate_limit(request: Request) -> None:
    ip = get_client_ip(request)
    route = request.scope.get("route")
    route_path = getattr(route, "path", None) or request.url.path or "/admin"
    action = f"admin:{request.method.upper()}:{route_path}"
    await check_rate_limit(ip, action=action, limit=120, window_seconds=60)


# ─────────────────────────────────────────────────────────────────────
# Request models (God Mode)
# ─────────────────────────────────────────────────────────────────────

class AdminUpdateUserRequest(BaseModel):
    role: Optional[Literal["client", "freelancer"]] = None
    level: Optional[int] = Field(None, ge=1, le=100)
    grade: Optional[GradeEnum] = None
    xp: Optional[int] = Field(None, ge=0)
    xp_to_next: Optional[int] = Field(None, ge=0)
    stat_points: Optional[int] = Field(None, ge=0)
    stats_int: Optional[int] = Field(None, ge=1, le=100)
    stats_dex: Optional[int] = Field(None, ge=1, le=100)
    stats_cha: Optional[int] = Field(None, ge=1, le=100)
    bio: Optional[str] = Field(None, max_length=500)
    skills: Optional[List[AdminSkill]] = Field(None, max_length=20)
    character_class: Optional[ClassId] = None


class AdminBanUserRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500, description="Ban reason")


class AdminGrantXPRequest(BaseModel):
    amount: int = Field(..., description="XP to grant (positive) or revoke (negative)")
    reason: str = Field(..., min_length=3, max_length=500)


class AdminAdjustWalletRequest(BaseModel):
    amount: Decimal = Field(..., ge=-10_000_000, le=10_000_000, description="Positive = credit, negative = debit")
    currency: str = Field(default="RUB", max_length=10)
    reason: str = Field(..., min_length=3, max_length=500)


class AdminUpdateQuestRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    budget: Optional[Decimal] = Field(None, ge=100, le=1_000_000)
    xp_reward: Optional[int] = Field(None, ge=10, le=500)
    required_grade: Optional[GradeEnum] = None
    status: Optional[Literal["open", "assigned", "in_progress", "completed", "confirmed", "cancelled", "revision_requested", "draft"]] = None
    assigned_to: Optional[str] = None
    is_urgent: Optional[bool] = None
    required_portfolio: Optional[bool] = None


class AdminForceQuestStatusRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)
    skip_escrow: bool = Field(
        default=False,
        description="Allow force-completion even without an active escrow hold (no payout to freelancer)",
    )


class AdminGrantBadgeRequest(BaseModel):
    badge_id: str = Field(..., min_length=1)


class AdminChangeClassRequest(BaseModel):
    class_id: Optional[str] = Field(None, description="Class ID or null to reset")


class AdminGrantPerkPointsRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Bonus perk points to grant")
    reason: str = Field(..., min_length=3, max_length=500)


class AdminBroadcastNotificationRequest(BaseModel):
    user_ids: List[str] = Field(..., min_length=1, description="At least one user ID is required")
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    event_type: str = Field(default="admin_broadcast")


class AdminGuildSeasonRewardConfigRequest(BaseModel):
    season_code: str = Field(..., min_length=2, max_length=40)
    family: str = Field(..., min_length=2, max_length=30)
    label: str = Field(..., min_length=2, max_length=80)
    accent: str = Field(..., min_length=2, max_length=20)
    treasury_bonus: Decimal = Field(...)
    guild_tokens_bonus: int = Field(default=0, ge=0)
    badge_name: str = Field(..., min_length=2, max_length=80)
    is_active: bool = True


# ─────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────

@router.get("/users", summary="List all users (admin)", response_model=AdminUsersListResponse)
async def admin_list_users(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    role: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=100),
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    return await admin_service.list_users(conn, page=page, page_size=page_size, role_filter=role, search=search)


# ─────────────────────────────────────────────────────────────────────
# Transactions
# ─────────────────────────────────────────────────────────────────────

@router.get("/transactions", summary="List transactions (admin)", response_model=AdminTransactionsListResponse)
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
    await _admin_rate_limit(request)
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
    await _admin_rate_limit(request)
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
    await _admin_rate_limit(request)
    ip = get_client_ip(request)

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
    await _admin_rate_limit(request)
    ip = get_client_ip(request)

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

@router.get("/logs", summary="Admin audit log", response_model=AdminLogsListResponse)
async def admin_get_logs(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    admin_id: Optional[str] = Query(default=None),
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
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
    summary="Generate a pending TOTP secret for the calling admin",
)
async def admin_totp_setup(
    request: Request,
    current_admin: UserProfile = Depends(require_admin_role_only),
    conn: asyncpg.Connection = Depends(get_db_connection),
    x_totp_token: Optional[str] = Header(None, alias="X-TOTP-Token"),
):
    """
    Generates a new TOTP secret and stores it as *pending*.

    If the admin already has an active TOTP secret, a valid current TOTP
    code must be provided in the ``X-TOTP-Token`` header to authorise
    rotation.  First-time setup does not require TOTP.

    The pending secret is **not active** until confirmed via
    POST /admin/auth/totp/enable.
    """
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="admin_totp_setup", limit=5, window_seconds=60)
    try:
        import pyotp
    except ImportError:
        raise HTTPException(status_code=500, detail="pyotp package not installed")

    from app.core.security import encrypt_totp_secret, decrypt_totp_secret

    # If admin already has an active TOTP, require current code for rotation
    existing_secret_enc = await conn.fetchval(
        "SELECT totp_secret FROM users WHERE id = $1", current_admin.id
    )
    if existing_secret_enc:
        if not x_totp_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Current X-TOTP-Token header required to rotate an existing TOTP secret",
            )
        existing_secret = decrypt_totp_secret(existing_secret_enc)
        if not pyotp.TOTP(existing_secret).verify(x_totp_token, valid_window=0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid current TOTP token — cannot rotate secret",
            )

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(
        name=current_admin.username,
        issuer_name="QuestionWork Admin",
    )

    encrypted = encrypt_totp_secret(secret)

    async with conn.transaction():
        await conn.execute(
            "UPDATE users SET pending_totp_secret = $1 WHERE id = $2",
            encrypted,
            current_admin.id,
        )
        action = "totp_rotation_started" if existing_secret_enc else "totp_setup_started"
        await admin_service.log_admin_action(
            conn,
            admin_id=current_admin.id,
            action=action,
            target_type="user",
            target_id=current_admin.id,
            ip_address=ip,
        )
    logger.info(f"Admin {current_admin.id} generated pending TOTP secret")

    return {"secret": secret, "otpauth_uri": uri}


@router.post(
    "/auth/totp/enable",
    summary="Activate the pending TOTP secret after verifying a valid token",
)
async def admin_totp_enable(
    body: VerifyTotpRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin_role_only),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """
    Verifies that the caller's authenticator app produces correct tokens for
    the *pending* secret created by /setup, then promotes it to the active
    secret.  This is the only path that activates a TOTP secret.
    """
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="admin_totp_enable", limit=5, window_seconds=60)
    try:
        import pyotp
    except ImportError:
        raise HTTPException(status_code=500, detail="pyotp package not installed")

    pending_secret_encrypted = await conn.fetchval(
        "SELECT pending_totp_secret FROM users WHERE id = $1", current_admin.id
    )
    if not pending_secret_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending TOTP secret. Call POST /admin/auth/totp/setup first.",
        )

    from app.core.security import decrypt_totp_secret
    pending_secret = decrypt_totp_secret(pending_secret_encrypted)
    totp = pyotp.TOTP(pending_secret)
    if not totp.verify(body.token, valid_window=0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP token",
        )

    # Promote pending → active and clear the pending slot
    async with conn.transaction():
        await conn.execute(
            "UPDATE users SET totp_secret = $1, pending_totp_secret = NULL WHERE id = $2",
            pending_secret_encrypted,
            current_admin.id,
        )
        await admin_service.log_admin_action(
            conn,
            admin_id=current_admin.id,
            action="totp_enabled",
            target_type="user",
            target_id=current_admin.id,
            ip_address=get_client_ip(request),
        )
    logger.info(f"Admin {current_admin.id} activated TOTP")

    return {"ok": True, "message": "TOTP activated. You can now enable ADMIN_TOTP_REQUIRED=True."}


@router.delete(
    "/auth/totp",
    summary="Disable TOTP for the calling admin",
)
async def admin_totp_disable(
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(
        get_client_ip(request), action="admin_totp_disable", limit=3, window_seconds=60
    )
    """Clears both the active and pending TOTP secrets. Requires full admin auth."""
    async with conn.transaction():
        await conn.execute(
            "UPDATE users SET totp_secret = NULL, pending_totp_secret = NULL WHERE id = $1",
            current_admin.id,
        )
        await admin_service.log_admin_action(
            conn,
            admin_id=current_admin.id,
            action="totp_disable",
            target_type="user",
            target_id=current_admin.id,
            ip_address=get_client_ip(request),
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
    await _admin_rate_limit(request)
    deleted = await admin_service.cleanup_old_notifications(conn)
    logger.info(
        f"Notification cleanup triggered by admin {current_admin.id}: {deleted} rows deleted"
    )
    return {
        "deleted": deleted,
        "message": f"Removed {deleted} old read notification(s).",
    }


# ═════════════════════════════════════════════════════════════════════
# GOD MODE ENDPOINTS
# ═════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────────
# Platform stats
# ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminPlatformStatsResponse, summary="Platform-wide statistics")
async def admin_platform_stats(
    request: Request,
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    return await admin_service.get_platform_stats(conn)


# ─────────────────────────────────────────────────────────────────────
# User detail / edit / ban / delete / XP / wallet / badge / class
# ─────────────────────────────────────────────────────────────────────

@router.get("/users/{user_id}", response_model=AdminUserDetailResponse, summary="Full user detail (admin)")
async def admin_get_user_detail(
    user_id: str,
    request: Request,
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    try:
        return await admin_service.get_user_detail(conn, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/users/{user_id}", summary="Edit user fields (admin)")
async def admin_update_user(
    user_id: str,
    body: AdminUpdateUserRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    try:
        async with conn.transaction():
            return await admin_service.update_user(conn, user_id, fields, current_admin.id, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/users/{user_id}/ban", summary="Ban user")
async def admin_ban_user(
    user_id: str,
    body: AdminBanUserRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.ban_user(conn, user_id, body.reason, current_admin.id, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/users/{user_id}/unban", summary="Unban user")
async def admin_unban_user(
    user_id: str,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.unban_user(conn, user_id, current_admin.id, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/users/{user_id}", summary="Hard delete user")
async def admin_delete_user(
    user_id: str,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.delete_user(conn, user_id, current_admin.id, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/users/{user_id}/grant-xp", summary="Grant or revoke XP")
async def admin_grant_xp(
    user_id: str,
    body: AdminGrantXPRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.grant_xp(conn, user_id, body.amount, body.reason, current_admin.id, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/users/{user_id}/adjust-wallet", summary="Credit or debit wallet")
async def admin_adjust_wallet(
    user_id: str,
    body: AdminAdjustWalletRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.adjust_wallet(
                conn, user_id, body.amount, body.currency, body.reason, current_admin.id, ip
            )
    except (ValueError, InsufficientFundsError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/users/{user_id}/grant-badge", summary="Award badge to user")
async def admin_grant_badge(
    user_id: str,
    body: AdminGrantBadgeRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.grant_badge(conn, user_id, body.badge_id, current_admin.id, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/users/{user_id}/badges/{badge_id}", summary="Revoke badge from user")
async def admin_revoke_badge(
    user_id: str,
    badge_id: str,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.revoke_badge(conn, user_id, badge_id, current_admin.id, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/users/{user_id}/change-class", summary="Force change or reset user class")
async def admin_change_class(
    user_id: str,
    body: AdminChangeClassRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.change_user_class(conn, user_id, body.class_id, current_admin.id, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/users/{user_id}/grant-perk-points", summary="Grant bonus perk points for class tree")
async def admin_grant_perk_points(
    user_id: str,
    body: AdminGrantPerkPointsRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.grant_class_perk_points(
                conn,
                user_id,
                body.amount,
                body.reason,
                current_admin.id,
                ip,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────
# Quest listing (admin) — P2-07
# ─────────────────────────────────────────────────────────────────────

@router.get("/quests", summary="List quests (admin)")
async def admin_list_quests(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    quest_status: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None, max_length=200),
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    return await admin_service.list_quests(conn, page=page, page_size=page_size, status_filter=quest_status, search=search)


# ─────────────────────────────────────────────────────────────────────
# Quest detail / edit / force-cancel / force-complete / delete
# ─────────────────────────────────────────────────────────────────────

@router.get("/quests/{quest_id}", response_model=AdminQuestDetailResponse, summary="Full quest detail (admin)")
async def admin_get_quest_detail(
    quest_id: str,
    request: Request,
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    try:
        return await admin_service.get_quest_detail(conn, quest_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/quests/{quest_id}", summary="Edit quest fields (admin)")
async def admin_update_quest(
    quest_id: str,
    body: AdminUpdateQuestRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    try:
        async with conn.transaction():
            return await admin_service.update_quest(conn, quest_id, fields, current_admin.id, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/quests/{quest_id}/force-cancel", summary="Force cancel quest")
async def admin_force_cancel_quest(
    quest_id: str,
    body: AdminForceQuestStatusRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.force_cancel_quest(conn, quest_id, body.reason, current_admin.id, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/quests/{quest_id}/force-complete", summary="Force complete quest")
async def admin_force_complete_quest(
    quest_id: str,
    body: AdminForceQuestStatusRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.force_complete_quest(conn, quest_id, body.reason, current_admin.id, ip, skip_escrow=body.skip_escrow)
    except EscrowMismatchError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ESCROW_CONFLICT_DETAIL)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/quests/{quest_id}", summary="Hard delete quest")
async def admin_delete_quest(
    quest_id: str,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.delete_quest(conn, quest_id, current_admin.id, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────
# Broadcast notification
# ─────────────────────────────────────────────────────────────────────

@router.post("/notifications/broadcast", summary="Send notification to multiple users")
async def admin_broadcast_notification(
    body: AdminBroadcastNotificationRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.broadcast_notification(
                conn, body.user_ids, body.title, body.message, body.event_type,
                current_admin.id, ip,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/guild-season-rewards",
    response_model=AdminGuildSeasonRewardConfigResponse,
    summary="Create or update guild seasonal reward config",
)
async def admin_upsert_guild_season_reward_config(
    body: AdminGuildSeasonRewardConfigRequest,
    request: Request,
    current_admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    ip = get_client_ip(request)
    try:
        async with conn.transaction():
            return await admin_service.upsert_guild_season_reward_config(
                conn,
                body.model_dump(),
                current_admin.id,
                ip,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
