"""Public world meta endpoints for shared frontend world-state UI."""

import asyncpg
from fastapi import APIRouter, Depends

from app.db.session import get_db_connection
from app.models.meta import WorldMetaResponse
from app.services import meta_service

router = APIRouter(prefix="/meta", tags=["Meta"])


@router.get("/world", response_model=WorldMetaResponse)
async def get_world_meta(
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    return WorldMetaResponse(**(await meta_service.get_world_meta(conn)))