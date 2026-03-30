"""Lifecycle CRM endpoints — admin controls for lifecycle messaging campaigns."""

from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.api.deps import require_admin
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.services import lifecycle_service

router = APIRouter(prefix="/lifecycle", tags=["Lifecycle CRM"])


class ScanResult(BaseModel):
    dormant_clients_enqueued: int = 0
    stale_shortlists_enqueued: int = 0


class EnqueueRequest(BaseModel):
    campaign_key: str
    user_id: str
    quest_id: Optional[str] = None


class EnqueueResponse(BaseModel):
    inserted: bool


@router.post(
    "/scan",
    response_model=ScanResult,
    summary="Trigger lifecycle scan (admin only)",
)
async def trigger_scan(
    request: Request,
    current_user: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> ScanResult:
    """Scan the database for users that should receive lifecycle nudges and enqueue them.

    Safe to call repeatedly — idempotency keys prevent duplicates.
    """
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="lifecycle_scan", limit=5, window_seconds=60)

    dormant = await lifecycle_service.scan_and_enqueue_dormant_clients(conn)
    stale = await lifecycle_service.scan_and_enqueue_stale_shortlists(conn)

    return ScanResult(
        dormant_clients_enqueued=dormant,
        stale_shortlists_enqueued=stale,
    )


@router.post(
    "/enqueue",
    response_model=EnqueueResponse,
    summary="Manually enqueue a lifecycle message (admin only)",
)
async def manual_enqueue(
    body: EnqueueRequest,
    request: Request,
    current_user: UserProfile = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> EnqueueResponse:
    """Manually enqueue a lifecycle message for a specific user.

    Useful for testing campaign templates from the admin panel.
    """
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="lifecycle_enqueue", limit=20, window_seconds=60)

    campaign_key = body.campaign_key
    user_id = body.user_id

    known_keys = {
        "incomplete_profile",
        "incomplete_quest_draft",
        "stale_shortlist",
        "unreviewed_completion",
        "dormant_client",
        "lead_no_register",
        "lead_no_quest",
    }
    if campaign_key not in known_keys:
        raise HTTPException(status_code=400, detail=f"Unknown campaign_key: {campaign_key!r}")

    try:
        async with conn.transaction():
            if campaign_key == "incomplete_profile":
                inserted = await lifecycle_service.enqueue_incomplete_profile(conn, user_id)
            elif campaign_key == "incomplete_quest_draft":
                if not body.quest_id:
                    raise HTTPException(status_code=400, detail="quest_id required for incomplete_quest_draft")
                inserted = await lifecycle_service.enqueue_incomplete_quest_draft(conn, user_id, body.quest_id)
            elif campaign_key == "stale_shortlist":
                inserted = await lifecycle_service.enqueue_stale_shortlist(conn, user_id)
            elif campaign_key == "unreviewed_completion":
                if not body.quest_id:
                    raise HTTPException(status_code=400, detail="quest_id required for unreviewed_completion")
                inserted = await lifecycle_service.enqueue_unreviewed_completion(conn, user_id, body.quest_id)
            elif campaign_key == "dormant_client":
                inserted = await lifecycle_service.enqueue_dormant_client(
                    conn, user_id, days=7, last_quest_id=body.quest_id or "manual"
                )
            elif campaign_key == "lead_no_register":
                inserted = await lifecycle_service.enqueue_lead_no_register(conn, user_id, email=user_id)
            else:  # lead_no_quest
                inserted = await lifecycle_service.enqueue_lead_no_quest(conn, user_id)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return EnqueueResponse(inserted=inserted)
