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
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.realtime import WebSocketTicketResponse
from app.models.user import UserProfile
from app.services import message_service, realtime_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["Сообщения"])


# ── Schemas ────────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: str
    quest_id: str
    author_id: Optional[str] = None
    author_username: Optional[str] = None
    text: str
    created_at: str
    message_type: str = "user"


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int
    unread_count: int = 0


class DialogResponse(BaseModel):
    quest_id: str
    quest_title: str
    quest_status: str
    other_user_id: Optional[str] = None
    other_username: Optional[str] = None
    last_message_text: Optional[str] = None
    last_message_type: str = "user"
    last_message_at: Optional[str] = None
    unread_count: int = 0


class DialogListResponse(BaseModel):
    dialogs: list[DialogResponse]
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
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="send_message", limit=30, window_seconds=60)
    try:
        async with conn.transaction():
            result = await message_service.send_message(
                conn, quest_id, current_user.id, body.text,
            )
        return MessageResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/dialogs", response_model=DialogListResponse)
async def list_dialogs(
    request: Request,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """List user's active quest dialogs with unread counters."""
    await check_rate_limit(get_client_ip(request), action="list_dialogs", limit=30, window_seconds=60)
    result = await message_service.list_dialogs(
        conn,
        current_user.id,
        limit=limit,
        offset=offset,
    )
    return DialogListResponse(
        dialogs=[DialogResponse(**d) for d in result["dialogs"]],
        total=result["total"],
    )


@router.get("/{quest_id}", response_model=MessageListResponse)
async def get_messages(
    quest_id: str,
    request: Request,
    limit: int = Query(default=50, le=100),
    before: Optional[str] = None,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get messages for a quest (participant only)."""
    await check_rate_limit(get_client_ip(request), action="get_messages", limit=60, window_seconds=60)
    try:
        result = await message_service.get_messages(
            conn, quest_id, current_user.id, limit=limit, before=before,
        )
        return MessageListResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{quest_id}/ws-ticket", response_model=WebSocketTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_ws_ticket(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Issue a short-lived WebSocket ticket for quest chat auth."""
    await check_rate_limit(get_client_ip(request), action="issue_chat_ws_ticket", limit=30, window_seconds=60)
    try:
        ticket = await realtime_service.issue_chat_ticket(conn, user_id=current_user.id, quest_id=quest_id)
        return WebSocketTicketResponse(**ticket)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
