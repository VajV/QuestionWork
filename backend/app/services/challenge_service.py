"""Weekly challenge service — RPG weekly missions that reset on Monday."""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import asyncpg

from app.services import notification_service

logger = logging.getLogger(__name__)

# Challenge type definitions
CHALLENGE_CATALOG = [
    {
        "challenge_type": "complete_quests",
        "title": "Искатель приключений",
        "description": "Завершите 3 квеста за неделю",
        "target_value": 3,
        "xp_reward": 250,
    },
    {
        "challenge_type": "earn_five_star",
        "title": "Мастер качества",
        "description": "Получите 5-звёздочный отзыв",
        "target_value": 1,
        "xp_reward": 150,
    },
    {
        "challenge_type": "complete_urgent",
        "title": "Боевое крещение",
        "description": "Выполните 2 срочных квеста",
        "target_value": 2,
        "xp_reward": 200,
    },
    {
        "challenge_type": "apply_to_quests",
        "title": "Охотник",
        "description": "Подайте 5 заявок на квесты",
        "target_value": 5,
        "xp_reward": 100,
    },
    {
        "challenge_type": "earn_xp",
        "title": "Опытный герой",
        "description": "Заработайте 500 XP за неделю",
        "target_value": 500,
        "xp_reward": 300,
    },
]


def _current_week_start() -> date:
    today = date.today()
    # Monday of current week
    return today - timedelta(days=today.weekday())


async def ensure_weekly_challenges(conn: asyncpg.Connection) -> List[dict]:
    """Ensure challenges exist for the current week. Idempotent."""
    week_start = _current_week_start()

    # Check if already seeded
    existing = await conn.fetch(
        "SELECT id, challenge_type FROM weekly_challenges WHERE week_start = $1",
        week_start,
    )
    if len(existing) >= len(CHALLENGE_CATALOG):
        return [dict(r) for r in existing]

    existing_types = {r["challenge_type"] for r in existing}
    created = []
    now = datetime.now(timezone.utc)

    for cat in CHALLENGE_CATALOG:
        if cat["challenge_type"] in existing_types:
            continue
        ch_id = f"ch_{secrets.token_hex(8)}"
        row = await conn.fetchrow(
            """
            INSERT INTO weekly_challenges
                (id, week_start, challenge_type, title, description, target_value, xp_reward, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (week_start, challenge_type) DO NOTHING
            RETURNING id, week_start, challenge_type, title, description, target_value, xp_reward, created_at
            """,
            ch_id,
            week_start,
            cat["challenge_type"],
            cat["title"],
            cat["description"],
            cat["target_value"],
            cat["xp_reward"],
            now,
        )
        if row:
            created.append(dict(row))

    return created or [dict(r) for r in existing]


async def get_current_challenges(
    conn: asyncpg.Connection, user_id: str
) -> List[dict]:
    """Return this week's challenges with user progress merged in."""
    week_start = _current_week_start()

    rows = await conn.fetch(
        """
        SELECT
            wc.id, wc.challenge_type, wc.title, wc.description,
            wc.target_value, wc.xp_reward, wc.week_start,
            COALESCE(ucp.current_value, 0) AS current_value,
            COALESCE(ucp.completed, FALSE) AS completed,
            ucp.completed_at,
            COALESCE(ucp.reward_granted, FALSE) AS reward_granted
        FROM weekly_challenges wc
        LEFT JOIN user_challenge_progress ucp
            ON ucp.challenge_id = wc.id AND ucp.user_id = $2
        WHERE wc.week_start = $1
        ORDER BY wc.challenge_type
        """,
        week_start,
        user_id,
    )
    return [dict(r) for r in rows]


async def increment_challenge_progress(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    challenge_type: str,
    increment: int = 1,
    week_start: Optional[date] = None,
) -> Optional[dict]:
    """Increment a user's progress on a challenge type for the current week.

    Returns the updated progress row if the challenge was found, otherwise None.
    Grants XP reward if newly completed.
    """
    if week_start is None:
        week_start = _current_week_start()

    challenge = await conn.fetchrow(
        "SELECT id, target_value, xp_reward, title FROM weekly_challenges "
        "WHERE week_start = $1 AND challenge_type = $2",
        week_start,
        challenge_type,
    )
    if not challenge:
        return None

    ch_id = challenge["id"]
    progress_id = f"ucp_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc)

    row = await conn.fetchrow(
        """
        INSERT INTO user_challenge_progress (id, user_id, challenge_id, current_value, updated_at)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, challenge_id) DO UPDATE
            SET current_value = LEAST(
                    user_challenge_progress.current_value + EXCLUDED.current_value,
                    (SELECT target_value FROM weekly_challenges WHERE id = $3)
                ),
                updated_at = EXCLUDED.updated_at
        RETURNING id, current_value, completed, reward_granted
        """,
        progress_id, user_id, ch_id, increment, now,
    )

    # Check if newly completed and reward not yet granted
    if (
        row["current_value"] >= challenge["target_value"]
        and not row["completed"]
        and not row["reward_granted"]
    ):
        await conn.execute(
            """
            UPDATE user_challenge_progress
            SET completed = TRUE, completed_at = $1, reward_granted = TRUE, updated_at = $1
            WHERE user_id = $2 AND challenge_id = $3
            """,
            now, user_id, ch_id,
        )

        # Grant XP reward
        await conn.execute(
            "UPDATE users SET xp = xp + $1, updated_at = $2 WHERE id = $3",
            challenge["xp_reward"], now, user_id,
        )

        await notification_service.create_notification(
            conn,
            user_id,
            title=f"🏆 Недельный вызов выполнен: «{challenge['title']}»!",
            message=f"Вы получили {challenge['xp_reward']} XP за завершение еженедельного задания.",
            event_type="weekly_challenge_completed",
        )
        logger.info("Weekly challenge completed: user=%s type=%s xp=%d", user_id, challenge_type, challenge["xp_reward"])

    return dict(row)
