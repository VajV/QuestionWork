"""Unit tests for saved_searches_service."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.saved_searches_service import (
    MAX_SAVED_SEARCHES_PER_USER,
    create_saved_search,
    delete_saved_search,
    get_alert_searches,
    list_saved_searches,
    mark_alerted,
)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_conn():
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=True)
    return conn


def _search_row(
    search_id="search-uuid-1",
    user_id="user_1",
    name="My Filter",
    search_type="quests",
    filters_json=None,
    alert_enabled=False,
    last_alerted_at=None,
    created_at=None,
):
    return {
        "id": search_id,
        "user_id": user_id,
        "name": name,
        "search_type": search_type,
        "filters_json": filters_json or {"grade": "junior"},
        "alert_enabled": alert_enabled,
        "last_alerted_at": last_alerted_at,
        "created_at": created_at or datetime.now(timezone.utc),
    }


# ─────────────────────────────────────────────────────────────────────
# list_saved_searches
# ─────────────────────────────────────────────────────────────────────

class TestListSavedSearches:
    @pytest.mark.asyncio
    async def test_returns_records_ordered_newest_first(self):
        conn = _make_conn()
        row1 = _search_row(search_id="s1")
        row2 = _search_row(search_id="s2")
        conn.fetch = AsyncMock(return_value=[row1, row2])

        result = await list_saved_searches(conn, "user_1")

        assert result == [row1, row2]
        conn.fetch.assert_called_once()
        sql = conn.fetch.call_args[0][0]
        assert "ORDER BY created_at DESC" in sql

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none_exist(self):
        conn = _make_conn()
        conn.fetch = AsyncMock(return_value=[])

        result = await list_saved_searches(conn, "user_no_searches")

        assert result == []

    @pytest.mark.asyncio
    async def test_filters_by_user_id(self):
        conn = _make_conn()
        conn.fetch = AsyncMock(return_value=[])

        await list_saved_searches(conn, "specific_user")

        positional_args = conn.fetch.call_args[0]
        assert "specific_user" in positional_args


# ─────────────────────────────────────────────────────────────────────
# create_saved_search
# ─────────────────────────────────────────────────────────────────────

class TestCreateSavedSearch:
    @pytest.mark.asyncio
    async def test_creates_search_and_returns_row(self):
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=0)  # current count = 0
        conn.fetchrow = AsyncMock(return_value=_search_row(name="New Filter"))

        result = await create_saved_search(
            conn,
            "user_1",
            name="New Filter",
            search_type="quests",
            filters_json={"grade": "senior"},
            alert_enabled=False,
        )

        assert result["name"] == "New Filter"
        conn.fetchrow.assert_called_once()
        sql = conn.fetchrow.call_args[0][0]
        assert "INSERT INTO saved_searches" in sql

    @pytest.mark.asyncio
    async def test_raises_value_error_when_limit_reached(self):
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=MAX_SAVED_SEARCHES_PER_USER)

        with pytest.raises(ValueError, match="limit reached"):
            await create_saved_search(
                conn,
                "user_1",
                name="Overflow",
                search_type="quests",
                filters_json={},
            )

        conn.fetchrow.assert_not_called()

    @pytest.mark.asyncio
    async def test_allowed_at_limit_minus_one(self):
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=MAX_SAVED_SEARCHES_PER_USER - 1)
        conn.fetchrow = AsyncMock(return_value=_search_row())

        # Should NOT raise
        result = await create_saved_search(
            conn, "user_1", name="Just Under Limit",
            search_type="quests", filters_json={},
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_serialises_filters_json_as_jsonb(self):
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetchrow = AsyncMock(return_value=_search_row())

        filters = {"min_budget": 500, "grade": "middle"}
        await create_saved_search(
            conn, "user_1", name="Budget Filter",
            search_type="quests", filters_json=filters,
        )

        call_args = conn.fetchrow.call_args[0]
        # The serialised JSON string is passed as a positional arg
        json_args = [a for a in call_args if isinstance(a, str) and a.startswith("{")]
        assert any(json.loads(a) == filters for a in json_args)

    @pytest.mark.asyncio
    async def test_alert_enabled_flag_passed_through(self):
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=5)
        conn.fetchrow = AsyncMock(return_value=_search_row(alert_enabled=True))

        result = await create_saved_search(
            conn, "user_1", name="Alert Me",
            search_type="quests", filters_json={}, alert_enabled=True,
        )

        assert result["alert_enabled"] is True
        call_args = conn.fetchrow.call_args[0]
        assert True in call_args


# ─────────────────────────────────────────────────────────────────────
# delete_saved_search
# ─────────────────────────────────────────────────────────────────────

class TestDeleteSavedSearch:
    @pytest.mark.asyncio
    async def test_returns_true_when_deleted(self):
        conn = _make_conn()
        conn.execute = AsyncMock(return_value="DELETE 1")

        result = await delete_saved_search(conn, "search-uuid-1", "user_1")

        assert result is True
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found_or_wrong_owner(self):
        conn = _make_conn()
        conn.execute = AsyncMock(return_value="DELETE 0")

        result = await delete_saved_search(conn, "wrong-uuid", "user_1")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_enforces_ownership_via_user_id_param(self):
        conn = _make_conn()
        conn.execute = AsyncMock(return_value="DELETE 1")

        await delete_saved_search(conn, "search-uuid-1", "owner_user")

        call_args = conn.execute.call_args[0]
        assert "owner_user" in call_args
        assert "search-uuid-1" in call_args


# ─────────────────────────────────────────────────────────────────────
# get_alert_searches
# ─────────────────────────────────────────────────────────────────────

class TestGetAlertSearches:
    @pytest.mark.asyncio
    async def test_returns_only_alert_enabled_searches(self):
        conn = _make_conn()
        alert_row = _search_row(search_id="alert-1", alert_enabled=True)
        conn.fetch = AsyncMock(return_value=[alert_row])

        result = await get_alert_searches(conn)

        assert result == [alert_row]
        sql = conn.fetch.call_args[0][0]
        assert "alert_enabled = TRUE" in sql

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_alerts(self):
        conn = _make_conn()
        conn.fetch = AsyncMock(return_value=[])

        result = await get_alert_searches(conn)

        assert result == []

    @pytest.mark.asyncio
    async def test_sql_orders_by_last_alerted_at_asc_nulls_first(self):
        conn = _make_conn()
        conn.fetch = AsyncMock(return_value=[])

        await get_alert_searches(conn)

        sql = conn.fetch.call_args[0][0]
        assert "last_alerted_at ASC NULLS FIRST" in sql


# ─────────────────────────────────────────────────────────────────────
# mark_alerted
# ─────────────────────────────────────────────────────────────────────

class TestMarkAlerted:
    @pytest.mark.asyncio
    async def test_updates_last_alerted_at(self):
        conn = _make_conn()
        conn.execute = AsyncMock(return_value="UPDATE 1")

        await mark_alerted(conn, "search-uuid-1")

        conn.execute.assert_called_once()
        sql, search_id = conn.execute.call_args[0]
        assert "last_alerted_at" in sql
        assert search_id == "search-uuid-1"

    @pytest.mark.asyncio
    async def test_passes_uuid_cast_in_query(self):
        conn = _make_conn()
        conn.execute = AsyncMock(return_value="UPDATE 1")

        await mark_alerted(conn, "some-uuid")

        sql = conn.execute.call_args[0][0]
        assert "$1::uuid" in sql
