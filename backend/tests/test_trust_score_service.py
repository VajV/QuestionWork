from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.services import trust_score_service


def _make_conn():
    return AsyncMock()


def test_calculate_trust_score_full_breakdown():
    score, breakdown = trust_score_service.calculate_trust_score(
        avg_rating_5=4.8,
        accepted_quests=12,
        confirmed_quests=10,
        on_time_quests=9,
        grade="middle",
    )

    assert breakdown["avg_rating"] == pytest.approx(0.96)
    assert breakdown["completion_rate"] == pytest.approx(10 / 12, rel=1e-3)
    assert breakdown["on_time_rate"] == pytest.approx(0.9)
    assert breakdown["level_bonus"] == 0.5
    assert breakdown["raw"] == {
        "average_rating_5": 4.8,
        "accepted_quests": 12,
        "confirmed_quests": 10,
        "on_time_quests": 9,
        "grade": "middle",
    }
    assert score == pytest.approx(0.864, rel=1e-3)


def test_calculate_trust_score_handles_zero_denominators():
    score, breakdown = trust_score_service.calculate_trust_score(
        avg_rating_5=None,
        accepted_quests=0,
        confirmed_quests=0,
        on_time_quests=0,
        grade="novice",
    )

    assert score == 0.0
    assert breakdown["avg_rating"] == 0.0
    assert breakdown["completion_rate"] == 0.0
    assert breakdown["on_time_rate"] == 0.0
    assert breakdown["level_bonus"] == 0.0


@pytest.mark.parametrize(
    ("grade", "expected_bonus"),
    [
        ("novice", 0.0),
        ("junior", 0.25),
        ("middle", 0.5),
        ("senior", 1.0),
        (None, 0.0),
    ],
)
def test_grade_to_level_bonus_mapping(grade, expected_bonus):
    assert trust_score_service.grade_to_level_bonus(grade) == expected_bonus


def test_calculate_trust_score_clamps_to_one():
    score, breakdown = trust_score_service.calculate_trust_score(
        avg_rating_5=50,
        accepted_quests=1,
        confirmed_quests=1,
        on_time_quests=5,
        grade="senior",
    )

    assert score == 1.0
    assert breakdown["avg_rating"] == 1.0
    assert breakdown["on_time_rate"] == 1.0


@pytest.mark.asyncio
async def test_fetch_trust_inputs_uses_cached_profile_values_and_quest_counts():
    conn = _make_conn()
    conn.fetchrow = AsyncMock(
        side_effect=[
            {
                "id": "user_1",
                "avg_rating": Decimal("4.50"),
                "review_count": 3,
                "grade": "junior",
            },
            {
                "accepted_quests": 7,
                "confirmed_quests": 5,
                "on_time_quests": 4,
            },
        ]
    )

    result = await trust_score_service.fetch_trust_inputs(conn, "user_1")

    assert result == {
        "user_id": "user_1",
        "avg_rating_5": 4.5,
        "review_count": 3,
        "grade": "junior",
        "accepted_quests": 7,
        "confirmed_quests": 5,
        "on_time_quests": 4,
    }
    first_query = conn.fetchrow.await_args_list[0].args[0]
    second_query = conn.fetchrow.await_args_list[1].args[0]
    assert "FROM users" in first_query
    assert "COUNT(*) FILTER" in second_query


@pytest.mark.asyncio
async def test_refresh_trust_score_updates_cached_columns():
    conn = _make_conn()
    conn.fetchrow = AsyncMock(
        side_effect=[
            {
                "id": "user_1",
                "avg_rating": Decimal("4.80"),
                "review_count": 8,
                "grade": "middle",
            },
            {
                "accepted_quests": 12,
                "confirmed_quests": 10,
                "on_time_quests": 9,
            },
        ]
    )

    result = await trust_score_service.refresh_trust_score(conn, "user_1")

    assert result["user_id"] == "user_1"
    assert result["trust_score"] == pytest.approx(0.864, rel=1e-3)
    execute_args = conn.execute.await_args.args
    assert "UPDATE users" in execute_args[0]
    assert execute_args[1] == Decimal("0.8640")
    assert result["updated_at"].tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_get_cached_trust_score_returns_stable_breakdown_shape():
    conn = _make_conn()
    updated_at = datetime.now(timezone.utc)
    conn.fetchrow = AsyncMock(
        return_value={
            "id": "user_1",
            "grade": "senior",
            "trust_score": Decimal("0.9123"),
            "trust_score_breakdown": {"avg_rating": 0.9, "raw": {"accepted_quests": 5}},
            "trust_score_updated_at": updated_at,
        }
    )

    result = await trust_score_service.get_cached_trust_score(conn, "user_1")

    assert result["user_id"] == "user_1"
    assert result["trust_score"] == pytest.approx(0.9123)
    assert result["updated_at"] == updated_at
    assert result["breakdown"]["avg_rating"] == 0.9
    assert result["breakdown"]["completion_rate"] == 0.0
    assert result["breakdown"]["raw"]["accepted_quests"] == 5
    assert result["breakdown"]["raw"]["grade"] == "senior"