from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _user_profile(**overrides):
    from app.models.user import GradeEnum, UserProfile, UserRoleEnum, UserStats

    payload = {
        "id": "user_profile_1",
        "username": "proofsmith",
        "email": "proofsmith@example.com",
        "role": UserRoleEnum.freelancer,
        "level": 8,
        "grade": GradeEnum.junior,
        "xp": 900,
        "xp_to_next": 600,
        "stats": UserStats(intelligence=12, dexterity=10, charisma=11),
        "bio": None,
        "skills": [],
        "availability_status": None,
        "portfolio_links": [],
        "portfolio_summary": None,
        "badges": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    payload.update(overrides)
    return UserProfile(**payload)


class _AsyncTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_build_public_profile_payload_computes_completeness_and_proof_fields():
    from app.api.v1.endpoints.users import _build_public_profile_payload

    profile = _user_profile(
        bio="Backend engineer with clear delivery habits.",
        skills=["FastAPI", "PostgreSQL"],
        availability_status="available",
        portfolio_links=["https://github.com/example/case"],
    )
    proof = {
        "avg_rating": 4.9,
        "review_count": 3,
        "trust_score": 0.8123,
        "trust_score_updated_at": datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
        "confirmed_quest_count": 2,
        "completion_rate": 100.0,
        "avg_budget": Decimal("64000.00"),
        "active_quest_count": 0,
        "portfolio_links": ["https://github.com/example/case"],
        "portfolio_summary": None,
        "availability_status": "available",
    }

    payload = _build_public_profile_payload(profile, proof)

    assert payload["typical_budget_band"] == "50k_to_150k"
    assert payload["response_time_hint"] == "Недавно активен, ответ обычно не затягивается"
    assert payload["profile_completeness_percent"] == 100
    assert payload["onboarding_completed"] is True
    assert payload["trust_score"] == pytest.approx(0.8123)
    assert payload["trust_score_updated_at"] == datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc)


def test_to_public_user_profile_serializes_trust_fields():
    from app.models.user import to_public_user_profile

    profile = _user_profile()
    updated_at = datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc)

    public_profile = to_public_user_profile(
        profile,
        avg_rating=4.8,
        review_count=6,
        trust_score=0.9021,
        trust_score_updated_at=updated_at,
        confirmed_quest_count=5,
        completion_rate=100.0,
    )

    assert public_profile.trust_score == pytest.approx(0.9021)
    assert public_profile.trust_score_updated_at == updated_at


def test_row_to_user_profile_includes_avatar_url():
    from app.models.user import row_to_user_profile

    now = datetime.now(timezone.utc)
    row = {
        "id": "user_profile_2",
        "username": "avatar_user",
        "email": "avatar@example.com",
        "role": "freelancer",
        "is_banned": False,
        "banned_reason": None,
        "level": 3,
        "grade": "novice",
        "xp": 120,
        "xp_to_next": 180,
        "stat_points": 0,
        "stats_int": 10,
        "stats_dex": 11,
        "stats_cha": 9,
        "badges": [],
        "bio": "Profile with avatar",
        "avatar_url": "/uploads/avatars/test.png",
        "skills": ["FastAPI"],
        "availability_status": "available",
        "portfolio_links": [],
        "portfolio_summary": None,
        "onboarding_completed": False,
        "onboarding_completed_at": None,
        "profile_completeness_percent": 40,
        "character_class": None,
        "created_at": now,
        "updated_at": now,
    }

    profile = row_to_user_profile(row)

    assert profile.avatar_url == "/uploads/avatars/test.png"


@pytest.mark.asyncio
async def test_update_my_profile_persists_onboarding_completion_fields():
    from app.api.v1.endpoints.users import ProfileUpdateRequest, update_my_profile

    now = datetime.now(timezone.utc)
    current_user = _user_profile()
    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={},
    )

    conn = AsyncMock()
    conn.transaction = lambda: _AsyncTransaction()
    conn.fetchrow.side_effect = [
        {
            "avg_rating": Decimal("4.60"),
            "review_count": 4,
            "trust_score": None,
            "trust_score_updated_at": None,
            "availability_status": None,
            "portfolio_summary": None,
            "portfolio_links": [],
            "confirmed_quest_count": 1,
            "active_quest_count": 0,
            "avg_budget": Decimal("20000.00"),
            "completion_rate": Decimal("100.0"),
        },
        {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": "freelancer",
            "is_banned": False,
            "banned_reason": None,
            "level": current_user.level,
            "grade": "junior",
            "xp": current_user.xp,
            "xp_to_next": current_user.xp_to_next,
            "stat_points": 0,
            "stats_int": 12,
            "stats_dex": 10,
            "stats_cha": 11,
            "badges": [],
            "bio": "Reliable backend freelancer with product focus.",
            "skills": ["FastAPI", "PostgreSQL"],
            "availability_status": "available",
            "portfolio_links": ["https://github.com/example/case"],
            "portfolio_summary": "Shipping APIs and dashboards.",
            "onboarding_completed": True,
            "onboarding_completed_at": now,
            "profile_completeness_percent": 100,
            "character_class": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "avg_rating": Decimal("4.60"),
            "review_count": 4,
            "trust_score": Decimal("0.8123"),
            "trust_score_updated_at": now,
            "availability_status": "available",
            "portfolio_summary": "Shipping APIs and dashboards.",
            "portfolio_links": ["https://github.com/example/case"],
            "confirmed_quest_count": 1,
            "active_quest_count": 0,
            "avg_budget": Decimal("20000.00"),
            "completion_rate": Decimal("100.0"),
        },
    ]

    with patch("app.api.v1.endpoints.users.check_rate_limit"):
        response = await update_my_profile(
            request=request,
            body=ProfileUpdateRequest(
                bio="Reliable backend freelancer with product focus.",
                skills=["FastAPI", "PostgreSQL"],
                availability_status="available",
                portfolio_summary="Shipping APIs and dashboards.",
                portfolio_links=["https://github.com/example/case"],
            ),
            current_user=current_user,
            conn=conn,
        )

    assert response.onboarding_completed is True
    assert response.profile_completeness_percent == 100
    assert response.availability_status == "available"
    assert response.typical_budget_band == "15k_to_50k"


@pytest.mark.asyncio
async def test_complete_onboarding_sets_flag_and_awards_badge():
    from app.api.v1.endpoints.users import complete_onboarding

    current_user = _user_profile()
    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={},
    )

    conn = AsyncMock()
    conn.transaction = lambda: _AsyncTransaction()
    conn.execute = AsyncMock()

    mock_badge = SimpleNamespace(
        dict=lambda: {
            "id": "ub_1",
            "user_id": current_user.id,
            "badge_id": "badge_recruit",
            "badge_name": "Новобранец",
            "badge_description": "Завершил онбординг и готов к работе",
            "badge_icon": "/icons/badges/recruit.svg",
            "earned_at": "2026-03-17T00:00:00Z",
        }
    )
    mock_result = SimpleNamespace(newly_earned=[mock_badge])

    with patch("app.api.v1.endpoints.users.badge_service") as mock_bs:
        mock_bs.check_and_award = AsyncMock(return_value=mock_result)
        response = await complete_onboarding(
            request=request,
            current_user=current_user,
            conn=conn,
        )

    assert response["ok"] is True
    assert len(response["badges_earned"]) == 1
    assert response["badges_earned"][0]["badge_id"] == "badge_recruit"

    # Verify UPDATE was called with current_user.id (not dict-style)
    conn.execute.assert_called_once()
    call_args = conn.execute.call_args
    assert current_user.id in call_args.args

    # Verify badge_service called with correct params
    mock_bs.check_and_award.assert_awaited_once_with(
        conn, current_user.id, "registration", {}
    )


@pytest.mark.asyncio
async def test_get_user_trust_score_returns_cached_payload():
    from app.api.v1.endpoints.users import get_user_trust_score

    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={},
    )
    conn = AsyncMock()
    updated_at = datetime(2026, 3, 17, 14, 0, tzinfo=timezone.utc)

    with patch("app.api.v1.endpoints.users.check_rate_limit"):
        with patch(
            "app.api.v1.endpoints.users.trust_score_service.get_cached_trust_score",
            new=AsyncMock(
                return_value={
                    "user_id": "user_profile_1",
                    "trust_score": 0.7444,
                    "breakdown": {
                        "avg_rating": 0.9,
                        "completion_rate": 0.8,
                        "on_time_rate": 0.75,
                        "level_bonus": 0.25,
                        "raw": {
                            "average_rating_5": 4.5,
                            "accepted_quests": 10,
                            "confirmed_quests": 8,
                            "on_time_quests": 6,
                            "grade": "junior",
                        },
                    },
                    "updated_at": updated_at,
                }
            ),
        ):
            response = await get_user_trust_score("user_profile_1", request=request, conn=conn)

    assert response.user_id == "user_profile_1"
    assert response.trust_score == pytest.approx(0.7444)
    assert response.breakdown.raw.grade == "junior"
    assert response.updated_at == updated_at