"""
Dispute resolution endpoints.

Routes:
  POST   /disputes                    — open a dispute (freelancer only)
  GET    /disputes                    — list my disputes
  GET    /disputes/{id}               — get dispute detail
  PATCH  /disputes/{id}/respond       — client responds to dispute
  POST   /disputes/{id}/escalate      — either party escalates
  PATCH  /disputes/{id}/resolve       — admin resolves (also in admin.py for admin prefix)
  GET    /admin/disputes              — admin: list all disputes
"""

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import require_admin, require_auth
from app.core.ratelimit import check_rate_limit, check_user_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.dispute import (
    DisputeCreate,
    DisputeListResponse,
    DisputeOut,
    DisputeResolve,
    DisputeRespond,
    ResolutionType,
)
from app.models.user import UserProfile
from app.services import dispute_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/disputes", tags=["Disputes"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])


# ─────────────────────────────────────────────────────────────────────
# User-facing routes
# ─────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=DisputeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Open a dispute on a quest",
)
async def open_dispute(
    body: DisputeCreate,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="dispute_open", limit=5, window_seconds=300)
    await check_user_rate_limit(current_user.id, action="dispute_open", limit=5, window_seconds=300)

    try:
        async with conn.transaction():
            return await dispute_service.open_dispute(
                conn,
                quest_id=body.quest_id,
                initiator_id=current_user.id,
                reason=body.reason,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_409_CONFLICT if "already exists" in detail else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=detail)


@router.get(
    "",
    response_model=DisputeListResponse,
    summary="List my disputes",
)
async def list_my_disputes(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="dispute_read", limit=60, window_seconds=60)
    return await dispute_service.list_my_disputes(conn, current_user.id, limit=limit, offset=offset)


@router.get(
    "/{dispute_id}",
    response_model=DisputeOut,
    summary="Get dispute detail",
)
async def get_dispute(
    dispute_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="dispute_read", limit=60, window_seconds=60)
    try:
        return await dispute_service.get_dispute(
            conn,
            dispute_id,
            user_id=current_user.id,
            is_admin=current_user.role == "admin",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.patch(
    "/{dispute_id}/respond",
    response_model=DisputeOut,
    summary="Client responds to an open dispute",
)
async def respond_dispute(
    dispute_id: str,
    body: DisputeRespond,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="dispute_respond", limit=20, window_seconds=300)

    try:
        async with conn.transaction():
            return await dispute_service.respond_dispute(
                conn,
                dispute_id=dispute_id,
                user_id=current_user.id,
                response_text=body.response_text,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.post(
    "/{dispute_id}/escalate",
    response_model=DisputeOut,
    summary="Escalate dispute to moderators",
)
async def escalate_dispute(
    dispute_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="dispute_escalate", limit=10, window_seconds=300)

    try:
        async with conn.transaction():
            return await dispute_service.escalate_dispute(
                conn,
                dispute_id=dispute_id,
                user_id=current_user.id,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.patch(
    "/{dispute_id}/resolve",
    response_model=DisputeOut,
    summary="Admin: resolve an escalated dispute",
)
async def resolve_dispute(
    dispute_id: str,
    body: DisputeResolve,
    request: Request,
    current_user: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    if body.resolution_type == ResolutionType.partial and body.partial_percent is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="partial_percent is required for 'partial' resolution",
        )
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="dispute_resolve", limit=60, window_seconds=60)

    try:
        async with conn.transaction():
            return await dispute_service.resolve_dispute(
                conn,
                dispute_id=dispute_id,
                moderator_id=current_user.id,
                resolution_type=body.resolution_type,
                resolution_note=body.resolution_note,
                partial_percent=body.partial_percent,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────
# Admin-prefixed routes (under /admin/disputes)
# ─────────────────────────────────────────────────────────────────────

@admin_router.get(
    "/disputes",
    response_model=DisputeListResponse,
    summary="Admin: list all disputes",
)
async def admin_list_disputes(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="admin_dispute_read", limit=60, window_seconds=60)
    return await dispute_service.admin_list_disputes(
        conn,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
