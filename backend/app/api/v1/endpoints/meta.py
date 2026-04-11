"""Public world meta endpoints for shared frontend world-state UI."""

import asyncpg
from fastapi import APIRouter, Depends, Request

from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.meta import WorldMetaResponse
from app.services import meta_service

router = APIRouter(prefix="/meta", tags=["Meta"])


@router.get("/world", response_model=WorldMetaResponse)
async def get_world_meta(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="meta_world", limit=60, window_seconds=60)
    return WorldMetaResponse(**(await meta_service.get_world_meta(conn)))