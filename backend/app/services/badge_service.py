"""
BadgeService — checks user progress against badge criteria and awards new badges.

Event types that trigger checks:
  - quest_completed   : event_data = {"quests_completed": int, "xp": int, "earnings": float, "grade": str, "level": int}
  - level_up          : event_data = {"level": int, "xp": int, "grade": str}
  - quest_confirmed   : alias for quest_completed from the client side
  - registration      : event_data = {} (first login / new account)
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.models.badge_notification import BadgeAwardResult, UserBadgeEarned

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# Criteria evaluators
# ──────────────────────────────────────────

def _meets_criteria(criteria_type: str, criteria_value: int, event_data: dict) -> bool:
    """Return True if event_data satisfies badge criteria."""
    v = criteria_value
    match criteria_type:
        case "quests_completed":
            return int(event_data.get("quests_completed", 0)) >= v
        case "level":
            return int(event_data.get("level", 0)) >= v
        case "xp":
            return int(event_data.get("xp", 0)) >= v
        case "earnings":
            return float(event_data.get("earnings", 0.0)) >= v
        case "grade_junior":
            return event_data.get("grade") in ("junior", "middle", "senior")
        case "grade_middle":
            return event_data.get("grade") in ("middle", "senior")
        case "grade_senior":
            return event_data.get("grade") == "senior"
        case _:
            return False


# ──────────────────────────────────────────
# Public API
# ──────────────────────────────────────────

async def check_and_award(
    conn: asyncpg.Connection,
    user_id: str,
    event_type: str,
    event_data: dict,
) -> BadgeAwardResult:
    """Check all catalogue badges against event_data and award any newly earned ones.

    Must be called inside an existing DB transaction.

    Args:
        conn: asyncpg connection (already in a transaction).
        user_id: The user to check badges for.
        event_type: One of quest_completed, level_up, registration.
        event_data: Context dict used by _meets_criteria.

    Returns:
        BadgeAwardResult listing newly awarded badges (empty if none).
    """
    if not conn.is_in_transaction():
        raise RuntimeError(
            "check_and_award must be called inside an explicit DB transaction."
        )

    # Load all catalogue badges
    catalogue = await conn.fetch("SELECT * FROM badges")

    # Load badges already earned by this user
    already_earned = await conn.fetch(
        "SELECT badge_id FROM user_badges WHERE user_id = $1", user_id
    )
    earned_ids = {row["badge_id"] for row in already_earned}

    newly_earned: list[UserBadgeEarned] = []
    now = datetime.now(timezone.utc)

    for badge in catalogue:
        badge_id = badge["id"]
        if badge_id in earned_ids:
            continue  # already has this badge

        if not _meets_criteria(badge["criteria_type"], badge["criteria_value"], event_data):
            continue

        # Award the badge
        ub_id = f"ub_{uuid.uuid4().hex[:12]}"
        await conn.execute(
            """
            INSERT INTO user_badges (id, user_id, badge_id, earned_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, badge_id) DO NOTHING
            """,
            ub_id,
            user_id,
            badge_id,
            now,
        )

        newly_earned.append(
            UserBadgeEarned(
                id=ub_id,
                user_id=user_id,
                badge_id=badge_id,
                badge_name=badge["name"],
                badge_description=badge["description"],
                badge_icon=badge["icon"],
                earned_at=now,
            )
        )
        logger.info(f"Badge awarded: user={user_id}, badge={badge['name']} ({badge_id})")

    return BadgeAwardResult(newly_earned=newly_earned)


async def get_user_badges(
    conn: asyncpg.Connection,
    user_id: str,
) -> list[UserBadgeEarned]:
    """Return all badges earned by a user, newest first."""
    rows = await conn.fetch(
        """
        SELECT ub.id, ub.user_id, ub.badge_id, ub.earned_at,
               b.name, b.description, b.icon
        FROM user_badges ub
        JOIN badges b ON b.id = ub.badge_id
        WHERE ub.user_id = $1
        ORDER BY ub.earned_at DESC
        """,
        user_id,
    )
    return [
        UserBadgeEarned(
            id=row["id"],
            user_id=row["user_id"],
            badge_id=row["badge_id"],
            badge_name=row["name"],
            badge_description=row["description"],
            badge_icon=row["icon"],
            earned_at=row["earned_at"],
        )
        for row in rows
    ]


async def get_badge_catalogue(conn: asyncpg.Connection) -> list[dict]:
    """Return all available badges from the platform catalogue."""
    rows = await conn.fetch(
        "SELECT id, name, description, icon, criteria_type, criteria_value FROM badges ORDER BY criteria_value"
    )
    return [dict(row) for row in rows]
