"""
Review service — business logic for quest reviews.

All write operations require an asyncpg connection inside an explicit transaction.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.core.cache import redis_cache, invalidate_cache_scope
from app.core.rewards import check_level_up, calculate_xp_to_next
from app.services import badge_service, trust_score_service

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────
# Models (lightweight dicts — Pydantic models live in models/)
# ────────────────────────────────────────────

REVIEW_BONUS_XP = 10  # XP awarded to *reviewer* for a 5-star review


# ────────────────────────────────────────────
# Create review
# ────────────────────────────────────────────

async def create_review(
    conn: asyncpg.Connection,
    quest_id: str,
    reviewer_id: str,
    reviewee_id: str,
    rating: int,
    comment: Optional[str] = None,
) -> dict:
    """Create a review for a confirmed quest.

    Validations:
    1. Quest exists and has status 'confirmed'
    2. Reviewer is a participant (client or assigned freelancer)
    3. Reviewer has not already reviewed this quest
    4. Reviewer ≠ reviewee

    Returns:
        dict with review data + optional xp_bonus info.

    Raises:
        ValueError on validation failure.
    """
    if not conn.is_in_transaction():
        raise RuntimeError("create_review must be called inside a DB transaction")

    if reviewer_id == reviewee_id:
        raise ValueError("Нельзя оставить отзыв самому себе")

    if not (1 <= rating <= 5):
        raise ValueError("Рейтинг должен быть от 1 до 5")

    # 1. Check quest status
    quest = await conn.fetchrow(
        "SELECT id, client_id, assigned_to, status FROM quests WHERE id = $1 FOR SHARE",
        quest_id,
    )
    if not quest:
        raise ValueError("Квест не найден")
    if quest["status"] != "confirmed":
        raise ValueError("Отзыв можно оставить только после подтверждения квеста")

    # 2. Check reviewer is participant
    participants = {quest["client_id"], quest["assigned_to"]}
    if reviewer_id not in participants:
        raise ValueError("Вы не являетесь участником этого квеста")

    # 3. Verify reviewee is the other participant
    if reviewee_id not in participants:
        raise ValueError("Получатель отзыва не является участником квеста")

    # 4. Check duplicate
    existing = await conn.fetchval(
        "SELECT 1 FROM quest_reviews WHERE quest_id = $1 AND reviewer_id = $2",
        quest_id,
        reviewer_id,
    )
    if existing:
        raise ValueError("Вы уже оставили отзыв на этот квест")

    # 5. Insert review
    review_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO quest_reviews (id, quest_id, reviewer_id, reviewee_id, rating, comment, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        review_id,
        quest_id,
        reviewer_id,
        reviewee_id,
        rating,
        comment,
        now,
    )

    # 6. Refresh reviewee's cached rating on users table
    await _refresh_user_rating(conn, reviewee_id)
    await trust_score_service.refresh_trust_score(conn, reviewee_id)
    await invalidate_cache_scope("user_rating", "user", reviewee_id)

    # 7. Bonus XP for 5-star review → reviewer (with level-up check)
    xp_bonus = 0
    if rating == 5:
        xp_bonus = REVIEW_BONUS_XP
        # P1 R-02 FIX: Use FOR UPDATE to prevent lost-update race on concurrent XP grants
        reviewer_row = await conn.fetchrow(
            "SELECT xp, level, grade FROM users WHERE id = $1 FOR UPDATE", reviewer_id
        )
        if reviewer_row:
            from app.models.user import GradeEnum
            new_xp = reviewer_row["xp"] + xp_bonus
            current_grade = GradeEnum(reviewer_row["grade"])
            level_up, new_grade, new_level, _ = check_level_up(new_xp, current_grade)
            new_xp_to_next = calculate_xp_to_next(new_xp, new_grade)
            await conn.execute(
                """
                UPDATE users SET xp = $1, level = $2, grade = $3,
                    xp_to_next = $4, updated_at = CURRENT_TIMESTAMP
                WHERE id = $5
                """,
                new_xp, new_level, new_grade.value,
                new_xp_to_next, reviewer_id,
            )
        else:
            # Fallback: reviewer row disappeared between check and update; still apply XP with level-up
            logger.warning("Reviewer %s not found for XP grant; applying raw increment", reviewer_id)
            await conn.execute(
                "UPDATE users SET xp = xp + $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                xp_bonus, reviewer_id,
            )

    # 8. Badge checks (reviewer — reviews_given, reviewee — five_star_received)
    badges_earned: list[dict] = []
    try:
        # Count reviews written by reviewer
        reviews_given_count = await conn.fetchval(
            "SELECT COUNT(*) FROM quest_reviews WHERE reviewer_id = $1",
            reviewer_id,
        )
        reviewer_data = await conn.fetchrow(
            "SELECT xp, level, grade FROM users WHERE id = $1",
            reviewer_id,
        )
        reviewer_event = {
            "reviews_given": reviews_given_count or 0,
            "xp": reviewer_data["xp"] if reviewer_data else 0,
            "level": reviewer_data["level"] if reviewer_data else 1,
            "grade": reviewer_data["grade"] if reviewer_data else "novice",
        }
        reviewer_result = await badge_service.check_and_award(
            conn, reviewer_id, "review_given", reviewer_event,
        )
        for b in reviewer_result.newly_earned:
            badges_earned.append({"user_id": reviewer_id, "badge_name": b.badge_name, "badge_icon": b.badge_icon})

        # If 5-star → check reviewee badges for five_star_received
        if rating == 5:
            five_star_count = await conn.fetchval(
                "SELECT COUNT(*) FROM quest_reviews WHERE reviewee_id = $1 AND rating = 5",
                reviewee_id,
            )
            reviewee_event = {"five_star_received": five_star_count or 0}
            reviewee_result = await badge_service.check_and_award(
                conn, reviewee_id, "five_star_received", reviewee_event,
            )
            for b in reviewee_result.newly_earned:
                badges_earned.append({"user_id": reviewee_id, "badge_name": b.badge_name, "badge_icon": b.badge_icon})
    except (KeyError, TypeError, AttributeError, LookupError) as exc:
        logger.warning("Badge check after review failed (non-critical): %s", exc, exc_info=True)

    return {
        "id": review_id,
        "quest_id": quest_id,
        "reviewer_id": reviewer_id,
        "reviewee_id": reviewee_id,
        "rating": rating,
        "comment": comment,
        "created_at": now.isoformat(),
        "xp_bonus": xp_bonus,
        "badges_earned": badges_earned,
    }


# ────────────────────────────────────────────
# Read helpers
# ────────────────────────────────────────────

async def get_reviews_for_user(
    conn: asyncpg.Connection,
    user_id: str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Get reviews received by a user (as reviewee).

    Returns:
        dict with keys: reviews (list), total (int), avg_rating (float|None), review_count (int).
    """
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM quest_reviews WHERE reviewee_id = $1",
        user_id,
    )
    avg = await conn.fetchval(
        "SELECT AVG(rating)::NUMERIC(3,2) FROM quest_reviews WHERE reviewee_id = $1",
        user_id,
    )
    rows = await conn.fetch(
        """
        SELECT r.id, r.quest_id, r.reviewer_id, r.reviewee_id,
               r.rating, r.comment, r.created_at,
               u.username AS reviewer_username
        FROM quest_reviews r
        JOIN users u ON u.id = r.reviewer_id
        WHERE r.reviewee_id = $1
        ORDER BY r.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        user_id,
        limit,
        offset,
    )

    reviews = [
        {
            "id": row["id"],
            "quest_id": row["quest_id"],
            "reviewer_id": row["reviewer_id"],
            "reviewer_username": row["reviewer_username"],
            "reviewee_id": row["reviewee_id"],
            "rating": row["rating"],
            "comment": row["comment"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]

    return {
        "reviews": reviews,
        "total": total or 0,
        "avg_rating": round(avg, 2) if avg is not None else None,
        "review_count": total or 0,
    }


@redis_cache(ttl_seconds=120, key_prefix="user_rating", scope_builder=lambda conn, user_id: f"user:{user_id}")
async def get_user_rating(
    conn: asyncpg.Connection,
    user_id: str,
) -> dict:
    """Quick aggregation: avg_rating + review_count for a single user."""
    row = await conn.fetchrow(
        """
        SELECT AVG(rating)::NUMERIC(3,2) AS avg_rating, COUNT(*) AS review_count
        FROM quest_reviews
        WHERE reviewee_id = $1
        """,
        user_id,
    )
    return {
        "avg_rating": round(row["avg_rating"], 2) if row and row["avg_rating"] is not None else None,
        "review_count": row["review_count"] if row else 0,
    }


async def has_reviewed(
    conn: asyncpg.Connection,
    quest_id: str,
    reviewer_id: str,
) -> bool:
    """Check if a user already reviewed a specific quest."""
    val = await conn.fetchval(
        "SELECT 1 FROM quest_reviews WHERE quest_id = $1 AND reviewer_id = $2",
        quest_id,
        reviewer_id,
    )
    return val is not None


# ────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────

async def _refresh_user_rating(conn: asyncpg.Connection, user_id: str) -> None:
    """Recalculate and cache avg_rating & review_count on the users row.

    P2 D-02 FIX: Lock the user row first to prevent concurrent reviews
    from overwriting each other's cached rating.
    """
    # Lock user row to serialise concurrent rating refreshes
    await conn.fetchrow(
        "SELECT id FROM users WHERE id = $1 FOR UPDATE", user_id
    )
    await conn.execute(
        """
        UPDATE users
        SET avg_rating = sub.avg_r,
            review_count = sub.cnt
        FROM (
            SELECT AVG(rating)::NUMERIC(3,2) AS avg_r, COUNT(*) AS cnt
            FROM quest_reviews
            WHERE reviewee_id = $1
        ) sub
        WHERE id = $1
        """,
        user_id,
    )
