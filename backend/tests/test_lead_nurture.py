from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.lead_nurture_service import process_due_leads


def _make_conn(fetch_rows=None):
    conn = AsyncMock()
    txn = AsyncMock()
    txn.__aenter__.return_value = None
    txn.__aexit__.return_value = None
    conn.transaction = MagicMock(return_value=txn)
    conn.fetch = AsyncMock(return_value=fetch_rows or [])
    conn.execute = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_process_due_leads_advances_initial_stage():
    now = datetime(2026, 3, 12, 10, 0, tzinfo=timezone.utc)
    conn = _make_conn(
        [
            {
                "id": "lead_1",
                "email": "buyer@example.com",
                "company_name": "Quest Ops",
                "use_case": "FastAPI backend",
                "status": "new",
                "nurture_stage": "intake",
                "last_contacted_at": None,
                "next_contact_at": now - timedelta(minutes=10),
                "converted_user_id": None,
                "created_at": now - timedelta(days=1),
            }
        ]
    )

    result = await process_due_leads(conn, now=now, limit=10)

    assert result["processed"] == 1
    assert result["planned_touches"][0]["nurture_stage"] == "follow_up_1"
    assert result["planned_touches"][0]["status"] == "nurturing"
    execute_args = conn.execute.await_args.args
    assert execute_args[0].strip().startswith("UPDATE growth_leads")
    assert execute_args[2] == "nurturing"
    assert execute_args[3] == "follow_up_1"
    assert execute_args[5] == now + timedelta(days=3)


@pytest.mark.asyncio
async def test_process_due_leads_pauses_after_final_stage():
    now = datetime(2026, 3, 12, 10, 0, tzinfo=timezone.utc)
    conn = _make_conn(
        [
            {
                "id": "lead_2",
                "email": "buyer@example.com",
                "company_name": "Quest Ops",
                "use_case": "Urgent bugfix",
                "status": "nurturing",
                "nurture_stage": "follow_up_2",
                "last_contacted_at": now - timedelta(days=6),
                "next_contact_at": now - timedelta(minutes=5),
                "converted_user_id": None,
                "created_at": now - timedelta(days=9),
            }
        ]
    )

    result = await process_due_leads(conn, now=now, limit=10)

    assert result["planned_touches"][0]["nurture_stage"] == "paused"
    assert result["planned_touches"][0]["status"] == "paused"
    assert result["planned_touches"][0]["next_contact_at"] is None


@pytest.mark.asyncio
async def test_process_due_leads_dry_run_is_idempotent():
    now = datetime(2026, 3, 12, 10, 0, tzinfo=timezone.utc)
    conn = _make_conn(
        [
            {
                "id": "lead_3",
                "email": "buyer@example.com",
                "company_name": "Quest Ops",
                "use_case": "MVP sprint",
                "status": "new",
                "nurture_stage": "intake",
                "last_contacted_at": None,
                "next_contact_at": now - timedelta(minutes=1),
                "converted_user_id": None,
                "created_at": now - timedelta(days=1),
            }
        ]
    )

    result = await process_due_leads(conn, now=now, limit=10, dry_run=True)

    assert result["processed"] == 1
    conn.execute.assert_not_awaited()
    fetch_query = conn.fetch.await_args.args[0]
    assert "converted_user_id IS NULL" in fetch_query
    assert "last_contacted_at IS NULL OR last_contacted_at <= $3" in fetch_query