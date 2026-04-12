"""Milestone escrow endpoints — staged payment release for quests."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.services import milestone_service

router = APIRouter(prefix="/quests", tags=["Milestones"])


class MilestoneCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    amount: Decimal = Field(..., gt=0, le=10_000_000)
    description: Optional[str] = Field(None, max_length=1000)
    sort_order: int = Field(default=0, ge=0, le=1000)
    due_at: Optional[datetime] = None
    currency: str = Field(default="RUB", pattern="^[A-Z]{3}$")


class MilestoneResponse(BaseModel):
    id: str
    quest_id: str
    title: str
    description: Optional[str] = None
    amount: Decimal
    currency: str
    sort_order: int
    status: str
    due_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str


def _fmt(row: dict) -> MilestoneResponse:
    def _dt(v) -> Optional[str]:
        return v.isoformat() if v else None
    return MilestoneResponse(
        id=row["id"],
        quest_id=row["quest_id"],
        title=row["title"],
        description=row.get("description"),
        amount=row["amount"],
        currency=row["currency"],
        sort_order=row["sort_order"],
        status=row["status"],
        due_at=_dt(row.get("due_at")),
        completed_at=_dt(row.get("completed_at")),
        created_at=_dt(row["created_at"]),
        updated_at=_dt(row["updated_at"]),
    )


@router.get("/{quest_id}/milestones", response_model=List[MilestoneResponse])
async def list_milestones(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="milestone_list", limit=60, window_seconds=60)
    rows = await milestone_service.list_milestones(conn, quest_id)
    return [_fmt(r) for r in rows]


@router.post("/{quest_id}/milestones", response_model=MilestoneResponse, status_code=status.HTTP_201_CREATED)
async def create_milestone(
    quest_id: str,
    body: MilestoneCreate,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="milestone_create", limit=20, window_seconds=60)
    try:
        async with conn.transaction():
            # Verify ownership
            client_id_in_quest = await conn.fetchval("SELECT client_id FROM quests WHERE id = $1", quest_id)
            if client_id_in_quest != current_user.id and current_user.role.value != "admin":
                raise HTTPException(status_code=403, detail="Только заказчик может добавлять milestones")
            row = await milestone_service.create_milestone(
                conn,
                quest_id=quest_id,
                title=body.title,
                amount=body.amount,
                description=body.description,
                sort_order=body.sort_order,
                due_at=body.due_at,
                currency=body.currency,
            )
        return _fmt(row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{quest_id}/milestones/{milestone_id}/activate", response_model=MilestoneResponse)
async def activate_milestone(
    quest_id: str,
    milestone_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="milestone_activate", limit=20, window_seconds=60)
    try:
        async with conn.transaction():
            row = await milestone_service.activate_milestone(conn, milestone_id=milestone_id, client_id=current_user.id)
        return _fmt(row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{quest_id}/milestones/{milestone_id}/complete", response_model=MilestoneResponse)
async def complete_milestone(
    quest_id: str,
    milestone_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="milestone_complete", limit=20, window_seconds=60)
    try:
        async with conn.transaction():
            row = await milestone_service.complete_milestone(conn, milestone_id=milestone_id, client_id=current_user.id)
        return _fmt(row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/{quest_id}/milestones/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_milestone(
    quest_id: str,
    milestone_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="milestone_cancel", limit=20, window_seconds=60)
    try:
        async with conn.transaction():
            await milestone_service.cancel_milestone(conn, milestone_id=milestone_id, client_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
