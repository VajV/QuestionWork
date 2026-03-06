"""
Endpoints для системы отзывов о квестах.

POST /reviews/       — создать отзыв (auth required)
GET  /reviews/user/{user_id} — получить отзывы пользователя
GET  /reviews/check/{quest_id} — проверить, оставлен ли уже отзыв
"""

import logging
from typing import List, Optional

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.services import email_service, review_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["Отзывы"])


# ── Request / Response schemas ─────────────────────────────────────────────

class CreateReviewRequest(BaseModel):
    quest_id: str = Field(..., description="Quest ID")
    reviewee_id: str = Field(..., description="Target user ID")
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    comment: Optional[str] = Field(None, max_length=2000)


class ReviewResponse(BaseModel):
    id: str
    quest_id: str
    reviewer_id: str
    reviewer_username: Optional[str] = None
    reviewee_id: str
    rating: int
    comment: Optional[str] = None
    created_at: str
    xp_bonus: int = 0


class UserReviewsResponse(BaseModel):
    reviews: List[ReviewResponse]
    total: int
    avg_rating: Optional[float] = None
    review_count: int


class ReviewCheckResponse(BaseModel):
    has_reviewed: bool


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    body: CreateReviewRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Create a review for a confirmed quest."""
    ip = request.client.host if request.client else "unknown"
    check_rate_limit(ip, action="create_review", limit=10, window_seconds=60)
    try:
        async with conn.transaction():
            result = await review_service.create_review(
                conn,
                quest_id=body.quest_id,
                reviewer_id=current_user.id,
                reviewee_id=body.reviewee_id,
                rating=body.rating,
                comment=body.comment,
            )
        review_obj = ReviewResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Notify reviewee (fire-and-forget)
    try:
        row = await conn.fetchrow(
            "SELECT email, username FROM users WHERE id = $1", body.reviewee_id
        )
        if row:
            background_tasks.add_task(
                email_service.send_review_received,
                to=row["email"],
                username=row["username"],
                reviewer_username=current_user.username,
                rating=body.rating,
                comment=body.comment,
            )
    except Exception as exc:
        logger.debug("Could not enqueue review email: %s", exc)
    return review_obj


@router.get("/user/{user_id}", response_model=UserReviewsResponse)
async def get_user_reviews(
    user_id: str,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get all reviews received by a user (public, no auth required)."""
    data = await review_service.get_reviews_for_user(
        conn, user_id, limit=limit, offset=offset
    )
    return UserReviewsResponse(
        reviews=[ReviewResponse(**r) for r in data["reviews"]],
        total=data["total"],
        avg_rating=data["avg_rating"],
        review_count=data["review_count"],
    )


@router.get("/check/{quest_id}", response_model=ReviewCheckResponse)
async def check_review_status(
    quest_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Check if the current user has already reviewed this quest."""
    reviewed = await review_service.has_reviewed(conn, quest_id, current_user.id)
    return ReviewCheckResponse(has_reviewed=reviewed)
