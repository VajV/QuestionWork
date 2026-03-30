import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.repositories import command_repository


@pytest.mark.asyncio
async def test_command_dedupe_key_replay_within_retention_window_returns_existing_command():
    conn = AsyncMock()
    now = datetime.now(timezone.utc)
    row = {"id": "cmd-1", "status": "succeeded", "submitted_at": now.isoformat()}
    conn.fetchrow = AsyncMock(return_value=row)

    result = await command_repository.find_replayable_command_by_dedupe_key(
        conn,
        command_kind="ops.noop",
        dedupe_key="ops:noop:1",
        replay_window_seconds=60,
        now=now,
    )

    assert result == row
    query, kind, dedupe_key, cutoff = conn.fetchrow.await_args.args
    assert "FROM command_requests" in query
    assert "status IN ('accepted', 'running', 'succeeded')" in query
    assert kind == "ops.noop"
    assert dedupe_key == "ops:noop:1"
    assert cutoff == now - timedelta(seconds=60)


@pytest.mark.asyncio
async def test_create_command_persists_payload_json():
    conn = AsyncMock()
    row = {"id": "cmd-2", "status": "accepted"}
    conn.fetchrow = AsyncMock(return_value=row)

    result = await command_repository.create_command(
        conn,
        command_kind="ops.noop",
        dedupe_key="ops:noop:2",
        request_id="req-1",
        payload_json={"job": "noop"},
    )

    assert result == row
    query = conn.fetchrow.await_args.args[0]
    payload = conn.fetchrow.await_args.args[-1]
    assert "INSERT INTO command_requests" in query
    assert json.loads(payload) == {"job": "noop"}


@pytest.mark.asyncio
async def test_mark_command_failed_updates_terminal_fields():
    conn = AsyncMock()
    row = {"id": "cmd-3", "status": "failed", "error_code": "boom"}
    conn.fetchrow = AsyncMock(return_value=row)

    result = await command_repository.mark_command_failed(
        conn,
        "cmd-3",
        error_code="boom",
        error_text="failure",
    )

    assert result["status"] == "failed"
    query, command_id, error_code, error_text = conn.fetchrow.await_args.args
    assert "SET status = 'failed'" in query
    assert command_id == "cmd-3"
    assert error_code == "boom"
    assert error_text == "failure"


@pytest.mark.asyncio
async def test_get_command_by_id_uses_primary_key_lookup():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": "cmd-4"})

    result = await command_repository.get_command_by_id(conn, "cmd-4")

    assert result == {"id": "cmd-4"}
    query, command_id = conn.fetchrow.await_args.args
    assert query.strip() == "SELECT * FROM command_requests WHERE id = $1"
    assert command_id == "cmd-4"