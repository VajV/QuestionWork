"""Saved searches endpoints.

GET    /saved-searches          — list user's saved searches
POST   /saved-searches          — create a new saved search
DELETE /saved-searches/{id}     — delete a saved search
"""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.lifecycle import SavedSearch, SavedSearchCreate, SavedSearchListResponse
from app.models.user import UserProfile
from app.services import saved_searches_service

router = APIRouter(prefix="/saved-searches", tags=["Saved Searches"])


@router.get("/", response_model=SavedSearchListResponse)
async def list_saved_searches(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> SavedSearchListResponse:
    """Return all saved searches for the authenticated user."""
    await check_rate_limit(get_client_ip(request), action="saved_search_read", limit=60, window_seconds=60)
    rows = await saved_searches_service.list_saved_searches(conn, current_user.id)
    items = [
        SavedSearch(
            id=str(r["id"]),
            user_id=r["user_id"],
            name=r["name"],
            search_type=r["search_type"],
            filters_json=dict(r["filters_json"]) if r["filters_json"] else {},
            alert_enabled=r["alert_enabled"],
            last_alerted_at=r["last_alerted_at"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return SavedSearchListResponse(items=items, total=len(items))


@router.post("/", response_model=SavedSearch, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    body: SavedSearchCreate,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> SavedSearch:
    """Create a new saved search / filter subscription."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="create_saved_search", limit=30, window_seconds=60)

    try:
        row = await saved_searches_service.create_saved_search(
            conn,
            current_user.id,
            name=body.name,
            search_type=body.search_type,
            filters_json=body.filters_json,
            alert_enabled=body.alert_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SavedSearch(
        id=str(row["id"]),
        user_id=row["user_id"],
        name=row["name"],
        search_type=row["search_type"],
        filters_json=dict(row["filters_json"]) if row["filters_json"] else {},
        alert_enabled=row["alert_enabled"],
        last_alerted_at=row["last_alerted_at"],
        created_at=row["created_at"],
    )


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> None:
    """Delete a saved search. Returns 404 if not found or not owned by the user."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="delete_saved_search", limit=30, window_seconds=60)

    deleted = await saved_searches_service.delete_saved_search(conn, search_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved search not found")
