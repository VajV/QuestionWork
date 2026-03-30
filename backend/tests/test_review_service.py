"""Targeted coverage for review_service edge cases and happy paths."""

import fnmatch
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.review_service import (
    REVIEW_BONUS_XP,
    create_review,
    get_reviews_for_user,
    get_user_rating,
    has_reviewed,
)


def _make_conn(in_txn: bool = True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_txn)
    return conn


async def _aiter(values):
    for value in values:
        yield value


@pytest.fixture(autouse=True)
def _mock_refresh_trust_score():
    with patch(
        "app.services.review_service.trust_score_service.refresh_trust_score",
        new=AsyncMock(return_value=None),
    ):
        yield


class TestCreateReview:
    @pytest.mark.asyncio
    async def test_create_review_invalidates_scoped_user_rating_cache(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(
            side_effect=[
                {
                    "id": "quest_1",
                    "client_id": "client_1",
                    "assigned_to": "freelancer_1",
                    "status": "confirmed",
                },
                {"id": "reviewee_lock"},
                {"xp": 0, "level": 1, "grade": "novice"},
            ]
        )
        conn.fetchval = AsyncMock(side_effect=[None, 1])

        badge_result = SimpleNamespace(newly_earned=[])
        with patch(
            "app.services.review_service.badge_service.check_and_award",
            new=AsyncMock(return_value=badge_result),
        ):
            with patch(
                "app.services.review_service.invalidate_cache_scope",
                new=AsyncMock(),
                create=True,
            ) as mock_invalidate:
                await create_review(
                    conn,
                    quest_id="quest_1",
                    reviewer_id="client_1",
                    reviewee_id="freelancer_1",
                    rating=4,
                    comment="Solid work",
                )

        mock_invalidate.assert_awaited_once_with("user_rating", "user", "freelancer_1")

    @pytest.mark.asyncio
    async def test_create_review_awards_bonus_xp_for_five_stars(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(
            side_effect=[
                {
                    "id": "quest_1",
                    "client_id": "client_1",
                    "assigned_to": "freelancer_1",
                    "status": "confirmed",
                },
                {"id": "reviewee_lock"},
                {"xp": 100, "level": 1, "grade": "novice"},
                {"xp": 110, "level": 1, "grade": "novice"},
            ]
        )
        conn.fetchval = AsyncMock(side_effect=[None, 1, 2])

        badge_result = SimpleNamespace(newly_earned=[])
        with patch(
            "app.services.review_service.badge_service.check_and_award",
            new=AsyncMock(return_value=badge_result),
        ):
            result = await create_review(
                conn,
                quest_id="quest_1",
                reviewer_id="client_1",
                reviewee_id="freelancer_1",
                rating=5,
                comment="Strong delivery",
            )

        assert result["quest_id"] == "quest_1"
        assert result["xp_bonus"] == REVIEW_BONUS_XP
        executed_queries = [call.args[0] for call in conn.execute.await_args_list]
        assert any("INSERT INTO quest_reviews" in query for query in executed_queries)
        assert any("avg_rating" in query for query in executed_queries)
        assert any("UPDATE users SET xp = $1" in query for query in executed_queries)

    @pytest.mark.asyncio
    async def test_create_review_refreshes_trust_score_for_reviewee(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(
            side_effect=[
                {
                    "id": "quest_1",
                    "client_id": "client_1",
                    "assigned_to": "freelancer_1",
                    "status": "confirmed",
                },
                {"id": "reviewee_lock"},
                {"xp": 0, "level": 1, "grade": "novice"},
            ]
        )
        conn.fetchval = AsyncMock(side_effect=[None, 1])

        badge_result = SimpleNamespace(newly_earned=[])
        with patch(
            "app.services.review_service.badge_service.check_and_award",
            new=AsyncMock(return_value=badge_result),
        ):
            with patch(
                "app.services.review_service.trust_score_service.refresh_trust_score",
                new=AsyncMock(),
            ) as mock_refresh_trust:
                await create_review(
                    conn,
                    quest_id="quest_1",
                    reviewer_id="client_1",
                    reviewee_id="freelancer_1",
                    rating=4,
                    comment="Solid work",
                )

        mock_refresh_trust.assert_awaited_once_with(conn, "freelancer_1")

    @pytest.mark.asyncio
    async def test_create_review_rejects_duplicate_review(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "quest_1",
                "client_id": "client_1",
                "assigned_to": "freelancer_1",
                "status": "confirmed",
            }
        )
        conn.fetchval = AsyncMock(return_value=1)

        with pytest.raises(ValueError, match="уже оставили отзыв"):
            await create_review(
                conn,
                quest_id="quest_1",
                reviewer_id="client_1",
                reviewee_id="freelancer_1",
                rating=4,
            )


class TestReviewReads:
    @pytest.mark.asyncio
    async def test_invalidate_cache_scope_deletes_only_matching_scope_keys(self):
        from app.core.cache import invalidate_cache_scope

        keys = [
            "qw:cache:user_rating:user:user_1:abc",
            "qw:cache:user_rating:user:user_2:def",
        ]
        redis = SimpleNamespace(delete=AsyncMock())

        def _scan_iter(*, match: str, count: int):
            return _aiter([key for key in keys if fnmatch.fnmatch(key, match)])

        redis.scan_iter = MagicMock(side_effect=_scan_iter)

        with patch("app.core.cache.get_redis_client", new=AsyncMock(return_value=redis)):
            deleted = await invalidate_cache_scope("user_rating", "user", "user_1")

        assert deleted == 1
        redis.scan_iter.assert_called_once_with(match="qw:cache:user_rating:user:user_1:*", count=100)
        redis.delete.assert_awaited_once_with("qw:cache:user_rating:user:user_1:abc")

    @pytest.mark.asyncio
    async def test_get_reviews_for_user_returns_reviews_and_avg(self):
        now = datetime.now(timezone.utc)
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(side_effect=[2, Decimal("4.25")])
        conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": "rev_1",
                    "quest_id": "quest_1",
                    "reviewer_id": "client_1",
                    "reviewee_id": "freelancer_1",
                    "reviewer_username": "client",
                    "rating": 5,
                    "comment": "Great",
                    "created_at": now,
                },
                {
                    "id": "rev_2",
                    "quest_id": "quest_2",
                    "reviewer_id": "client_2",
                    "reviewee_id": "freelancer_1",
                    "reviewer_username": "client2",
                    "rating": 4,
                    "comment": None,
                    "created_at": now,
                },
            ]
        )

        result = await get_reviews_for_user(conn, "freelancer_1")

        assert result["total"] == 2
        assert result["review_count"] == 2
        assert result["avg_rating"] == Decimal("4.25")
        assert result["reviews"][0]["reviewer_username"] == "client"
        assert result["reviews"][0]["created_at"] == now.isoformat()

    @pytest.mark.asyncio
    async def test_get_user_rating_returns_rounded_payload(self):
        conn = _make_conn(in_txn=False)
        conn.fetchrow = AsyncMock(return_value={"avg_rating": Decimal("4.50"), "review_count": 3})

        result = await get_user_rating(conn, "freelancer_1")

        assert result == {"avg_rating": Decimal("4.50"), "review_count": 3}

    @pytest.mark.asyncio
    async def test_has_reviewed_returns_boolean(self):
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(return_value=1)

        assert await has_reviewed(conn, "quest_1", "client_1") is True

        conn.fetchval = AsyncMock(return_value=None)
        assert await has_reviewed(conn, "quest_1", "client_1") is False