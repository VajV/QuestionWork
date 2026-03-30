"""
Seasonal events endpoints.

Routes:
  GET    /events                      — list events (public)
  GET    /events/{id}                 — get event detail (public)
  GET    /events/{id}/leaderboard     — get event leaderboard (public)
  POST   /events/{id}/join            — join an active event (auth)
  POST   /events/{id}/score           — submit score delta (auth)
  POST   /admin/events                — create event (admin)
  PATCH  /admin/events/{id}           — update draft event (admin)
  POST   /admin/events/{id}/activate  — activate event (admin)
  POST   /admin/events/{id}/end       — end event (admin)
  POST   /admin/events/{id}/finalize  — finalize event (admin)
"""

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import require_admin, require_auth
from app.core.ratelimit import check_rate_limit, check_user_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.event import (
    EventCreate,
    EventLeaderboardResponse,
    EventListResponse,
    EventOut,
    EventParticipantOut,
    EventUpdate,
    ScoreSubmit,
)
from app.models.user import UserProfile
from app.services import event_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["Events"])
admin_events_router = APIRouter(prefix="/admin/events", tags=["Admin"])


# ─────────────────────────────────────────────────────────────────────
# Public routes
# ─────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=EventListResponse,
    summary="List events",
)
async def list_events(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="event_list", limit=60, window_seconds=60)
    return await event_service.list_events(
        conn, status_filter=status_filter, limit=limit, offset=offset
    )


@router.get(
    "/{event_id}",
    response_model=EventOut,
    summary="Get event detail",
)
async def get_event(
    event_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="event_detail", limit=60, window_seconds=60)
    try:
        return await event_service.get_event(conn, event_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/{event_id}/leaderboard",
    response_model=EventLeaderboardResponse,
    summary="Get event leaderboard",
)
async def get_event_leaderboard(
    event_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="event_leaderboard", limit=60, window_seconds=60)
    try:
        return await event_service.get_leaderboard(conn, event_id, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────
# Authenticated user routes
# ─────────────────────────────────────────────────────────────────────

@router.post(
    "/{event_id}/join",
    response_model=EventParticipantOut,
    status_code=status.HTTP_201_CREATED,
    summary="Join an active event",
)
async def join_event(
    event_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="event_join", limit=10, window_seconds=60)
    await check_user_rate_limit(current_user.id, action="event_join", limit=10, window_seconds=60)

    try:
        async with conn.transaction():
            return await event_service.join_event(
                conn, event_id=event_id, user_id=current_user.id
            )
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_409_CONFLICT if "Already joined" in detail else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=detail)


@router.post(
    "/{event_id}/score",
    response_model=EventParticipantOut,
    summary="Submit score delta",
)
async def submit_event_score(
    event_id: str,
    body: ScoreSubmit,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="event_score", limit=30, window_seconds=60)
    await check_user_rate_limit(current_user.id, action="event_score", limit=30, window_seconds=60)

    try:
        async with conn.transaction():
            return await event_service.submit_score(
                conn, event_id=event_id, user_id=current_user.id, score_delta=body.score_delta
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────
# Admin routes (under /admin/events)
# ─────────────────────────────────────────────────────────────────────

@admin_events_router.post(
    "",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new event",
)
async def admin_create_event(
    body: EventCreate,
    request: Request,
    current_user: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="admin_event_create", limit=20, window_seconds=60)

    try:
        async with conn.transaction():
            return await event_service.create_event(
                conn,
                title=body.title,
                description=body.description,
                xp_multiplier=body.xp_multiplier,
                badge_reward_id=body.badge_reward_id,
                max_participants=body.max_participants,
                start_at=body.start_at,
                end_at=body.end_at,
                created_by=current_user.id,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@admin_events_router.patch(
    "/{event_id}",
    response_model=EventOut,
    summary="Update a draft event",
)
async def admin_update_event(
    event_id: str,
    body: EventUpdate,
    request: Request,
    current_user: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="admin_event_update", limit=20, window_seconds=60)

    try:
        async with conn.transaction():
            return await event_service.update_event(
                conn,
                event_id=event_id,
                admin_id=current_user.id,
                updates=body.model_dump(exclude_unset=True),
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@admin_events_router.post(
    "/{event_id}/activate",
    response_model=EventOut,
    summary="Activate a draft event",
)
async def admin_activate_event(
    event_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="admin_event_activate", limit=20, window_seconds=60)

    try:
        async with conn.transaction():
            return await event_service.activate_event(
                conn, event_id=event_id, admin_id=current_user.id
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@admin_events_router.post(
    "/{event_id}/end",
    response_model=EventOut,
    summary="End an active event",
)
async def admin_end_event(
    event_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="admin_event_end", limit=20, window_seconds=60)

    try:
        async with conn.transaction():
            return await event_service.end_event(conn, event_id=event_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@admin_events_router.post(
    "/{event_id}/finalize",
    summary="Finalize an ended event",
)
async def admin_finalize_event(
    event_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="admin_event_finalize", limit=20, window_seconds=60)

    try:
        async with conn.transaction():
            return await event_service.finalize_event(conn, event_id=event_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
