"""Guild seasonal XP progression and tier helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

from app.core.cache import redis_cache, invalidate_cache_scope


TIER_THRESHOLDS: tuple[tuple[str, int], ...] = (
    ("bronze", 0),
    ("silver", 5000),
    ("gold", 20000),
    ("platinum", 50000),
)
TIER_ORDER = {tier: index for index, (tier, _) in enumerate(TIER_THRESHOLDS)}
TIER_THRESHOLD_MAP = dict(TIER_THRESHOLDS)


def _assert_in_transaction(conn: asyncpg.Connection) -> None:
    if not conn.is_in_transaction():
        raise RuntimeError("Guild progression mutations must run inside a DB transaction")


def get_current_season_code(now: Optional[datetime] = None) -> str:
    timestamp = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    season_half = 1 if timestamp.month <= 6 else 2
    return f"{timestamp.year}-S{season_half}"


def calculate_guild_xp_delta(xp_reward: int) -> int:
    return max(0, int(xp_reward or 0))


def resolve_tier(seasonal_xp: int) -> str:
    xp = max(0, int(seasonal_xp or 0))
    current = "bronze"
    for tier, threshold in TIER_THRESHOLDS:
        if xp >= threshold:
            current = tier
    return current


def get_tier_benefits(tier: str) -> list[str]:
    if tier == "silver":
        return ["+5% XP"]
    if tier == "gold":
        return ["+10% XP", "exclusive badges"]
    if tier == "platinum":
        return ["+15% XP", "exclusive badges", "unique title"]
    return ["+0% XP"]


def get_xp_bonus_percent(tier: str) -> int:
    if tier == "silver":
        return 5
    if tier == "gold":
        return 10
    if tier == "platinum":
        return 15
    return 0


def get_next_tier(tier: str) -> tuple[Optional[str], Optional[int]]:
    next_index = TIER_ORDER[tier] + 1
    if next_index >= len(TIER_THRESHOLDS):
        return None, None
    next_tier, next_threshold = TIER_THRESHOLDS[next_index]
    return next_tier, next_threshold


def build_empty_progress_state(season_code: Optional[str] = None) -> dict[str, Any]:
    active_season = season_code or get_current_season_code()
    next_tier, next_tier_xp = get_next_tier("bronze")
    return {
        "season_code": active_season,
        "seasonal_xp": 0,
        "current_tier": "bronze",
        "next_tier": next_tier,
        "next_tier_xp": next_tier_xp,
        "xp_to_next_tier": int(next_tier_xp or 0),
        "progress_percent": 0,
        "xp_bonus_percent": 0,
        "tier_benefits": get_tier_benefits("bronze"),
        "season_rank": None,
    }


def _build_progress_state(*, season_code: str, seasonal_xp: int, current_tier: str, season_rank: Optional[int]) -> dict[str, Any]:
    next_tier, next_tier_xp = get_next_tier(current_tier)
    current_threshold = TIER_THRESHOLD_MAP[current_tier]
    xp_to_next_tier = 0 if next_tier_xp is None else max(0, next_tier_xp - seasonal_xp)
    if next_tier_xp is None:
        progress_percent = 100
    else:
        segment = max(1, next_tier_xp - current_threshold)
        gained = max(0, min(segment, seasonal_xp - current_threshold))
        progress_percent = int((gained / segment) * 100)

    return {
        "season_code": season_code,
        "seasonal_xp": seasonal_xp,
        "current_tier": current_tier,
        "next_tier": next_tier,
        "next_tier_xp": next_tier_xp,
        "xp_to_next_tier": xp_to_next_tier,
        "progress_percent": progress_percent,
        "xp_bonus_percent": get_xp_bonus_percent(current_tier),
        "tier_benefits": get_tier_benefits(current_tier),
        "season_rank": season_rank,
    }


async def _fetch_season_rank(conn: asyncpg.Connection, *, guild_id: str, season_code: str, seasonal_xp: int) -> int:
    return int(
        await conn.fetchval(
            """
            SELECT COUNT(*)::INT + 1
            FROM guild_season_progress
            WHERE season_code = $1
              AND (
                seasonal_xp > $2
                OR (seasonal_xp = $2 AND guild_id < $3)
              )
            """,
            season_code,
            seasonal_xp,
            guild_id,
        )
        or 1
    )


async def _record_progress_activity(
    conn: asyncpg.Connection,
    *,
    guild_id: str,
    event_type: str,
    summary: str,
    payload: dict[str, Any],
    user_id: Optional[str] = None,
    quest_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> None:
    activity_id = f"gact_{uuid.uuid4().hex[:12]}"
    timestamp = created_at or datetime.now(timezone.utc)
    await conn.execute(
        """
        INSERT INTO guild_activity (
            id, guild_id, user_id, quest_id, event_type, summary, payload,
            treasury_delta, guild_tokens_delta, contribution_delta, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 0, 0, 0, $8)
        """,
        activity_id,
        guild_id,
        user_id,
        quest_id,
        event_type,
        summary,
        json.dumps(payload),
        timestamp,
    )


@redis_cache(ttl_seconds=60, key_prefix="guild_progress", scope_builder=lambda conn, guild_id, season_code=None: f"guild:{guild_id}")
async def get_guild_progress_state(
    conn: asyncpg.Connection,
    guild_id: str,
    *,
    season_code: Optional[str] = None,
) -> dict[str, Any]:
    active_season = season_code or get_current_season_code()
    row = await conn.fetchrow(
        """
        SELECT season_code, seasonal_xp, current_tier
        FROM guild_season_progress
        WHERE guild_id = $1 AND season_code = $2
        """,
        guild_id,
        active_season,
    )
    if not row:
        return build_empty_progress_state(active_season)

    seasonal_xp = int(row["seasonal_xp"] or 0)
    season_rank = await _fetch_season_rank(
        conn,
        guild_id=guild_id,
        season_code=active_season,
        seasonal_xp=seasonal_xp,
    )
    return _build_progress_state(
        season_code=active_season,
        seasonal_xp=seasonal_xp,
        current_tier=str(row["current_tier"] or "bronze"),
        season_rank=season_rank,
    )


async def apply_guild_xp_gain(
    conn: asyncpg.Connection,
    *,
    guild_id: str,
    xp_gain: int,
    source: str,
    user_id: Optional[str] = None,
    quest_id: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
) -> dict[str, Any]:
    _assert_in_transaction(conn)

    xp_delta = calculate_guild_xp_delta(xp_gain)
    timestamp = occurred_at or datetime.now(timezone.utc)
    season_code = get_current_season_code(timestamp)
    row = await conn.fetchrow(
        """
        SELECT id, seasonal_xp, current_tier
        FROM guild_season_progress
        WHERE guild_id = $1 AND season_code = $2
        FOR UPDATE
        """,
        guild_id,
        season_code,
    )

    previous_xp = int(row["seasonal_xp"] or 0) if row else 0
    previous_tier = str(row["current_tier"] or "bronze") if row else "bronze"
    seasonal_xp = previous_xp + xp_delta
    current_tier = resolve_tier(seasonal_xp)
    promoted = TIER_ORDER[current_tier] > TIER_ORDER[previous_tier]

    if row:
        await conn.execute(
            """
            UPDATE guild_season_progress
            SET seasonal_xp = $1,
                current_tier = $2,
                last_tier_change_at = CASE WHEN $3 THEN $4 ELSE last_tier_change_at END,
                updated_at = $4
            WHERE id = $5
            """,
            seasonal_xp,
            current_tier,
            promoted,
            timestamp,
            row["id"],
        )
    else:
        await conn.execute(
            """
            INSERT INTO guild_season_progress (
                id, guild_id, season_code, seasonal_xp, current_tier,
                last_tier_change_at, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $6, $6)
            """,
            f"gsp_{uuid.uuid4().hex[:12]}",
            guild_id,
            season_code,
            seasonal_xp,
            current_tier,
            timestamp if promoted else None,
        )

    if xp_delta > 0:
        await _record_progress_activity(
            conn,
            guild_id=guild_id,
            event_type="guild_xp_awarded",
            summary=f"Guild gained +{xp_delta} seasonal XP in {season_code}.",
            payload={
                "source": source,
                "season_code": season_code,
                "xp_gain": xp_delta,
                "seasonal_xp": seasonal_xp,
                "current_tier": current_tier,
            },
            user_id=user_id,
            quest_id=quest_id,
            created_at=timestamp,
        )

    if promoted:
        await _record_progress_activity(
            conn,
            guild_id=guild_id,
            event_type="guild_tier_promoted",
            summary=f"Guild tier advanced from {previous_tier} to {current_tier} in {season_code}.",
            payload={
                "source": source,
                "season_code": season_code,
                "previous_tier": previous_tier,
                "current_tier": current_tier,
                "seasonal_xp": seasonal_xp,
            },
            user_id=user_id,
            quest_id=quest_id,
            created_at=timestamp,
        )

    season_rank = await _fetch_season_rank(
        conn,
        guild_id=guild_id,
        season_code=season_code,
        seasonal_xp=seasonal_xp,
    )
    await invalidate_cache_scope("guild_progress", "guild", guild_id)
    return {
        **_build_progress_state(
            season_code=season_code,
            seasonal_xp=seasonal_xp,
            current_tier=current_tier,
            season_rank=season_rank,
        ),
        "guild_id": guild_id,
        "xp_gain": xp_delta,
        "previous_tier": previous_tier,
        "promoted": promoted,
    }


async def recalculate_guild_progress(
    conn: asyncpg.Connection,
    guild_id: str,
    *,
    season_code: Optional[str] = None,
) -> dict[str, Any]:
    _assert_in_transaction(conn)

    active_season = season_code or get_current_season_code()
    seasonal_xp = int(
        await conn.fetchval(
            """
            SELECT COALESCE(SUM((payload->>'xp_gain')::INT), 0)::INT
            FROM guild_activity
            WHERE guild_id = $1
              AND event_type = 'guild_xp_awarded'
              AND payload->>'season_code' = $2
            """,
            guild_id,
            active_season,
        )
        or 0
    )
    current_tier = resolve_tier(seasonal_xp)
    row = await conn.fetchrow(
        "SELECT id FROM guild_season_progress WHERE guild_id = $1 AND season_code = $2 FOR UPDATE",
        guild_id,
        active_season,
    )
    timestamp = datetime.now(timezone.utc)
    if row:
        await conn.execute(
            """
            UPDATE guild_season_progress
            SET seasonal_xp = $1,
                current_tier = $2,
                updated_at = $3,
                last_tier_change_at = CASE WHEN current_tier <> $2 THEN $3 ELSE last_tier_change_at END
            WHERE id = $4
            """,
            seasonal_xp,
            current_tier,
            timestamp,
            row["id"],
        )
    else:
        await conn.execute(
            """
            INSERT INTO guild_season_progress (
                id, guild_id, season_code, seasonal_xp, current_tier, last_tier_change_at, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, NULL, $6, $6)
            """,
            f"gsp_{uuid.uuid4().hex[:12]}",
            guild_id,
            active_season,
            seasonal_xp,
            current_tier,
            timestamp,
        )

    season_rank = await _fetch_season_rank(
        conn,
        guild_id=guild_id,
        season_code=active_season,
        seasonal_xp=seasonal_xp,
    )
    return _build_progress_state(
        season_code=active_season,
        seasonal_xp=seasonal_xp,
        current_tier=current_tier,
        season_rank=season_rank,
    )


# ---------------------------------------------------------------------------
# Guild milestones — shared progression markers unlocked by seasonal XP
# ---------------------------------------------------------------------------

GUILD_MILESTONES: tuple[tuple[str, str, str, int, str], ...] = (
    ("first_spark", "First Spark", "Guild started its seasonal journey.", 100, "The guild flame ignites"),
    ("bronze_foundation", "Bronze Foundation", "Guild reached 1 000 seasonal XP.", 1_000, "+2% treasury bonus for the season"),
    ("rising_force", "Rising Force", "Guild crossed the 3 000 XP mark.", 3_000, "Unlock guild emblem glow"),
    ("silver_threshold", "Silver Threshold", "Guild earned 5 000 XP — Silver tier unlocked.", 5_000, "Silver tier perks activated"),
    ("battle_hardened", "Battle-Hardened", "Guild accumulated 10 000 seasonal XP.", 10_000, "+1 guild token per quest"),
    ("golden_ascent", "Golden Ascent", "Guild crossed 20 000 XP — Gold tier reached.", 20_000, "Gold tier perks activated"),
    ("elite_corps", "Elite Corps", "Guild amassed 35 000 seasonal XP.", 35_000, "Exclusive seasonal badge"),
    ("platinum_legend", "Platinum Legend", "Guild earned 50 000 XP — Platinum tier achieved.", 50_000, "Platinum tier perks + unique title"),
)


def calculate_milestone_state(seasonal_xp: int) -> list[dict[str, Any]]:
    """Return the full milestone list with unlock status for a given XP value."""
    result: list[dict[str, Any]] = []
    for code, label, description, threshold, reward_desc in GUILD_MILESTONES:
        result.append({
            "milestone_code": code,
            "label": label,
            "description": description,
            "threshold_xp": threshold,
            "unlocked": seasonal_xp >= threshold,
            "unlocked_at": None,
            "reward_description": reward_desc,
        })
    return result


async def get_guild_milestones(
    conn: asyncpg.Connection,
    guild_id: str,
    *,
    season_code: Optional[str] = None,
    seasonal_xp: int = 0,
) -> list[dict[str, Any]]:
    """Fetch persisted milestones and merge with static definitions."""
    active_season = season_code or get_current_season_code()
    rows = await conn.fetch(
        """
        SELECT milestone_code, unlocked_at
        FROM guild_milestones
        WHERE guild_id = $1 AND season_code = $2
        """,
        guild_id,
        active_season,
    )
    unlocked_map: dict[str, datetime] = {
        row["milestone_code"]: row["unlocked_at"] for row in rows
    }
    result: list[dict[str, Any]] = []
    for code, label, description, threshold, reward_desc in GUILD_MILESTONES:
        unlocked_at = unlocked_map.get(code)
        result.append({
            "milestone_code": code,
            "label": label,
            "description": description,
            "threshold_xp": threshold,
            "unlocked": unlocked_at is not None or seasonal_xp >= threshold,
            "unlocked_at": unlocked_at.isoformat() if unlocked_at else None,
            "reward_description": reward_desc,
        })
    return result


async def check_and_unlock_milestones(
    conn: asyncpg.Connection,
    *,
    guild_id: str,
    seasonal_xp: int,
    season_code: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Persist any newly crossed milestone thresholds. Returns list of newly unlocked milestones."""
    _assert_in_transaction(conn)

    active_season = season_code or get_current_season_code()
    timestamp = occurred_at or datetime.now(timezone.utc)

    existing = await conn.fetch(
        "SELECT milestone_code FROM guild_milestones WHERE guild_id = $1 AND season_code = $2",
        guild_id,
        active_season,
    )
    existing_codes = {row["milestone_code"] for row in existing}

    newly_unlocked: list[dict[str, Any]] = []
    for code, label, description, threshold, reward_desc in GUILD_MILESTONES:
        if seasonal_xp >= threshold and code not in existing_codes:
            milestone_id = f"gml_{uuid.uuid4().hex[:12]}"
            await conn.execute(
                """
                INSERT INTO guild_milestones (id, guild_id, season_code, milestone_code, label, threshold_xp, unlocked_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT ON CONSTRAINT uq_guild_milestones_guild_season_code DO NOTHING
                """,
                milestone_id,
                guild_id,
                active_season,
                code,
                label,
                threshold,
                timestamp,
            )
            newly_unlocked.append({
                "milestone_code": code,
                "label": label,
                "description": description,
                "threshold_xp": threshold,
                "reward_description": reward_desc,
            })

    if newly_unlocked:
        summary_parts = [m["label"] for m in newly_unlocked]
        await _record_progress_activity(
            conn,
            guild_id=guild_id,
            event_type="guild_milestone_unlocked",
            summary=f"Guild unlocked milestone(s): {', '.join(summary_parts)}.",
            payload={
                "season_code": active_season,
                "milestones": [m["milestone_code"] for m in newly_unlocked],
                "seasonal_xp": seasonal_xp,
            },
            created_at=timestamp,
        )

    return newly_unlocked