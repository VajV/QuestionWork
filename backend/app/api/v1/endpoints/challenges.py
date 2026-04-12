"""Weekly challenges endpoints."""

from typing import List

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.services import challenge_service

router = APIRouter(prefix="/challenges", tags=["Challenges"])


class ChallengeProgressResponse(BaseModel):
    id: str
    challenge_type: str
    title: str
    description: str
    target_value: int
    xp_reward: int
    week_start: str
    current_value: int
    completed: bool
    completed_at: str | None
    reward_granted: bool


@router.get("/weekly", response_model=List[ChallengeProgressResponse])
async def get_weekly_challenges(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return this week's challenges with the caller's progress."""
    check_rate_limit(get_client_ip(request), action="weekly_challenges", limit=60, window_seconds=60)
    try:
        # Ensure this week's challenges exist
        await challenge_service.ensure_weekly_challenges(conn)
        rows = await challenge_service.get_current_challenges(conn, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return [
        ChallengeProgressResponse(
            id=r["id"],
            challenge_type=r["challenge_type"],
            title=r["title"],
            description=r["description"],
            target_value=r["target_value"],
            xp_reward=r["xp_reward"],
            week_start=str(r["week_start"]),
            current_value=r["current_value"],
            completed=r["completed"],
            completed_at=r["completed_at"].isoformat() if r.get("completed_at") else None,
            reward_granted=r["reward_granted"],
        )
        for r in rows
    ]
