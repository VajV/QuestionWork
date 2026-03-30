"""Trust score calculation and cache refresh helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

import asyncpg


TRUST_SCORE_PRECISION = Decimal("0.0001")
GRADE_LEVEL_BONUS = {
    "novice": 0.0,
    "junior": 0.25,
    "middle": 0.5,
    "senior": 1.0,
}
ACCEPTED_STATUSES = (
    "assigned",
    "in_progress",
    "completed",
    "revision_requested",
    "confirmed",
    "cancelled",
    "disputed",
)
CONFIRMED_STATUS = "confirmed"


def _clamp_01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _round_score(score: float) -> float:
    return float(Decimal(str(score)).quantize(TRUST_SCORE_PRECISION, rounding=ROUND_HALF_UP))


def _normalize_count(raw_value: Any) -> int:
    return max(0, int(raw_value or 0))


def normalize_rating(avg_rating_5: Optional[float]) -> float:
    if avg_rating_5 is None:
        return 0.0
    return _clamp_01(float(avg_rating_5) / 5.0)


def grade_to_level_bonus(grade: Any) -> float:
    if grade is None:
        return 0.0
    normalized_grade = str(getattr(grade, "value", grade)).strip().lower()
    return GRADE_LEVEL_BONUS.get(normalized_grade, 0.0)


def build_trust_breakdown(
    *,
    avg_rating_5: Optional[float],
    accepted_quests: int,
    confirmed_quests: int,
    on_time_quests: int,
    grade: Any,
) -> dict[str, Any]:
    normalized_rating = normalize_rating(avg_rating_5)
    normalized_accepted = _normalize_count(accepted_quests)
    normalized_confirmed = _normalize_count(confirmed_quests)
    normalized_on_time = _normalize_count(on_time_quests)
    normalized_grade = str(getattr(grade, "value", grade)).strip().lower() if grade is not None else "novice"

    completion_rate = _clamp_01(
        normalized_confirmed / normalized_accepted if normalized_accepted > 0 else 0.0
    )
    on_time_rate = _clamp_01(
        normalized_on_time / normalized_confirmed if normalized_confirmed > 0 else 0.0
    )
    level_bonus = grade_to_level_bonus(normalized_grade)

    return {
        "avg_rating": _round_score(normalized_rating),
        "completion_rate": _round_score(completion_rate),
        "on_time_rate": _round_score(on_time_rate),
        "level_bonus": _round_score(level_bonus),
        "raw": {
            "average_rating_5": float(avg_rating_5) if avg_rating_5 is not None else 0.0,
            "accepted_quests": normalized_accepted,
            "confirmed_quests": normalized_confirmed,
            "on_time_quests": normalized_on_time,
            "grade": normalized_grade,
        },
    }


def calculate_trust_score(
    *,
    avg_rating_5: Optional[float],
    accepted_quests: int,
    confirmed_quests: int,
    on_time_quests: int,
    grade: Any,
) -> tuple[float, dict[str, Any]]:
    breakdown = build_trust_breakdown(
        avg_rating_5=avg_rating_5,
        accepted_quests=accepted_quests,
        confirmed_quests=confirmed_quests,
        on_time_quests=on_time_quests,
        grade=grade,
    )
    score = (
        breakdown["avg_rating"] * 0.4
        + breakdown["completion_rate"] * 0.3
        + breakdown["on_time_rate"] * 0.2
        + breakdown["level_bonus"] * 0.1
    )
    return _round_score(_clamp_01(score)), breakdown


def _default_breakdown(grade: Any = "novice") -> dict[str, Any]:
    return build_trust_breakdown(
        avg_rating_5=None,
        accepted_quests=0,
        confirmed_quests=0,
        on_time_quests=0,
        grade=grade,
    )


async def fetch_trust_inputs(conn: asyncpg.Connection, user_id: str) -> Optional[dict[str, Any]]:
    profile_row = await conn.fetchrow(
        """
        SELECT id, avg_rating, review_count, grade
        FROM users
        WHERE id = $1
        """,
        user_id,
    )
    if not profile_row:
        return None

    counter_row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status::text = ANY($2::text[]))::INT AS accepted_quests,
            COUNT(*) FILTER (WHERE status::text = $3)::INT AS confirmed_quests,
            COUNT(*) FILTER (
                WHERE status::text = $3
                  AND deadline IS NOT NULL
                  AND COALESCE(delivery_submitted_at, completed_at) IS NOT NULL
                  AND COALESCE(delivery_submitted_at, completed_at) <= deadline
            )::INT AS on_time_quests
        FROM quests
        WHERE assigned_to = $1
        """,
        user_id,
        list(ACCEPTED_STATUSES),
        CONFIRMED_STATUS,
    )

    return {
        "user_id": profile_row["id"],
        "avg_rating_5": float(profile_row["avg_rating"]) if profile_row["avg_rating"] is not None else None,
        "review_count": int(profile_row["review_count"] or 0),
        "grade": profile_row["grade"],
        "accepted_quests": int(counter_row["accepted_quests"] or 0) if counter_row else 0,
        "confirmed_quests": int(counter_row["confirmed_quests"] or 0) if counter_row else 0,
        "on_time_quests": int(counter_row["on_time_quests"] or 0) if counter_row else 0,
    }


async def refresh_trust_score(conn: asyncpg.Connection, user_id: str) -> Optional[dict[str, Any]]:
    inputs = await fetch_trust_inputs(conn, user_id)
    if not inputs:
        return None

    score, breakdown = calculate_trust_score(
        avg_rating_5=inputs["avg_rating_5"],
        accepted_quests=inputs["accepted_quests"],
        confirmed_quests=inputs["confirmed_quests"],
        on_time_quests=inputs["on_time_quests"],
        grade=inputs["grade"],
    )
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        UPDATE users
        SET trust_score = $1,
            trust_score_breakdown = $2::jsonb,
            trust_score_updated_at = $3,
            updated_at = $3
        WHERE id = $4
        """,
        Decimal(str(score)).quantize(TRUST_SCORE_PRECISION, rounding=ROUND_HALF_UP),
        json.dumps(breakdown),
        now,
        user_id,
    )

    return {
        "user_id": user_id,
        "trust_score": score,
        "breakdown": breakdown,
        "updated_at": now,
    }


async def get_cached_trust_score(conn: asyncpg.Connection, user_id: str) -> Optional[dict[str, Any]]:
    row = await conn.fetchrow(
        """
        SELECT id, grade, trust_score, trust_score_breakdown, trust_score_updated_at
        FROM users
        WHERE id = $1
        """,
        user_id,
    )
    if not row:
        return None

    raw_breakdown = row["trust_score_breakdown"] or {}
    if isinstance(raw_breakdown, str):
        raw_breakdown = json.loads(raw_breakdown)
    breakdown = _default_breakdown(row["grade"])
    if isinstance(raw_breakdown, dict):
        breakdown.update({k: raw_breakdown.get(k, breakdown[k]) for k in ("avg_rating", "completion_rate", "on_time_rate", "level_bonus")})
        raw_values = breakdown["raw"].copy()
        if isinstance(raw_breakdown.get("raw"), dict):
            raw_values.update(raw_breakdown["raw"])
        breakdown["raw"] = raw_values

    score = float(row["trust_score"]) if row["trust_score"] is not None else 0.0
    return {
        "user_id": row["id"],
        "trust_score": _round_score(score),
        "breakdown": breakdown,
        "updated_at": row["trust_score_updated_at"],
    }