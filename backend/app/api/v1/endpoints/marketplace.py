"""Talent market and guild endpoints."""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.marketplace import GuildActionResponse, GuildCreateRequest, GuildDetailResponse, TalentMarketResponse
from app.models.user import UserProfile
from app.services import marketplace_service

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


@router.get("/talent", response_model=TalentMarketResponse)
async def get_talent_market(
    request: Request,
    mode: str = Query(default="all", pattern="^(all|solo|guild|top-guilds)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    grade: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=80),
    sort_by: str = Query(default="xp", pattern="^(xp|level|username|rating|trust)$"),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="get_talent_market", limit=30, window_seconds=60)
    return TalentMarketResponse(**(await marketplace_service.get_talent_market(
        conn,
        mode=mode,
        limit=limit,
        offset=skip,
        grade=grade,
        search=search,
        sort_by=sort_by,
    )))

@router.get("/guilds/{guild_slug}", response_model=GuildDetailResponse)
async def get_guild_detail(
    guild_slug: str,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    try:
        return GuildDetailResponse(**(await marketplace_service.get_guild_public_profile(conn, guild_slug)))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/guilds", response_model=GuildActionResponse)
async def create_guild(
    body: GuildCreateRequest,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="create_guild", limit=5, window_seconds=3600)
    try:
        return GuildActionResponse(**(await marketplace_service.create_guild(conn, current_user, body)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/guilds/{guild_id}/join", response_model=GuildActionResponse)
async def join_guild(
    guild_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="join_guild", limit=10, window_seconds=3600)
    try:
        return GuildActionResponse(**(await marketplace_service.join_guild(conn, guild_id, current_user)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/guilds/{guild_id}/leave", response_model=GuildActionResponse)
async def leave_guild(
    guild_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="leave_guild", limit=10, window_seconds=3600)
    try:
        return GuildActionResponse(**(await marketplace_service.leave_guild(conn, guild_id, current_user)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
