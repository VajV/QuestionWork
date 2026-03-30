"""Services for the public talent market and basic guild lifecycle."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import math
import re
import uuid

import asyncpg

from app.models.marketplace import GuildCreateRequest
from app.models.user import UserProfile, UserStats, GradeEnum
from app.core.otel_utils import db_span
from app.core.cache import redis_cache, invalidate_cache_scope
from app.services import guild_card_service, guild_economy_service, guild_progression_service


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")
    return slug[:48] or f"guild-{uuid.uuid4().hex[:8]}"


def _to_stats(row: asyncpg.Record | dict) -> UserStats:
    return UserStats(
        int=int(row["stats_int"] or 10),
        dex=int(row["stats_dex"] or 10),
        cha=int(row["stats_cha"] or 10),
    )


def _to_decimal_string(value: Decimal | int | float | None) -> str:
    if value is None:
        return "0.00"
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return f"{Decimal(str(value)):.2f}"


def _member_rank_score(row: asyncpg.Record | dict) -> int:
    xp = int(row.get("xp", 0) if isinstance(row, dict) else row["xp"] or 0)
    level = int(row.get("level", 1) if isinstance(row, dict) else row["level"] or 1)
    avg_rating_raw = row.get("avg_rating") if isinstance(row, dict) else row["avg_rating"]
    avg_rating = float(avg_rating_raw) if avg_rating_raw is not None else 0.0
    review_count = int(row.get("review_count", 0) if isinstance(row, dict) else row["review_count"] or 0)
    guild_rating = int(row.get("guild_rating", 0) if isinstance(row, dict) else row["guild_rating"] or 0)
    return int(xp + level * 120 + avg_rating * 90 + review_count * 12 + guild_rating * 0.2)


def _compute_rank_signals(row: dict, guild_card: dict | None) -> list[str]:
    """Generate human-readable ranking explanations."""
    signals: list[str] = []
    avg_rating_raw = row.get("avg_rating")
    avg_rating = float(avg_rating_raw) if avg_rating_raw is not None else 0.0
    review_count = int(row.get("review_count") or 0)
    level = int(row.get("level") or 1)
    grade = str(row.get("grade") or "novice")

    if avg_rating >= 4.5 and review_count >= 3:
        signals.append("Высокий рейтинг")
    elif avg_rating >= 3.5 and review_count >= 1:
        signals.append("Хороший рейтинг")

    if review_count >= 10:
        signals.append("Много отзывов")
    elif review_count >= 3:
        signals.append("Подтверждённый опыт")

    if grade in ("senior", "middle"):
        signals.append("Сильный подтверждённый опыт")
    elif grade == "junior" and level >= 8:
        signals.append("Растущий специалист")

    if guild_card and int(guild_card.get("rating") or 0) > 500:
        signals.append("Сильная гильдия")

    if not signals:
        signals.append("Новый участник")

    return signals


def _budget_band(avg_budget: Decimal | int | float | None) -> str | None:
    if avg_budget is None:
        return None
    value = Decimal(str(avg_budget))
    if value < Decimal("15000"):
        return "up_to_15k"
    if value < Decimal("50000"):
        return "15k_to_50k"
    if value < Decimal("150000"):
        return "50k_to_150k"
    return "150k_plus"


def _response_time_hint(active_quest_count: int, review_count: int, confirmed_count: int) -> str:
    if active_quest_count >= 2:
        return "Сейчас сфокусирован на активных задачах"
    if active_quest_count == 1:
        return "Обычно отвечает выборочно из-за текущей загрузки"
    if confirmed_count >= 6 or review_count >= 6:
        return "Обычно отвечает в течение рабочего дня"
    if confirmed_count >= 2 or review_count >= 2:
        return "Недавно активен, ответ обычно не затягивается"
    return "Нужна первая подтверждённая история отклика"


def _guild_rating(card: dict) -> int:
    total_xp = int(card.get("total_xp") or 0)
    avg_rating = float(card.get("avg_rating") or 0.0)
    confirmed_quests = int(card.get("confirmed_quests") or 0)
    member_count = int(card.get("member_count") or 0)
    return int(math.sqrt(max(total_xp, 0)) * 14 + avg_rating * 160 + confirmed_quests * 18 + member_count * 20)


def _build_guild_leaderboard(
    members: list[dict[str, object]],
    trophies: list[dict[str, object]],
) -> list[dict[str, object]]:
    trophy_counts: dict[str, int] = {}
    family_counts: dict[str, Counter[str]] = {}

    for trophy in trophies:
        member_id = str(trophy.get("awarded_to_user_id") or "").strip()
        family = str(trophy.get("family") or "").strip()
        if not member_id:
            continue

        trophy_counts[member_id] = trophy_counts.get(member_id, 0) + 1
        if family:
            member_families = family_counts.setdefault(member_id, Counter())
            member_families[family] += 1

    ranked_members = sorted(
        members,
        key=lambda member: (
            -int(member.get("contribution") or 0),
            -int(member.get("level") or 1),
            str(member.get("username") or ""),
        ),
    )[:6]

    leaderboard: list[dict[str, object]] = []
    for index, member in enumerate(ranked_members, start=1):
        member_id = str(member.get("id") or "")
        member_families = family_counts.get(member_id)
        family_label = None
        if member_families:
            family_label = sorted(
                member_families.items(),
                key=lambda item: (-item[1], item[0]),
            )[0][0]

        leaderboard.append(
            {
                "rank": index,
                "member": member,
                "trophy_count": trophy_counts.get(member_id, 0),
                "family_label": family_label,
            }
        )

    return leaderboard


def build_guild_progression_snapshot(
    members: list[dict[str, object]],
    trophies: list[dict[str, object]],
    seasonal_sets: list[dict[str, object]],
    *,
    progress_state: dict[str, object] | None = None,
    milestones: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    state = progress_state or guild_progression_service.build_empty_progress_state()
    top_contributors = _build_top_contributors(members)
    return {
        "season_code": str(state["season_code"]),
        "seasonal_xp": int(state["seasonal_xp"]),
        "current_tier": str(state["current_tier"]),
        "next_tier": state["next_tier"],
        "next_tier_xp": state["next_tier_xp"],
        "xp_to_next_tier": int(state["xp_to_next_tier"]),
        "progress_percent": int(state["progress_percent"]),
        "xp_bonus_percent": int(state["xp_bonus_percent"]),
        "tier_benefits": list(state["tier_benefits"]),
        "season_rank": state["season_rank"],
        "completed_sets": sum(1 for item in seasonal_sets if bool(item.get("completed"))),
        "total_sets": len(seasonal_sets),
        "claimed_rewards": sum(1 for item in seasonal_sets if bool(item.get("reward_claimed"))),
        "leaderboard": _build_guild_leaderboard(members, trophies),
        "milestones": milestones or guild_progression_service.calculate_milestone_state(
            int(state.get("seasonal_xp") or 0),
        ),
        "top_contributors": top_contributors,
    }


def _build_top_contributors(members: list[dict[str, object]]) -> list[dict[str, object]]:
    """Rank members by contribution and return a concise summary list (top 10)."""
    ranked = sorted(
        members,
        key=lambda m: (
            -int(m.get("contribution") or 0),
            -int(m.get("level") or 1),
            str(m.get("username") or ""),
        ),
    )[:10]
    return [
        {
            "user_id": str(m.get("id") or ""),
            "username": str(m.get("username") or ""),
            "contribution": int(m.get("contribution") or 0),
            "quests_completed": 0,  # enriched by caller when available
            "role": str(m.get("role") or "member"),
            "rank": idx,
        }
        for idx, m in enumerate(ranked, start=1)
    ]


async def list_guild_cards(conn: asyncpg.Connection) -> list[dict]:
    query = """
        SELECT
            g.id,
            g.name,
            g.slug,
            g.description,
            g.emblem,
            g.member_limit,
            g.treasury_balance,
            g.guild_tokens,
            COUNT(gm.user_id)::INT AS member_count,
            COALESCE(SUM(u.xp), 0)::INT AS total_xp,
            AVG(u.avg_rating)::NUMERIC(3, 2) AS avg_rating,
            COALESCE((
                SELECT COUNT(*)::INT
                FROM quests q
                WHERE q.assigned_to IN (
                    SELECT user_id FROM guild_members
                    WHERE guild_id = g.id AND status = 'active'
                )
                AND q.status = 'confirmed'
            ), 0) AS confirmed_quests,
            (
                SELECT u2.username
                FROM guild_members gm2
                JOIN users u2 ON u2.id = gm2.user_id
                WHERE gm2.guild_id = g.id AND gm2.role = 'leader' AND gm2.status = 'active'
                ORDER BY gm2.joined_at ASC
                LIMIT 1
            ) AS leader_username,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT skill.value) FILTER (WHERE skill.value IS NOT NULL), NULL) AS top_skills
        FROM guilds g
        LEFT JOIN guild_members gm
          ON gm.guild_id = g.id AND gm.status = 'active'
        LEFT JOIN users u
          ON u.id = gm.user_id
        LEFT JOIN LATERAL jsonb_array_elements_text(COALESCE(u.skills, '[]'::jsonb)) AS skill(value) ON TRUE
        WHERE g.is_public = TRUE
        GROUP BY g.id
        ORDER BY g.created_at ASC
    """
    with db_span("db.fetch", query=query, params=[]):
        rows = await conn.fetch(query)

    cards = []
    for row in rows:
        skill_counts = Counter(list(row["top_skills"] or []))
        top_skills = [skill for skill, _ in skill_counts.most_common(4)]
        card = {
            "id": row["id"],
            "name": row["name"],
            "slug": row["slug"],
            "description": row["description"],
            "emblem": row["emblem"],
            "member_count": int(row["member_count"] or 0),
            "member_limit": int(row["member_limit"] or 20),
            "total_xp": int(row["total_xp"] or 0),
            "avg_rating": round(float(row["avg_rating"]), 2) if row["avg_rating"] is not None else None,
            "confirmed_quests": int(row["confirmed_quests"] or 0),
            "treasury_balance": _to_decimal_string(row["treasury_balance"]),
            "guild_tokens": int(row["guild_tokens"] or 0),
            "top_skills": top_skills,
            "leader_username": row["leader_username"],
        }
        card["rating"] = _guild_rating(card)
        cards.append(card)

    cards.sort(key=lambda item: (-item["rating"], -item["total_xp"], item["name"]))
    for index, card in enumerate(cards, start=1):
        card["season_position"] = index
    return cards


@redis_cache(ttl_seconds=60, key_prefix="guild_card", scope_builder=lambda conn, guild_slug: f"slug:{guild_slug}")
async def get_guild_public_profile(conn: asyncpg.Connection, guild_slug: str) -> dict:
    guild_cards = await list_guild_cards(conn)
    guild = next((card for card in guild_cards if card["slug"] == guild_slug), None)
    if not guild:
        raise ValueError("Guild not found")

    member_query = """
        SELECT
            u.id,
            u.username,
            u.level,
            u.grade,
            u.xp,
            u.xp_to_next,
            u.stats_int,
            u.stats_dex,
            u.stats_cha,
            u.skills,
            u.avg_rating,
            u.review_count,
            u.character_class,
            gm.role,
            gm.contribution,
            gm.joined_at
        FROM guild_members gm
        JOIN users u ON u.id = gm.user_id
        WHERE gm.guild_id = $1 AND gm.status = 'active'
        ORDER BY
            CASE gm.role WHEN 'leader' THEN 0 WHEN 'officer' THEN 1 ELSE 2 END,
            gm.contribution DESC,
            u.xp DESC,
            gm.joined_at ASC
    """
    with db_span("db.fetch", query=member_query, params=[guild["id"]]):
        member_rows = await conn.fetch(member_query, guild["id"])

    activity_query = """
        SELECT
            ga.id,
            ga.event_type,
            ga.summary,
            ga.user_id,
            actor.username AS actor_username,
            ga.quest_id,
            ga.treasury_delta,
            ga.guild_tokens_delta,
            ga.contribution_delta,
            ga.created_at
        FROM guild_activity ga
        LEFT JOIN users actor ON actor.id = ga.user_id
        WHERE ga.guild_id = $1
        ORDER BY ga.created_at DESC
        LIMIT 20
    """
    with db_span("db.fetch", query=activity_query, params=[guild["id"]]):
        activity_rows = await conn.fetch(activity_query, guild["id"])

    trophy_query = """
        SELECT
            grc.id,
            grc.card_code,
            grc.name,
            grc.rarity,
            grc.family,
            grc.description,
            grc.accent,
            grc.awarded_to_user_id,
            owner.username AS awarded_to_username,
            grc.source_quest_id,
            grc.dropped_at
        FROM guild_reward_cards grc
        LEFT JOIN users owner ON owner.id = grc.awarded_to_user_id
        WHERE grc.guild_id = $1
        ORDER BY grc.dropped_at DESC
        LIMIT 12
    """
    with db_span("db.fetch", query=trophy_query, params=[guild["id"]]):
        trophy_rows = await conn.fetch(trophy_query, guild["id"])

    seasonal_reward_query = """
        SELECT
            gsr.id,
            gsr.family,
            gsr.season_code,
            gsr.label,
            gsr.accent,
            gsr.treasury_bonus,
            gsr.guild_tokens_bonus,
            gsr.badge_name,
            gsr.claimed_at
        FROM guild_seasonal_rewards gsr
        WHERE gsr.guild_id = $1
        ORDER BY gsr.claimed_at DESC
    """
    with db_span("db.fetch", query=seasonal_reward_query, params=[guild["id"]]):
        seasonal_reward_rows = await conn.fetch(seasonal_reward_query, guild["id"])

    badge_query = """
        SELECT
            gb.id,
            gb.badge_code,
            gb.name,
            gb.slug,
            gb.accent,
            gb.season_code,
            gb.family,
            gb.awarded_at
        FROM guild_badges gb
        WHERE gb.guild_id = $1
        ORDER BY gb.awarded_at DESC, gb.name ASC
    """
    with db_span("db.fetch", query=badge_query, params=[guild["id"]]):
        badge_rows = await conn.fetch(badge_query, guild["id"])

    trophies = [
        {
            "id": row["id"],
            "card_code": row["card_code"],
            "name": row["name"],
            "rarity": row["rarity"],
            "family": row["family"],
            "description": row["description"],
            "accent": row["accent"],
            "awarded_to_user_id": row["awarded_to_user_id"],
            "awarded_to_username": row["awarded_to_username"],
            "source_quest_id": row["source_quest_id"],
            "dropped_at": row["dropped_at"],
        }
        for row in trophy_rows
    ]

    seasonal_rewards = [
        {
            "id": row["id"],
            "family": row["family"],
            "season_code": row["season_code"],
            "label": row["label"],
            "accent": row["accent"],
            "treasury_bonus": row["treasury_bonus"],
            "guild_tokens_bonus": int(row["guild_tokens_bonus"] or 0),
            "badge_name": row["badge_name"],
            "claimed_at": row["claimed_at"],
        }
        for row in seasonal_reward_rows
    ]
    reward_configs = await guild_card_service.load_season_reward_configs(conn)
    badges = [
        {
            "id": row["id"],
            "badge_code": row["badge_code"],
            "name": row["name"],
            "slug": row["slug"],
            "accent": row["accent"],
            "season_code": row["season_code"],
            "family": row["family"],
            "awarded_at": row["awarded_at"],
        }
        for row in badge_rows
    ]

    members = [
        {
            "id": row["id"],
            "username": row["username"],
            "level": int(row["level"] or 1),
            "grade": GradeEnum(row["grade"]),
            "xp": int(row["xp"] or 0),
            "xp_to_next": int(row["xp_to_next"] or 0),
            "stats": _to_stats(row),
            "skills": list(row["skills"] or []),
            "avg_rating": round(float(row["avg_rating"]), 2) if row["avg_rating"] is not None else None,
            "review_count": int(row["review_count"] or 0),
            "character_class": row["character_class"],
            "role": row["role"],
            "contribution": int(row["contribution"] or 0),
            "joined_at": row["joined_at"],
        }
        for row in member_rows
    ]
    activity = [
        {
            "id": row["id"],
            "event_type": row["event_type"],
            "summary": row["summary"],
            "actor_user_id": row["user_id"],
            "actor_username": row["actor_username"],
            "quest_id": row["quest_id"],
            "treasury_delta": _to_decimal_string(row["treasury_delta"]),
            "guild_tokens_delta": int(row["guild_tokens_delta"] or 0),
            "contribution_delta": int(row["contribution_delta"] or 0),
            "created_at": row["created_at"],
        }
        for row in activity_rows
    ]
    seasonal_sets = guild_card_service.build_seasonal_set_progress(trophies, seasonal_rewards, reward_configs)
    progress_state = await guild_progression_service.get_guild_progress_state(conn, guild["id"])
    milestones = await guild_progression_service.get_guild_milestones(
        conn,
        guild["id"],
        seasonal_xp=int(progress_state.get("seasonal_xp") or 0),
    )

    return {
        "guild": guild,
        "members": members,
        "activity": activity,
        "trophies": trophies,
        "seasonal_sets": seasonal_sets,
        "badges": badges,
        "progression_snapshot": build_guild_progression_snapshot(
            members,
            trophies,
            seasonal_sets,
            progress_state=progress_state,
            milestones=milestones,
        ),
        "generated_at": datetime.now(timezone.utc),
    }


async def get_talent_market(
    conn: asyncpg.Connection,
    *,
    mode: str = "all",
    limit: int = 20,
    offset: int = 0,
    grade: str | None = None,
    search: str | None = None,
    sort_by: str = "xp",
) -> dict:
    guild_cards = await list_guild_cards(conn)
    guild_by_id = {card["id"]: card for card in guild_cards}

    args: list[object] = []
    filters = ["u.role = 'freelancer'"]
    arg_idx = 1

    if grade:
      filters.append(f"u.grade = ${arg_idx}")
      args.append(grade)
      arg_idx += 1

    if mode == "solo":
      filters.append("gm.guild_id IS NULL")
    elif mode == "guild":
      filters.append("gm.guild_id IS NOT NULL")

    if search:
      _escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
      filters.append(f"(u.username ILIKE ${arg_idx} OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(COALESCE(u.skills, '[]'::jsonb)) AS skill WHERE skill ILIKE ${arg_idx}) OR g.name ILIKE ${arg_idx})")
      args.append(f"%{_escaped}%")
      arg_idx += 1

    order_clause = {
            "level": 'u.level DESC, u.xp DESC, COALESCE(u.trust_score, -1) DESC, u.created_at DESC',
            "username": 'u.username ASC, COALESCE(u.trust_score, -1) DESC, u.created_at DESC',
            "rating": 'COALESCE(u.avg_rating, 0) DESC, u.review_count DESC, COALESCE(u.trust_score, -1) DESC, u.xp DESC, u.created_at DESC',
            "trust": 'COALESCE(u.trust_score, -1) DESC, u.xp DESC, u.level DESC, u.created_at DESC',
            "xp": 'u.xp DESC, u.level DESC, COALESCE(u.trust_score, -1) DESC, u.created_at DESC',
        }.get(sort_by, 'u.xp DESC, u.level DESC, COALESCE(u.trust_score, -1) DESC, u.created_at DESC')

    member_query = f"""
        SELECT
            u.id,
            u.username,
            u.level,
            u.grade,
            u.xp,
            u.xp_to_next,
            u.stats_int,
            u.stats_dex,
            u.stats_cha,
            u.badges,
            u.skills,
            u.avg_rating,
            u.review_count,
            u.trust_score,
                        u.availability_status,
            u.character_class,
                        u.portfolio_summary,
            gm.role AS guild_role,
            g.id AS guild_id,
            g.name AS guild_name,
                        g.slug AS guild_slug,
                        COALESCE(q.confirmed_count, 0) AS confirmed_quest_count,
                        COALESCE(q.active_count, 0) AS active_quest_count,
                        q.avg_budget AS avg_budget
        FROM users u
        LEFT JOIN guild_members gm
          ON gm.user_id = u.id AND gm.status = 'active'
        LEFT JOIN guilds g
          ON g.id = gm.guild_id AND g.is_public = TRUE
                LEFT JOIN LATERAL (
                    SELECT
                            COUNT(*) FILTER (WHERE status IN ('completed', 'confirmed')) AS confirmed_count,
                            COUNT(*) FILTER (WHERE status IN ('assigned', 'in_progress', 'revision_requested')) AS active_count,
                            AVG(budget) FILTER (WHERE status IN ('completed', 'confirmed')) AS avg_budget
                    FROM quests
                    WHERE assigned_to = u.id
                ) q ON TRUE
        WHERE {' AND '.join(filters)}
        ORDER BY {order_clause}
        LIMIT ${arg_idx} OFFSET ${arg_idx + 1}
    """
    args.extend([limit + 1, offset])
    with db_span("db.fetch", query=member_query, params=args):
        rows = await conn.fetch(member_query, *args)

    summary_query = """
        SELECT
            COUNT(*) FILTER (WHERE u.role = 'freelancer')::INT AS total_freelancers,
            COUNT(*) FILTER (WHERE u.role = 'freelancer' AND gm.guild_id IS NULL)::INT AS solo_freelancers,
            COUNT(*) FILTER (WHERE u.role = 'freelancer' AND gm.guild_id IS NOT NULL)::INT AS guild_freelancers,
            COALESCE(MAX(u.xp) FILTER (WHERE u.role = 'freelancer' AND gm.guild_id IS NULL), 0)::INT AS top_solo_xp,
            (SELECT COUNT(*)::INT FROM guilds WHERE is_public = TRUE) AS total_guilds
        FROM users u
        LEFT JOIN guild_members gm
          ON gm.user_id = u.id AND gm.status = 'active'
    """
    with db_span("db.fetchrow", query=summary_query, params=[]):
        summary_row = await conn.fetchrow(summary_query)

    members = []
    has_more = len(rows) > limit
    for row in rows[:limit]:
        guild_card = guild_by_id.get(row["guild_id"]) if row["guild_id"] else None
        members.append(
            {
                "id": row["id"],
                "username": row["username"],
                "level": int(row["level"] or 1),
                "grade": GradeEnum(row["grade"]),
                "xp": int(row["xp"] or 0),
                "xp_to_next": int(row["xp_to_next"] or 0),
                "stats": _to_stats(row),
                "badges_count": len(row["badges"] or []),
                "skills": list(row["skills"] or []),
                "avg_rating": round(float(row["avg_rating"]), 2) if row["avg_rating"] is not None else None,
                "review_count": int(row["review_count"] or 0),
                "trust_score": round(float(row["trust_score"]), 4) if row["trust_score"] is not None else None,
                "typical_budget_band": _budget_band(row["avg_budget"]),
                "availability_status": row["availability_status"],
                "response_time_hint": _response_time_hint(
                    int(row["active_quest_count"] or 0),
                    int(row["review_count"] or 0),
                    int(row["confirmed_quest_count"] or 0),
                ),
                "character_class": row["character_class"],
                "market_kind": "guild" if row["guild_id"] else "solo",
                "rank_score": _member_rank_score({
                    "xp": row["xp"],
                    "level": row["level"],
                    "avg_rating": row["avg_rating"],
                    "review_count": row["review_count"],
                    "guild_rating": guild_card["rating"] if guild_card else 0,
                }),
                "rank_signals": _compute_rank_signals(
                    {"avg_rating": row["avg_rating"], "review_count": row["review_count"],
                     "level": row["level"], "grade": row["grade"]},
                    guild_card,
                ),
                "guild": None if not guild_card else {
                    "id": guild_card["id"],
                    "name": guild_card["name"],
                    "slug": guild_card["slug"],
                    "role": row["guild_role"] or "member",
                    "member_count": guild_card["member_count"],
                    "rating": guild_card["rating"],
                    "season_position": guild_card["season_position"],
                },
            }
        )

    return {
        "mode": mode,
        "summary": {
            "total_freelancers": int(summary_row["total_freelancers"] or 0) if summary_row else 0,
            "solo_freelancers": int(summary_row["solo_freelancers"] or 0) if summary_row else 0,
            "guild_freelancers": int(summary_row["guild_freelancers"] or 0) if summary_row else 0,
            "total_guilds": int(summary_row["total_guilds"] or 0) if summary_row else 0,
            "top_solo_xp": int(summary_row["top_solo_xp"] or 0) if summary_row else 0,
            "top_guild_rating": guild_cards[0]["rating"] if guild_cards else 0,
        },
        "members": [] if mode == "top-guilds" else members,
        "guilds": guild_cards,
        "limit": limit,
        "offset": offset,
        "has_more": False if mode == "top-guilds" else has_more,
        "generated_at": datetime.now(timezone.utc),
    }


async def create_guild(conn: asyncpg.Connection, current_user: UserProfile, body: GuildCreateRequest) -> dict:
    if current_user.role != "freelancer":
        raise PermissionError("Only freelancers can create guilds")

    slug = _slugify(body.name)
    guild_id = f"guild_{uuid.uuid4().hex[:12]}"
    member_id = f"guild_member_{uuid.uuid4().hex[:12]}"

    async with conn.transaction():
        existing_membership = await conn.fetchrow(
            "SELECT guild_id FROM guild_members WHERE user_id = $1 AND status = 'active'",
            current_user.id,
        )
        if existing_membership:
            raise ValueError("User is already in a guild")

        existing_slug = await conn.fetchrow(
            "SELECT id FROM guilds WHERE slug = $1 OR LOWER(name) = LOWER($2)",
            slug,
            body.name.strip(),
        )
        if existing_slug:
            raise ValueError("Guild with this name already exists")

        now = datetime.now(timezone.utc)
        await conn.execute(
            """
            INSERT INTO guilds (
                id, owner_id, name, slug, description, emblem,
                is_public, member_limit, treasury_balance, guild_tokens, rating,
                created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, TRUE, 20, 0, 0, 0, $7, $7)
            """,
            guild_id,
            current_user.id,
            body.name.strip(),
            slug,
            body.description.strip() if body.description else None,
            body.emblem.strip().lower(),
            now,
        )
        await conn.execute(
            """
            INSERT INTO guild_members (
                id, guild_id, user_id, role, contribution, status, joined_at
            ) VALUES ($1, $2, $3, 'leader', 0, 'active', $4)
            """,
            member_id,
            guild_id,
            current_user.id,
            now,
        )
        await guild_economy_service.record_guild_activity(
            conn,
            guild_id=guild_id,
            user_id=current_user.id,
            event_type="guild_created",
            summary=f"{current_user.username} founded the guild {body.name.strip()}",
            payload={"role": "leader", "emblem": body.emblem.strip().lower()},
            created_at=now,
        )

    await invalidate_cache_scope("guild_card", "slug", slug)
    return {"guild_id": guild_id, "status": "created", "message": "Guild created successfully"}


async def join_guild(conn: asyncpg.Connection, guild_id: str, current_user: UserProfile) -> dict:
    if current_user.role != "freelancer":
        raise PermissionError("Only freelancers can join guilds")

    async with conn.transaction():
        existing = await conn.fetchrow(
            "SELECT guild_id FROM guild_members WHERE user_id = $1 AND status = 'active'",
            current_user.id,
        )
        if existing:
            raise ValueError("User is already in a guild")

        guild = await conn.fetchrow(
            "SELECT id, member_limit, slug FROM guilds WHERE id = $1 AND is_public = TRUE FOR UPDATE",
            guild_id,
        )
        if not guild:
            raise ValueError("Guild not found")

        member_count = await conn.fetchval(
            "SELECT COUNT(*) FROM guild_members WHERE guild_id = $1 AND status = 'active'",
            guild_id,
        )
        if int(member_count or 0) >= int(guild["member_limit"] or 20):
            raise ValueError("Guild is full")

        await conn.execute(
            """
            INSERT INTO guild_members (id, guild_id, user_id, role, contribution, status, joined_at)
            VALUES ($1, $2, $3, 'member', 0, 'active', $4)
            """,
            f"guild_member_{uuid.uuid4().hex[:12]}",
            guild_id,
            current_user.id,
            datetime.now(timezone.utc),
        )
        await guild_economy_service.record_guild_activity(
            conn,
            guild_id=guild_id,
            user_id=current_user.id,
            event_type="member_joined",
            summary=f"{current_user.username} joined the guild",
            payload={"role": "member"},
        )

    await invalidate_cache_scope("guild_card", "slug", guild["slug"])
    return {"guild_id": guild_id, "status": "joined", "message": "Guild joined successfully"}


async def leave_guild(conn: asyncpg.Connection, guild_id: str, current_user: UserProfile) -> dict:
    guild_slug: str | None = None
    async with conn.transaction():
        membership = await conn.fetchrow(
            "SELECT role FROM guild_members WHERE guild_id = $1 AND user_id = $2 AND status = 'active' FOR UPDATE",
            guild_id,
            current_user.id,
        )
        if not membership:
            raise ValueError("Active guild membership not found")
        if membership["role"] == "leader":
            raise ValueError("Leader cannot leave guild without transferring ownership")

        guild_row = await conn.fetchrow(
            "SELECT slug FROM guilds WHERE id = $1",
            guild_id,
        )
        guild_slug = guild_row["slug"] if guild_row else None

        await conn.execute(
            "UPDATE guild_members SET status = 'left' WHERE guild_id = $1 AND user_id = $2 AND status = 'active'",
            guild_id,
            current_user.id,
        )
        await guild_economy_service.record_guild_activity(
            conn,
            guild_id=guild_id,
            user_id=current_user.id,
            event_type="member_left",
            summary=f"{current_user.username} left the guild",
            payload={"role": membership["role"]},
        )

    if guild_slug:
        await invalidate_cache_scope("guild_card", "slug", guild_slug)
    return {"guild_id": guild_id, "status": "left", "message": "Guild left successfully"}
