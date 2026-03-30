"""Shortlist endpoints — clients can save freelancers for later comparison."""

from typing import List

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.api.deps import require_auth
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.models.shortlist import ShortlistEntry, ShortlistResponse
from app.services import shortlist_service
from app.core.ratelimit import check_rate_limit, get_client_ip

router = APIRouter(prefix="/shortlists", tags=["Shortlists"])


class ShortlistAddRequest(BaseModel):
    freelancer_id: str


@router.post("/", response_model=ShortlistEntry, status_code=status.HTTP_201_CREATED)
async def add_shortlist(
    body: ShortlistAddRequest,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="shortlist_add", limit=30, window_seconds=60)
    if current_user.role.value != "client":
        raise HTTPException(status_code=403, detail="Только заказчики могут вести шортлист")
    if body.freelancer_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя добавить себя в шортлист")

    # Verify freelancer exists
    exists = await conn.fetchval("SELECT 1 FROM users WHERE id = $1 AND role = 'freelancer'", body.freelancer_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Фрилансер не найден")

    result = await shortlist_service.add_to_shortlist(conn, current_user.id, body.freelancer_id)
    if not result:
        raise HTTPException(status_code=500, detail="Не удалось добавить в шортлист")
    return ShortlistEntry(**result)


@router.delete("/{freelancer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_shortlist(
    freelancer_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="shortlist_remove", limit=30, window_seconds=60)
    removed = await shortlist_service.remove_from_shortlist(conn, current_user.id, freelancer_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Не найден в шортлисте")


@router.get("/", response_model=ShortlistResponse)
async def list_shortlist(
    request: Request,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="shortlist_list", limit=30, window_seconds=60)
    data = await shortlist_service.get_shortlist(conn, current_user.id, limit, offset)
    return ShortlistResponse(**data)


@router.get("/ids", response_model=List[str])
async def list_shortlist_ids(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Quick list of freelancer IDs in shortlist (for frontend icon state)."""
    await check_rate_limit(get_client_ip(request), action="shortlist_ids", limit=60, window_seconds=60)
    return await shortlist_service.get_shortlisted_ids(conn, current_user.id)
