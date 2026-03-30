# Last Audit Fix Plan (2026-03-13)

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every confirmed finding from the 2026-03-13 audit session — three backend bugs already hotfixed inline and one gap in test coverage that remains open.

**Architecture:** All work is backend-only. Three hotfixes were applied in the same audit session (BUG-1/2/3) and are recorded here as completed reference tasks. The only remaining work is writing a unit-test file for `saved_searches_service`, which has 0% coverage despite being a live, registered endpoint.

**Tech Stack:** Python 3.12 / FastAPI / asyncpg / pytest-asyncio (STRICT mode) / unittest.mock

---

## Audit Findings — Status Overview

| ID | Severity | Title | Status |
|----|----------|-------|--------|
| BUG-1 | P1 | Post-commit notifications always silently fail in `confirm_quest_completion` | ✅ Fixed |
| BUG-2 | P1 | `force_complete_quest` skips stat growth on level-up | ✅ Fixed |
| BUG-3 | P3 | Rate limiter INCR+EXPIRE race condition (key-leak on crash) | ✅ Fixed |
| BUG-4 | — | `broadcast_notification` accepts empty `user_ids` | N/A — by design (broadcasts to all) |
| BUG-5 | P1 | `create_system_message` also fails post-commit (same root as BUG-1) | ✅ Fixed via BUG-1 |
| BUG-6 | P1 | `conftest.py` does not load `.env` | N/A — pydantic-settings loads `.env` natively |
| BUG-7 | P2 | `test_saved_searches.py` missing — 0% coverage on service + endpoint | 🔴 OPEN — see Chunk 1 |
| BUG-8 | P3 | `pytest.ini addopts` includes `--cov` | N/A — `pytest-cov` is installed in venv |

---

## Hotfix Record (already applied — no action needed)

### BUG-1 fix — `quest_service.py`

`confirm_quest_completion` post-commit notification block wrapped in `async with conn.transaction()`.  
Both `notification_service.create_notification` and `message_service.create_system_message` guard on `is_in_transaction()`; calling them outside any transaction raised `RuntimeError` that was silently swallowed.  
Test `test_confirm_runs_in_transaction` updated: `assert conn.transaction.call_count >= 2`.

### BUG-2 fix — `admin_service.py`

`force_complete_quest` now computes `levels_gained = new_level - freelancer_row["level"]`, calls `allocate_stat_points(levels_gained)`, caps stats at `_STAT_CAP = 100`, and writes `stats_int / stats_dex / stats_cha / stat_points` alongside `xp / level / grade / xp_to_next` — matching the normal `confirm_quest_completion` path.

### BUG-3 fix — `ratelimit.py`

Replaced sequential `client.incr(key)` / `client.expire(key, window_seconds)` with a Redis pipeline:
```python
pipe = client.pipeline()
pipe.incr(key)
pipe.expire(key, window_seconds)
val, _ = pipe.execute()
```
Eliminates the key-leak window if the process terminates between the two commands.

---

## Chunk 1 — Write `test_saved_searches.py`

### Task 1: Unit tests for `saved_searches_service`

**Files:**
- Create: `backend/tests/test_saved_searches.py`
- Reference (read-only): `backend/app/services/saved_searches_service.py`

The service has five functions: `list_saved_searches`, `create_saved_search`, `delete_saved_search`, `get_alert_searches`, `mark_alerted`. None require `is_in_transaction()`, so mocking is simpler than wallet/notification tests.

- [ ] **Step 1: Create the test file with imports and helpers**

Create `backend/tests/test_saved_searches.py`:

```python
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
```

- [ ] **Step 2: Run the file to verify imports resolve**

```
cd backend
$env:SECRET_KEY="audit-key-2026-32-chars-long-ok!"
& .venv\Scripts\python.exe -m pytest tests/test_saved_searches.py --collect-only --override-ini="addopts="
```

Expected: `no tests ran` (file exists but no test classes yet). No import errors.

- [ ] **Step 3: Add `TestListSavedSearches` class**

Append to `backend/tests/test_saved_searches.py`:

```python
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

        call_args = conn.fetch.call_args
        assert "specific_user" in call_args[0] or "specific_user" in (call_args[1] or {}).values() or any("specific_user" == a for a in call_args[0][1:])
```

- [ ] **Step 4: Add `TestCreateSavedSearch` class**

Append to `backend/tests/test_saved_searches.py`:

```python
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
        assert any(json.loads(a) == filters for a in call_args if isinstance(a, str) and a.startswith("{"))

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
        # True must appear in the positional args of the INSERT call
        call_args = conn.fetchrow.call_args[0]
        assert True in call_args
```

- [ ] **Step 5: Add `TestDeleteSavedSearch` class**

Append to `backend/tests/test_saved_searches.py`:

```python
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
        # search id also passed
        assert "search-uuid-1" in call_args
```

- [ ] **Step 6: Add `TestGetAlertSearches` and `TestMarkAlerted` classes**

Append to `backend/tests/test_saved_searches.py`:

```python
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
```

- [ ] **Step 7: Run the new tests and verify all pass**

```
$env:SECRET_KEY="audit-key-2026-32-chars-long-ok!"
& "C:\QuestionWork\backend\.venv\Scripts\python.exe" -m pytest "C:\QuestionWork\backend\tests\test_saved_searches.py" -v --tb=short --override-ini="addopts="
```

Expected: **16 passed** (or similar), 0 failed.

- [ ] **Step 8: Run the full test suite to confirm no regressions**

```
$env:SECRET_KEY="audit-key-2026-32-chars-long-ok!"
& "C:\QuestionWork\backend\.venv\Scripts\python.exe" -m pytest "C:\QuestionWork\backend\tests\" -q --tb=short --override-ini="addopts="
```

Expected: **≥ 579 passed**, 0 failed.

---

## Completion Criteria

| Check | Expected |
|-------|----------|
| `test_saved_searches.py` exists | ✅ |
| All saved_searches tests pass | ✅ |
| Full test suite passes | ✅ 0 failures |
| TypeScript check (`tsc --noEmit`) | ✅ 0 errors (unchanged) |
