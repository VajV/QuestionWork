from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.services import matching_service


def _make_conn():
    return AsyncMock()


def _quest_row(*, quest_id: str = "quest_1", client_id: str = "client_1", required_grade: str = "junior", budget: Decimal = Decimal("20000"), skills: str = '["python", "fastapi"]'):
    now = datetime.now(timezone.utc)
    return {
        "id": quest_id,
        "client_id": client_id,
        "client_username": "client",
        "title": "Backend API hardening",
        "description": "Need help with FastAPI and PostgreSQL delivery.",
        "required_grade": required_grade,
        "skills": skills,
        "budget": budget,
        "currency": "RUB",
        "xp_reward": 180,
        "status": "open",
        "assigned_to": None,
        "is_urgent": False,
        "deadline": None,
        "required_portfolio": False,
        "delivery_note": None,
        "delivery_url": None,
        "delivery_submitted_at": None,
        "revision_reason": None,
        "revision_requested_at": None,
        "platform_fee_percent": Decimal("10.00"),
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }


def _freelancer_row(*, user_id: str, grade: str, trust_score: str, skills: list[str], active_quest_count: int = 0, avg_budget: Decimal | None = Decimal("24000")):
    return {
        "id": user_id,
        "username": user_id,
        "level": 5,
        "grade": grade,
        "xp": 700,
        "xp_to_next": 300,
        "stats_int": 12,
        "stats_dex": 10,
        "stats_cha": 11,
        "skills": skills,
        "avg_rating": Decimal("4.80"),
        "review_count": 7,
        "trust_score": Decimal(trust_score),
        "availability_status": "available",
        "avatar_url": None,
        "character_class": None,
        "confirmed_quest_count": 5,
        "active_quest_count": active_quest_count,
        "avg_budget": avg_budget,
    }


def test_calculate_match_score_combines_weighted_dimensions():
    score, breakdown, matched_skills = matching_service.calculate_match_score(
        required_skills=["Python", "FastAPI"],
        candidate_skills=["python", "fastapi", "redis"],
        required_grade="junior",
        candidate_grade="middle",
        trust_score=0.8,
        active_quest_count=0,
        availability_status="available",
        quest_budget=Decimal("20000"),
        typical_budget_band="15k_to_50k",
    )

    assert matched_skills == ["python", "fastapi"]
    assert breakdown["skill_overlap"] == 1.0
    assert breakdown["grade_fit"] == 1.0
    assert breakdown["trust_score"] == 0.8
    assert breakdown["availability"] == 1.0
    assert breakdown["budget_fit"] == 1.0
    assert score == pytest.approx(0.97, rel=1e-3)


def test_calculate_match_score_penalizes_busy_low_fit_candidates():
    score, breakdown, matched_skills = matching_service.calculate_match_score(
        required_skills=["python", "fastapi"],
        candidate_skills=["figma"],
        required_grade="senior",
        candidate_grade="novice",
        trust_score=0.1,
        active_quest_count=3,
        availability_status="busy",
        quest_budget=Decimal("180000"),
        typical_budget_band="up_to_15k",
    )

    assert matched_skills == []
    assert breakdown["skill_overlap"] == 0.0
    assert breakdown["grade_fit"] == 0.0
    assert breakdown["availability"] == 0.25
    assert score < 0.15


@pytest.mark.asyncio
async def test_match_freelancers_for_quest_orders_candidates_by_match_score():
    conn = _make_conn()
    conn.fetchrow = AsyncMock(return_value=_quest_row())
    conn.fetch = AsyncMock(
        return_value=[
            _freelancer_row(user_id="best_fit", grade="middle", trust_score="0.92", skills=["python", "fastapi", "postgres"]),
            _freelancer_row(user_id="weak_fit", grade="novice", trust_score="0.20", skills=["figma"], active_quest_count=2, avg_budget=Decimal("5000")),
        ]
    )

    result = await matching_service.match_freelancers_for_quest(conn, "quest_1", limit=10)

    assert result["quest_id"] == "quest_1"
    assert result["recommendations"][0]["freelancer"]["id"] == "best_fit"
    assert result["recommendations"][0]["matched_skills"] == ["python", "fastapi"]
    assert result["recommendations"][0]["match_score"] > result["recommendations"][1]["match_score"]


@pytest.mark.asyncio
async def test_recommend_quests_for_user_sorts_by_match_strength():
    conn = _make_conn()
    conn.fetchrow = AsyncMock(
        return_value={
            "id": "freelancer_1",
            "role": "freelancer",
            "grade": "middle",
            "skills": ["python", "fastapi", "postgres"],
            "trust_score": Decimal("0.85"),
            "availability_status": "available",
            "avg_rating": Decimal("4.7"),
            "review_count": 5,
            "confirmed_quest_count": 4,
            "active_quest_count": 0,
            "avg_budget": Decimal("24000"),
            "typical_budget_band": "15k_to_50k",
        }
    )
    conn.fetch = AsyncMock(
        side_effect=[
            [
                _quest_row(quest_id="quest_best", required_grade="junior", budget=Decimal("22000"), skills='["python", "fastapi"]'),
                _quest_row(quest_id="quest_weaker", required_grade="senior", budget=Decimal("220000"), skills='["go"]'),
            ],
            [],
        ]
    )

    result = await matching_service.recommend_quests_for_user(conn, "freelancer_1", limit=10)

    assert result["user_id"] == "freelancer_1"
    assert result["recommendations"][0]["quest"].id == "quest_best"
    assert result["recommendations"][0]["matched_skills"] == ["python", "fastapi"]
    assert result["recommendations"][0]["match_score"] > result["recommendations"][1]["match_score"]
