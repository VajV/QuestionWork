"""
Seasonal events service.

Handles the full lifecycle:
  draft → active → ended → finalized

All write operations must be called inside an explicit DB transaction.
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import asyncpg

from app.core.rewards import (
    allocate_stat_points,
    calculate_xp_to_next,
    check_level_up,
)
from app.models.event import (
    EventLeaderboardResponse,
    EventListResponse,
    EventOut,
    EventParticipantOut,
    EventStatus,
    LeaderboardEntry,
)
from app.models.user import GradeEnum
from app.services import notification_service

logger = logging.getLogger(__name__)

MAX_EVENT_DURATION = timedelta(hours=72)

STAT_CAP = 100

# XP bonus tiers for finalization
_XP_BONUS_TIERS = {
    1: 100,
    2: 50,
    3: 25,
}
_XP_BONUS_TOP10 = 10


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex[:14]}"


def _new_participant_id() -> str:
    return f"evp_{uuid.uuid4().hex[:14]}"


def _new_leaderboard_id() -> str:
    return f"elb_{uuid.uuid4().hex[:14]}"


def _assert_in_transaction(conn: asyncpg.Connection) -> None:
    if not conn.is_in_transaction():
        raise RuntimeError("event_service calls must be inside an explicit DB transaction")


def _row_to_event_out(row, *, participant_count: int = 0) -> EventOut:
    return EventOut(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=EventStatus(row["status"]),
        xp_multiplier=row["xp_multiplier"],
        badge_reward_id=row["badge_reward_id"],
        max_participants=row["max_participants"],
        participant_count=participant_count,
        created_by=row["created_by"],
        start_at=row["start_at"],
        end_at=row["end_at"],
        finalized_at=row["finalized_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_participant_out(row) -> EventParticipantOut:
    return EventParticipantOut(
        id=row["id"],
        event_id=row["event_id"],
        user_id=row["user_id"],
        username=row["username"],
        score=row["score"],
        joined_at=row["joined_at"],
    )


# ─────────────────────────────────────────────────────────────────────
# Read operations
# ─────────────────────────────────────────────────────────────────────

async def get_event(conn: asyncpg.Connection, event_id: str) -> EventOut:
    row = await conn.fetchrow("SELECT * FROM events WHERE id = $1", event_id)
    if row is None:
        raise ValueError("Event not found")
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM event_participants WHERE event_id = $1", event_id
    )
    return _row_to_event_out(row, participant_count=count or 0)


async def list_events(
    conn: asyncpg.Connection,
    *,
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> EventListResponse:
    if status_filter:
        rows = await conn.fetch(
            """
            SELECT e.*, COALESCE(pc.cnt, 0) AS participant_count
            FROM events e
            LEFT JOIN (SELECT event_id, COUNT(*) AS cnt FROM event_participants GROUP BY event_id) pc
                ON pc.event_id = e.id
            WHERE e.status = $1
            ORDER BY e.start_at DESC
            LIMIT $2 OFFSET $3
            """,
            status_filter, limit + 1, offset,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE status = $1", status_filter
        )
    else:
        rows = await conn.fetch(
            """
            SELECT e.*, COALESCE(pc.cnt, 0) AS participant_count
            FROM events e
            LEFT JOIN (SELECT event_id, COUNT(*) AS cnt FROM event_participants GROUP BY event_id) pc
                ON pc.event_id = e.id
            ORDER BY e.start_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit + 1, offset,
        )
        total = await conn.fetchval("SELECT COUNT(*) FROM events")

    has_more = len(rows) > limit
    items_rows = rows[:limit]
    items = [
        _row_to_event_out(r, participant_count=r["participant_count"])
        for r in items_rows
    ]
    return EventListResponse(items=items, total=total or 0, has_more=has_more)


async def get_leaderboard(
    conn: asyncpg.Connection,
    event_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> EventLeaderboardResponse:
    event = await conn.fetchrow("SELECT id, status FROM events WHERE id = $1", event_id)
    if event is None:
        raise ValueError("Event not found")

    total = await conn.fetchval(
        "SELECT COUNT(*) FROM event_participants WHERE event_id = $1", event_id
    )

    if event["status"] == "finalized":
        rows = await conn.fetch(
            """
            SELECT el.rank, el.user_id, u.username, u.grade, el.score, el.xp_bonus, el.badge_awarded
            FROM event_leaderboard el
            JOIN users u ON u.id = el.user_id
            WHERE el.event_id = $1
            ORDER BY el.rank
            LIMIT $2 OFFSET $3
            """,
            event_id, limit, offset,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT
                ROW_NUMBER() OVER (ORDER BY ep.score DESC, ep.joined_at ASC) AS rank,
                ep.user_id, u.username, u.grade, ep.score,
                0 AS xp_bonus, FALSE AS badge_awarded
            FROM event_participants ep
            JOIN users u ON u.id = ep.user_id
            WHERE ep.event_id = $1
            ORDER BY ep.score DESC, ep.joined_at ASC
            LIMIT $2 OFFSET $3
            """,
            event_id, limit, offset,
        )

    entries = [
        LeaderboardEntry(
            rank=r["rank"],
            user_id=r["user_id"],
            username=r["username"],
            grade=r["grade"],
            score=r["score"],
            xp_bonus=r["xp_bonus"],
            badge_awarded=r["badge_awarded"],
        )
        for r in rows
    ]
    return EventLeaderboardResponse(
        event_id=event_id,
        entries=entries,
        total_participants=total or 0,
    )


# ─────────────────────────────────────────────────────────────────────
# Write operations
# ─────────────────────────────────────────────────────────────────────

async def create_event(
    conn: asyncpg.Connection,
    *,
    title: str,
    description: str,
    xp_multiplier: Decimal,
    badge_reward_id: Optional[str],
    max_participants: Optional[int],
    start_at: datetime,
    end_at: datetime,
    created_by: str,
) -> EventOut:
    """Admin creates a new event in draft status."""
    _assert_in_transaction(conn)
    now = datetime.now(timezone.utc)

    if end_at <= start_at:
        raise ValueError("end_at must be after start_at")
    if (end_at - start_at) > MAX_EVENT_DURATION:
        raise ValueError("Event duration cannot exceed 72 hours")

    if badge_reward_id:
        badge_exists = await conn.fetchval(
            "SELECT 1 FROM badges WHERE id = $1", badge_reward_id
        )
        if not badge_exists:
            raise ValueError(f"Badge '{badge_reward_id}' not found")

    event_id = _new_event_id()
    row = await conn.fetchrow(
        """
        INSERT INTO events
            (id, title, description, status, xp_multiplier, badge_reward_id,
             max_participants, created_by, start_at, end_at, created_at, updated_at)
        VALUES ($1, $2, $3, 'draft', $4, $5, $6, $7, $8, $9, $10, $10)
        RETURNING *
        """,
        event_id, title, description, xp_multiplier, badge_reward_id,
        max_participants, created_by, start_at, end_at, now,
    )

    logger.info("Event %s created by %s", event_id, created_by)
    return _row_to_event_out(row, participant_count=0)


async def update_event(
    conn: asyncpg.Connection,
    *,
    event_id: str,
    admin_id: str,
    updates: dict,
) -> EventOut:
    """Admin updates a draft event."""
    _assert_in_transaction(conn)
    now = datetime.now(timezone.utc)

    event = await conn.fetchrow(
        "SELECT id, status, start_at, end_at, title, description, xp_multiplier, badge_reward_id, max_participants FROM events WHERE id = $1 FOR UPDATE", event_id
    )
    if event is None:
        raise ValueError("Event not found")
    if event["status"] != "draft":
        raise ValueError("Only draft events can be updated")

    allowed_fields = {"title", "description", "xp_multiplier", "badge_reward_id", "max_participants", "start_at", "end_at"}
    filtered = {k: v for k, v in updates.items() if k in allowed_fields and v is not None}

    if not filtered:
        return _row_to_event_out(event, participant_count=0)

    # Validate dates if either changes
    new_start = filtered.get("start_at", event["start_at"])
    new_end = filtered.get("end_at", event["end_at"])
    if new_end <= new_start:
        raise ValueError("end_at must be after start_at")
    if (new_end - new_start) > MAX_EVENT_DURATION:
        raise ValueError("Event duration cannot exceed 72 hours")

    if "badge_reward_id" in filtered and filtered["badge_reward_id"]:
        badge_exists = await conn.fetchval(
            "SELECT 1 FROM badges WHERE id = $1", filtered["badge_reward_id"]
        )
        if not badge_exists:
            raise ValueError(f"Badge '{filtered['badge_reward_id']}' not found")

    set_clauses = [f"{k} = ${i+1}" for i, k in enumerate(filtered.keys())]
    set_clauses.append(f"updated_at = ${len(filtered)+1}")
    values = list(filtered.values()) + [now, event_id]

    row = await conn.fetchrow(
        f"UPDATE events SET {', '.join(set_clauses)} WHERE id = ${len(filtered)+2} RETURNING *",
        *values,
    )

    logger.info("Event %s updated by %s", event_id, admin_id)
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM event_participants WHERE event_id = $1", event_id
    )
    return _row_to_event_out(row, participant_count=count or 0)


async def activate_event(
    conn: asyncpg.Connection,
    *,
    event_id: str,
    admin_id: str = "system",
) -> EventOut:
    """Transition event from draft -> active."""
    _assert_in_transaction(conn)
    now = datetime.now(timezone.utc)

    row = await conn.fetchrow(
        """
        UPDATE events SET status = 'active', updated_at = $1
        WHERE id = $2 AND status = 'draft'
        RETURNING *
        """,
        now, event_id,
    )
    if row is None:
        raise ValueError("Event not found or not in draft status")

    logger.info("Event %s activated by %s", event_id, admin_id)
    return _row_to_event_out(row, participant_count=0)


async def end_event(
    conn: asyncpg.Connection,
    *,
    event_id: str,
) -> EventOut:
    """Transition event from active -> ended."""
    _assert_in_transaction(conn)
    now = datetime.now(timezone.utc)

    row = await conn.fetchrow(
        """
        UPDATE events SET status = 'ended', updated_at = $1
        WHERE id = $2 AND status = 'active'
        RETURNING *
        """,
        now, event_id,
    )
    if row is None:
        raise ValueError("Event not found or not in active status")

    count = await conn.fetchval(
        "SELECT COUNT(*) FROM event_participants WHERE event_id = $1", event_id
    )
    logger.info("Event %s ended", event_id)
    return _row_to_event_out(row, participant_count=count or 0)


async def join_event(
    conn: asyncpg.Connection,
    *,
    event_id: str,
    user_id: str,
) -> EventParticipantOut:
    """Authenticated user joins an active event."""
    _assert_in_transaction(conn)

    event = await conn.fetchrow(
        "SELECT id, status, max_participants FROM events WHERE id = $1 FOR UPDATE",
        event_id,
    )
    if event is None:
        raise ValueError("Event not found")
    if event["status"] != "active":
        raise ValueError("Can only join active events")

    existing = await conn.fetchval(
        "SELECT id FROM event_participants WHERE event_id = $1 AND user_id = $2",
        event_id, user_id,
    )
    if existing:
        raise ValueError("Already joined this event")

    if event["max_participants"]:
        current_count = await conn.fetchval(
            "SELECT COUNT(*) FROM event_participants WHERE event_id = $1", event_id
        )
        if current_count >= event["max_participants"]:
            raise ValueError("Event has reached maximum participants")

    user = await conn.fetchrow(
        "SELECT id, username FROM users WHERE id = $1", user_id
    )
    if user is None:
        raise ValueError("User not found")

    participant_id = _new_participant_id()
    now = datetime.now(timezone.utc)
    row = await conn.fetchrow(
        """
        INSERT INTO event_participants (id, event_id, user_id, score, joined_at)
        VALUES ($1, $2, $3, 0, $4)
        RETURNING *
        """,
        participant_id, event_id, user_id, now,
    )

    logger.info("User %s joined event %s", user_id, event_id)
    return EventParticipantOut(
        id=row["id"],
        event_id=row["event_id"],
        user_id=row["user_id"],
        username=user["username"],
        score=row["score"],
        joined_at=row["joined_at"],
    )


async def submit_score(
    conn: asyncpg.Connection,
    *,
    event_id: str,
    user_id: str,
    score_delta: int,
) -> EventParticipantOut:
    """Add score_delta to participant's current score."""
    _assert_in_transaction(conn)

    event = await conn.fetchrow(
        "SELECT id, status FROM events WHERE id = $1", event_id
    )
    if event is None:
        raise ValueError("Event not found")
    if event["status"] != "active":
        raise ValueError("Scores can only be submitted during active events")

    participant = await conn.fetchrow(
        "SELECT id, score FROM event_participants WHERE event_id = $1 AND user_id = $2 FOR UPDATE",
        event_id, user_id,
    )
    if participant is None:
        raise ValueError("Not a participant of this event")

    new_score = participant["score"] + score_delta
    now = datetime.now(timezone.utc)
    await conn.execute(
        "UPDATE event_participants SET score = $1 WHERE id = $2",
        new_score, participant["id"],
    )

    user = await conn.fetchrow("SELECT username FROM users WHERE id = $1", user_id)

    logger.info("User %s submitted score +%d for event %s (total: %d)", user_id, score_delta, event_id, new_score)
    return EventParticipantOut(
        id=participant["id"],
        event_id=event_id,
        user_id=user_id,
        username=user["username"] if user else "unknown",
        score=new_score,
        joined_at=participant["joined_at"],
    )


async def finalize_event(
    conn: asyncpg.Connection,
    *,
    event_id: str,
) -> dict:
    """Transition event from ended -> finalized.

    Computes leaderboard, awards XP bonuses and badges to top participants.
    """
    _assert_in_transaction(conn)
    now = datetime.now(timezone.utc)

    event = await conn.fetchrow(
        "SELECT id, status, xp_multiplier, badge_reward_id FROM events WHERE id = $1 FOR UPDATE", event_id
    )
    if event is None:
        raise ValueError("Event not found")
    if event["status"] == "finalized":
        return {"already_finalized": True, "event_id": event_id}
    if event["status"] != "ended":
        raise ValueError(f"Event must be ended to finalize, got '{event['status']}'")

    xp_mult = float(event["xp_multiplier"])
    badge_reward_id = event["badge_reward_id"]

    # Get all participants ranked by score
    participants = await conn.fetch(
        """
        SELECT ep.id, ep.user_id, ep.score, u.username, u.xp, u.grade, u.level,
               u.stats_int, u.stats_dex, u.stats_cha, u.stat_points
        FROM event_participants ep
        JOIN users u ON u.id = ep.user_id
        WHERE ep.event_id = $1
        ORDER BY ep.score DESC, ep.joined_at ASC
        """,
        event_id,
    )

    awards_count = 0
    badges_awarded = 0

    for rank_idx, p in enumerate(participants, start=1):
        # Determine XP bonus tier
        base_bonus = _XP_BONUS_TIERS.get(rank_idx)
        if base_bonus is None and rank_idx <= 10:
            base_bonus = _XP_BONUS_TOP10
        elif base_bonus is None:
            base_bonus = 0

        xp_bonus = int(base_bonus * xp_mult) if base_bonus > 0 else 0

        # Award badge to top 3 if configured
        award_badge = bool(badge_reward_id and rank_idx <= 3)
        if award_badge:
            await conn.execute(
                """
                INSERT INTO user_badges (id, user_id, badge_id, earned_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, badge_id) DO NOTHING
                """,
                f"ub_{uuid.uuid4().hex[:14]}", p["user_id"], badge_reward_id, now,
            )
            badges_awarded += 1

        # Insert leaderboard entry
        await conn.execute(
            """
            INSERT INTO event_leaderboard
                (id, event_id, user_id, rank, score, xp_bonus, badge_awarded, computed_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (event_id, user_id) DO NOTHING
            """,
            _new_leaderboard_id(), event_id, p["user_id"], rank_idx,
            p["score"], xp_bonus, award_badge, now,
        )

        # Apply XP bonus to user
        if xp_bonus > 0:
            new_xp = p["xp"] + xp_bonus
            old_level = p["level"]
            grade_enum = GradeEnum(p["grade"])
            level_up, new_grade, new_level, _ = check_level_up(new_xp, grade_enum)
            new_xp_to_next = calculate_xp_to_next(new_xp, new_grade)

            levels_gained = max(0, new_level - old_level)
            stat_delta = allocate_stat_points(levels_gained) if levels_gained > 0 else {"int": 0, "dex": 0, "cha": 0, "unspent": 0}
            new_stats_int = min(STAT_CAP, p["stats_int"] + stat_delta["int"])
            new_stats_dex = min(STAT_CAP, p["stats_dex"] + stat_delta["dex"])
            new_stats_cha = min(STAT_CAP, p["stats_cha"] + stat_delta["cha"])

            await conn.execute(
                """
                UPDATE users
                SET xp = $1, level = $2, grade = $3, xp_to_next = $4,
                    stats_int = $5, stats_dex = $6, stats_cha = $7,
                    stat_points = stat_points + $8,
                    updated_at = $9
                WHERE id = $10
                """,
                new_xp, new_level, new_grade.value, new_xp_to_next,
                new_stats_int, new_stats_dex, new_stats_cha,
                stat_delta["unspent"], now, p["user_id"],
            )
            awards_count += 1

        # Notify top-10 participants
        if rank_idx <= 10 and xp_bonus > 0:
            badge_text = " + бейдж!" if award_badge else ""
            await notification_service.create_notification(
                conn,
                user_id=p["user_id"],
                title=f"Ивент «{event['title']}» завершён!",
                message=f"Вы заняли {rank_idx}-е место и получили +{xp_bonus} XP{badge_text}",
                event_type="event_finalized",
            )

    # Update event status
    await conn.execute(
        "UPDATE events SET status = 'finalized', finalized_at = $1, updated_at = $1 WHERE id = $2",
        now, event_id,
    )

    logger.info(
        "Event %s finalized: %d participants, %d XP awards, %d badges",
        event_id, len(participants), awards_count, badges_awarded,
    )
    return {
        "event_id": event_id,
        "participants": len(participants),
        "xp_awards": awards_count,
        "badges_awarded": badges_awarded,
    }


# ─────────────────────────────────────────────────────────────────────
# Scheduler helpers
# ─────────────────────────────────────────────────────────────────────

async def auto_activate_due_events(conn: asyncpg.Connection) -> int:
    """Activate all draft events whose start_at <= now. Returns count activated."""
    now = datetime.now(timezone.utc)
    result = await conn.execute(
        "UPDATE events SET status = 'active', updated_at = $1 WHERE status = 'draft' AND start_at <= $1",
        now,
    )
    count = int(result.split()[-1]) if result else 0
    if count > 0:
        logger.info("Auto-activated %d events", count)
    return count


async def auto_end_due_events(conn: asyncpg.Connection) -> int:
    """End all active events whose end_at <= now. Returns count ended."""
    now = datetime.now(timezone.utc)
    result = await conn.execute(
        "UPDATE events SET status = 'ended', updated_at = $1 WHERE status = 'active' AND end_at <= $1",
        now,
    )
    count = int(result.split()[-1]) if result else 0
    if count > 0:
        logger.info("Auto-ended %d events", count)
    return count
