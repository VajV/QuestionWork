"""Admin runtime observability and trust-layer status endpoints."""

from __future__ import annotations

from datetime import datetime

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status

from app.api.deps import require_admin
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.admin import (
    AdminCommandStatusResponse,
    AdminJobReplayRequest,
    AdminJobReplayResponse,
    AdminJobStatusResponse,
    AdminOperationsFeedResponse,
    AdminRuntimeHeartbeatPruneResponse,
    AdminRuntimeHeartbeatsResponse,
)
from app.models.user import UserProfile
from app.services import admin_runtime_service

router = APIRouter(prefix="/admin", tags=["Admin"])


async def _admin_rate_limit(request: Request) -> None:
    ip = get_client_ip(request)
    route = request.scope.get("route")
    route_path = getattr(route, "path", None) or request.url.path or "/admin"
    action = f"admin:{request.method.upper()}:{route_path}"
    await check_rate_limit(ip, action=action, limit=120, window_seconds=60)


@router.get("/commands/{command_id}", response_model=AdminCommandStatusResponse, summary="Get trust-layer command status")
async def admin_get_command_status(
    command_id: str,
    request: Request,
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    result = await admin_runtime_service.get_command_status(conn, command_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found")
    return result


@router.get("/jobs/{job_id}", response_model=AdminJobStatusResponse, summary="Get trust-layer job status")
async def admin_get_job_status(
    job_id: str,
    request: Request,
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    result = await admin_runtime_service.get_job_status(conn, job_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return result


@router.post(
    "/jobs/{job_id}/requeue",
    response_model=AdminJobReplayResponse,
    summary="Manually requeue failed or dead-letter trust-layer job",
)
async def admin_requeue_job(
    job_id: str,
    request: Request,
    admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
    body: AdminJobReplayRequest | None = Body(default=None),
):
    await _admin_rate_limit(request)
    try:
        result = await admin_runtime_service.requeue_job(
            conn,
            job_id=job_id,
            admin_id=admin.id,
            reason=body.reason if body is not None else None,
            request_ip=get_client_ip(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return result


@router.get("/operations", response_model=AdminOperationsFeedResponse, summary="List admin trust-layer operations")
async def admin_list_operations(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
    action: str | None = Query(default=None),
    actor_admin_id: str | None = Query(default=None, alias="actor"),
    submitted_from: datetime | None = Query(default=None, alias="from"),
    submitted_to: datetime | None = Query(default=None, alias="to"),
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    return await admin_runtime_service.list_operations(
        conn,
        page=page,
        page_size=page_size,
        status=status_filter,
        action=action,
        actor_admin_id=actor_admin_id,
        submitted_from=submitted_from,
        submitted_to=submitted_to,
    )


@router.get(
    "/runtime/heartbeats",
    response_model=AdminRuntimeHeartbeatsResponse,
    summary="List worker and scheduler heartbeats",
)
async def admin_list_runtime_heartbeats(
    request: Request,
    runtime_kind: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    active_only: bool = Query(default=True),
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    return await admin_runtime_service.list_runtime_heartbeats(
        conn,
        runtime_kind=runtime_kind,
        limit=limit,
        active_only=active_only,
    )


@router.post(
    "/runtime/heartbeats/prune",
    response_model=AdminRuntimeHeartbeatPruneResponse,
    summary="Prune stale runtime heartbeat rows",
)
async def admin_prune_runtime_heartbeats(
    request: Request,
    runtime_kind: str | None = Query(default=None),
    stale_only: bool = Query(default=True),
    retention_seconds: int | None = Query(default=None, ge=0),
    _admin: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _admin_rate_limit(request)
    return await admin_runtime_service.prune_runtime_heartbeats(
        conn,
        runtime_kind=runtime_kind,
        stale_only=stale_only,
        retention_seconds=retention_seconds,
    )