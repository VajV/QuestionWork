import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Optional

import asyncpg

from app.models.matching import MatchBreakdown
from app.models.user import UserStats, _safe_character_class, _safe_json_list
from app.services.quest_service import row_to_quest


GRADE_ORDER = {
    "novice": 0,
    "junior": 1,
    "middle": 2,
    "senior": 3,
}

MATCH_WEIGHTS = {
    "skill_overlap": 0.45,
    "grade_fit": 0.20,
    "trust_score": 0.15,
    "availability": 0.10,
    "budget_fit": 0.10,
}

BUDGET_BANDS = ["up_to_15k", "15k_to_50k", "50k_to_150k", "150k_plus"]


def _round_score(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _normalize_skill(skill: str) -> str:
    return str(skill or "").strip().lower()


def _unique_normalized_skills(skills: Iterable[str] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for skill in skills or []:
        normalized = _normalize_skill(skill)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _score_skill_overlap(required_skills: Iterable[str] | None, candidate_skills: Iterable[str] | None) -> tuple[float, list[str]]:
    required = _unique_normalized_skills(required_skills)
    candidate = set(_unique_normalized_skills(candidate_skills))
    if not required:
        return 0.0, []
    matched = [skill for skill in required if skill in candidate]
    return _round_score(len(matched) / len(required)), matched


def _score_grade_fit(required_grade: str | None, candidate_grade: str | None) -> float:
    required_rank = GRADE_ORDER.get(str(required_grade or "novice"), 0)
    candidate_rank = GRADE_ORDER.get(str(candidate_grade or "novice"), 0)
    if candidate_rank >= required_rank:
        return 1.0
    if required_rank - candidate_rank == 1:
        return 0.5
    return 0.0


def _budget_band_for_value(budget: Decimal | float | int | None) -> str:
    value = Decimal(str(budget or 0))
    if value < Decimal("15000"):
        return "up_to_15k"
    if value < Decimal("50000"):
        return "15k_to_50k"
    if value < Decimal("150000"):
        return "50k_to_150k"
    return "150k_plus"


def _score_budget_fit(quest_budget: Decimal | float | int | None, typical_budget_band: Optional[str]) -> float:
    if not typical_budget_band:
        return 0.5
    quest_band = _budget_band_for_value(quest_budget)
    try:
        distance = abs(BUDGET_BANDS.index(quest_band) - BUDGET_BANDS.index(typical_budget_band))
    except ValueError:
        return 0.5
    if distance == 0:
        return 1.0
    if distance == 1:
        return 0.7
    return 0.35


def _score_availability(active_quest_count: int, availability_status: Optional[str]) -> float:
    if active_quest_count <= 0:
        score = 1.0
    elif active_quest_count == 1:
        score = 0.6
    else:
        score = 0.25

    status = (availability_status or "").strip().lower()
    if any(token in status for token in ("full", "busy", "offline")):
        return min(score, 0.25)
    if any(token in status for token in ("part", "limited")):
        return min(score, 0.6)
    return score


def _response_time_hint(active_quest_count: int, review_count: int, confirmed_quest_count: int) -> str:
    if active_quest_count >= 2:
        return "Сейчас сфокусирован на активных задачах"
    if active_quest_count == 1:
        return "Обычно отвечает выборочно из-за текущей загрузки"
    if confirmed_quest_count >= 6 or review_count >= 6:
        return "Обычно отвечает в течение рабочего дня"
    if confirmed_quest_count >= 2 or review_count >= 2:
        return "Недавно активен, ответ обычно не затягивается"
    return "Нужна первая подтверждённая история отклика"


def calculate_match_score(
    *,
    required_skills: Iterable[str] | None,
    candidate_skills: Iterable[str] | None,
    required_grade: str | None,
    candidate_grade: str | None,
    trust_score: float | None,
    active_quest_count: int,
    availability_status: Optional[str],
    quest_budget: Decimal | float | int | None,
    typical_budget_band: Optional[str],
) -> tuple[float, dict[str, float], list[str]]:
    skill_overlap, matched_skills = _score_skill_overlap(required_skills, candidate_skills)
    breakdown = {
        "skill_overlap": skill_overlap,
        "grade_fit": _score_grade_fit(required_grade, candidate_grade),
        "trust_score": _round_score(float(trust_score or 0.0)),
        "availability": _round_score(_score_availability(active_quest_count, availability_status)),
        "budget_fit": _round_score(_score_budget_fit(quest_budget, typical_budget_band)),
    }
    score = _round_score(sum(breakdown[key] * weight for key, weight in MATCH_WEIGHTS.items()))
    return score, breakdown, matched_skills


def _build_freelancer_card(row) -> dict:
    active_count = int(row.get("active_quest_count") or 0)
    confirmed_count = int(row.get("confirmed_quest_count") or 0)
    review_count = int(row.get("review_count") or 0)
    avg_rating = float(row["avg_rating"]) if row.get("avg_rating") is not None else None
    trust_score = float(row["trust_score"]) if row.get("trust_score") is not None else None
    return {
        "id": row["id"],
        "username": row["username"],
        "level": int(row.get("level") or 1),
        "grade": row.get("grade") or "novice",
        "xp": int(row.get("xp") or 0),
        "xp_to_next": int(row.get("xp_to_next") or 0),
        "stats": UserStats(
            int=row.get("stats_int") or 10,
            dex=row.get("stats_dex") or 10,
            cha=row.get("stats_cha") or 10,
        ),
        "skills": _safe_json_list(row.get("skills")),
        "avg_rating": avg_rating,
        "review_count": review_count,
        "trust_score": trust_score,
        "typical_budget_band": row.get("typical_budget_band") or _budget_band_for_value(row.get("avg_budget")) if row.get("avg_budget") is not None else row.get("typical_budget_band"),
        "availability_status": row.get("availability_status"),
        "response_time_hint": _response_time_hint(active_count, review_count, confirmed_count),
        "character_class": _safe_character_class(row.get("character_class")),
        "avatar_url": row.get("avatar_url"),
    }


async def match_freelancers_for_quest(conn: asyncpg.Connection, quest_id: str, limit: int = 10) -> dict:
    quest_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest_row:
        raise ValueError("Quest not found")

    quest = row_to_quest(quest_row, [])
    candidate_rows = await conn.fetch(
        """
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
            COALESCE(u.skills, '[]'::jsonb) AS skills,
            u.avg_rating,
            u.review_count,
            u.trust_score,
            u.availability_status,
            u.avatar_url,
            u.character_class,
            q.confirmed_quest_count,
            q.active_quest_count,
            q.avg_budget
        FROM users u
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (WHERE status IN ('completed', 'confirmed')) AS confirmed_quest_count,
                COUNT(*) FILTER (WHERE status IN ('assigned', 'in_progress', 'revision_requested')) AS active_quest_count,
                AVG(budget) FILTER (WHERE status IN ('completed', 'confirmed')) AS avg_budget
            FROM quests
            WHERE assigned_to = u.id
        ) q ON TRUE
        WHERE u.role = 'freelancer'
          AND u.id <> $1
        ORDER BY COALESCE(u.trust_score, -1) DESC, COALESCE(u.avg_rating, 0) DESC, u.xp DESC, u.created_at DESC
        LIMIT $2
        """,
        quest.client_id,
        min(limit * 10, 200),
    )

    recommendations: list[dict] = []
    for row in candidate_rows:
        card = _build_freelancer_card(row)
        score, breakdown, matched_skills = calculate_match_score(
            required_skills=quest.skills,
            candidate_skills=card["skills"],
            required_grade=quest.required_grade,
            candidate_grade=card["grade"],
            trust_score=card["trust_score"],
            active_quest_count=int(row.get("active_quest_count") or 0),
            availability_status=card["availability_status"],
            quest_budget=quest.budget,
            typical_budget_band=card["typical_budget_band"],
        )
        recommendations.append(
            {
                "freelancer": card,
                "match_score": score,
                "match_breakdown": MatchBreakdown(**breakdown),
                "matched_skills": matched_skills,
            }
        )

    recommendations.sort(
        key=lambda item: (
            item["match_score"],
            item["match_breakdown"].skill_overlap,
            item["freelancer"].get("trust_score") or 0.0,
            item["freelancer"].get("avg_rating") or 0.0,
            item["freelancer"]["xp"],
        ),
        reverse=True,
    )

    return {
        "quest_id": quest_id,
        "recommendations": recommendations[:limit],
        "generated_at": datetime.now(timezone.utc),
    }


async def recommend_quests_for_user(conn: asyncpg.Connection, user_id: str, limit: int = 10) -> dict:
    user_row = await conn.fetchrow(
        """
        SELECT
            id,
            role,
            grade,
            COALESCE(skills, '[]'::jsonb) AS skills,
            trust_score,
            availability_status,
            avg_rating,
            review_count,
            q.confirmed_quest_count,
            q.active_quest_count,
            q.avg_budget,
            CASE
                WHEN q.avg_budget IS NULL THEN NULL
                WHEN q.avg_budget < 15000 THEN 'up_to_15k'
                WHEN q.avg_budget < 50000 THEN '15k_to_50k'
                WHEN q.avg_budget < 150000 THEN '50k_to_150k'
                ELSE '150k_plus'
            END AS typical_budget_band
        FROM users u
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (WHERE status IN ('completed', 'confirmed')) AS confirmed_quest_count,
                COUNT(*) FILTER (WHERE status IN ('assigned', 'in_progress', 'revision_requested')) AS active_quest_count,
                AVG(budget) FILTER (WHERE status IN ('completed', 'confirmed')) AS avg_budget
            FROM quests
            WHERE assigned_to = u.id
        ) q ON TRUE
        WHERE id = $1
        """,
        user_id,
    )
    if not user_row:
        raise ValueError("User not found")
    if user_row["role"] != "freelancer":
        raise PermissionError("Only freelancers can access recommended quests")

    quest_rows = await conn.fetch(
        """
        SELECT q.*
        FROM quests q
        WHERE q.status = 'open'
          AND q.client_id <> $1
          AND q.assigned_to IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM applications a
              WHERE a.quest_id = q.id AND a.freelancer_id = $1
          )
        ORDER BY q.created_at DESC
        LIMIT $2
        """,
        user_id,
        min(limit * 10, 200),
    )

    quest_ids = [row["id"] for row in quest_rows]
    apps_map: dict[str, list[str]] = {quest_id: [] for quest_id in quest_ids}
    if quest_ids:
        application_rows = await conn.fetch(
            "SELECT quest_id, freelancer_id FROM applications WHERE quest_id = ANY($1::text[])",
            quest_ids,
        )
        for application_row in application_rows:
            apps_map[application_row["quest_id"]].append(application_row["freelancer_id"])

    candidate_skills = _safe_json_list(user_row.get("skills"))
    candidate_grade = user_row.get("grade")
    candidate_trust = float(user_row["trust_score"]) if user_row.get("trust_score") is not None else None
    active_quest_count = int(user_row.get("active_quest_count") or 0)
    availability_status = user_row.get("availability_status")
    typical_budget_band = user_row.get("typical_budget_band")

    recommendations: list[dict] = []
    for quest_row in quest_rows:
        quest = row_to_quest(quest_row, apps_map.get(quest_row["id"], []))
        score, breakdown, matched_skills = calculate_match_score(
            required_skills=quest.skills,
            candidate_skills=candidate_skills,
            required_grade=quest.required_grade,
            candidate_grade=candidate_grade,
            trust_score=candidate_trust,
            active_quest_count=active_quest_count,
            availability_status=availability_status,
            quest_budget=quest.budget,
            typical_budget_band=typical_budget_band,
        )
        recommendations.append(
            {
                "quest": quest,
                "match_score": score,
                "match_breakdown": MatchBreakdown(**breakdown),
                "matched_skills": matched_skills,
            }
        )

    recommendations.sort(
        key=lambda item: (
            item["match_score"],
            item["match_breakdown"].skill_overlap,
            item["quest"].is_urgent,
            item["quest"].created_at,
        ),
        reverse=True,
    )

    return {
        "user_id": user_id,
        "recommendations": recommendations[:limit],
        "generated_at": datetime.now(timezone.utc),
    }
