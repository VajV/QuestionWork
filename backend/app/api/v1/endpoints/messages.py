"""
Endpoints для чата внутри квеста.

POST /messages/{quest_id}  — отправить сообщение (auth required, participant only)
GET  /messages/{quest_id}  — получить сообщения (auth required, participant only)
"""

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.services import message_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["Сообщения"])


# ── Schemas ────────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: str
    quest_id: str
    author_id: str
    author_username: Optional[str] = None
    text: str
    created_at: str


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/{quest_id}", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    quest_id: str,
    body: SendMessageRequest,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Send a message in a quest chat thread."""
    ip = request.client.host if request.client else "unknown"
    check_rate_limit(ip, action="send_message", limit=30, window_seconds=60)
    try:
        result = await message_service.send_message(
            conn, quest_id, current_user.id, body.text,
        )
        return MessageResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{quest_id}", response_model=MessageListResponse)
async def get_messages(
    quest_id: str,
    limit: int = Query(default=50, le=100),
    before: Optional[str] = None,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get messages for a quest (participant only)."""
    try:
        result = await message_service.get_messages(
            conn, quest_id, current_user.id, limit=limit, before=before,
        )
        return MessageListResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
