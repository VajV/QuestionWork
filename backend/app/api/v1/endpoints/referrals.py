"""Referral endpoints — generate and apply referral codes."""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.services import referral_service

router = APIRouter(prefix="/referrals", tags=["Referrals"])


class ReferralInfoResponse(BaseModel):
    code: str | None
    total_referred: int
    rewarded_count: int


class ApplyReferralRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=16)


class ApplyReferralResponse(BaseModel):
    referrer_id: str
    applied: bool


@router.get("/me", response_model=ReferralInfoResponse)
async def get_my_referral_info(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get the caller's referral code and stats."""
    check_rate_limit(get_client_ip(request), action="referral_info", limit=30, window_seconds=60)
    info = await referral_service.get_my_referral_info(conn, current_user.id)
    return ReferralInfoResponse(**info)


@router.post("/generate", response_model=ReferralInfoResponse)
async def generate_referral_code(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Generate a referral code (idempotent)."""
    check_rate_limit(get_client_ip(request), action="referral_generate", limit=5, window_seconds=60)
    async with conn.transaction():
        code = await referral_service.get_or_create_referral_code(conn, current_user.id)
    info = await referral_service.get_my_referral_info(conn, current_user.id)
    return ReferralInfoResponse(**info)


@router.post("/apply", response_model=ApplyReferralResponse)
async def apply_referral_code(
    body: ApplyReferralRequest,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Apply a referral code to the authenticated user."""
    check_rate_limit(get_client_ip(request), action="referral_apply", limit=5, window_seconds=60)
    try:
        async with conn.transaction():
            result = await referral_service.apply_referral_code(conn, current_user.id, body.code)
        return ApplyReferralResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
