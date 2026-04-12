from unittest.mock import AsyncMock, MagicMock

import pytest

from app.jobs.handlers.lifecycle_send import LifecycleSendHandler, LIFECYCLE_SEND_KIND
from app.services import lifecycle_runtime_service, lifecycle_service


@pytest.mark.asyncio
async def test_schedule_due_lifecycle_jobs_creates_jobs_for_pending_messages(monkeypatch):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {"id": "msg-1"},
        {"id": "msg-2"},
    ])
    create_job = AsyncMock()
    monkeypatch.setattr(lifecycle_runtime_service.job_repository, "create_job", create_job)

    created = await lifecycle_runtime_service.schedule_due_lifecycle_jobs(conn, batch_limit=25)

    assert created == 2
    assert "NOT EXISTS" in conn.fetch.await_args.args[0]
    assert create_job.await_count == 2
    first_kwargs = create_job.await_args_list[0].kwargs
    assert first_kwargs["kind"] == LIFECYCLE_SEND_KIND
    assert first_kwargs["queue_name"] == "default"
    assert first_kwargs["dedupe_key"] == "lifecycle:message:msg-1"
    assert first_kwargs["entity_type"] == "lifecycle_message"
    assert first_kwargs["entity_id"] == "msg-1"
    assert first_kwargs["payload_json"] == {"message_id": "msg-1"}


@pytest.mark.asyncio
async def test_lifecycle_send_handler_delivers_pending_message(monkeypatch):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "id": "msg-10",
        "user_id": "user-1",
        "campaign_key": "lead_no_quest",
        "trigger_data": {"quest_id": "quest-1"},
        "status": "pending",
        "error_message": None,
    })
    mark_sent = AsyncMock()
    monkeypatch.setattr(lifecycle_service, "resolve_delivery_recipient", AsyncMock(return_value={"email": "user@example.com", "username": "Alice"}))
    monkeypatch.setattr(lifecycle_service, "build_lifecycle_email", lambda campaign_key, trigger_data: ("Subject", "<p>Hello</p>"))
    monkeypatch.setattr(lifecycle_service, "mark_sent", mark_sent)
    monkeypatch.setattr(lifecycle_service, "record_delivery_error", AsyncMock())
    send = MagicMock()
    monkeypatch.setattr("app.services.email_service.send_lifecycle_nudge", send)

    handler = LifecycleSendHandler()
    context = MagicMock(job_id="job-10", worker_id="host:1")

    result = await handler.execute(conn, {"message_id": "msg-10"}, context)

    assert result["status"] == "succeeded"
    send.assert_called_once_with(
        to="user@example.com",
        username="Alice",
        subject="Subject",
        body_html="<p>Hello</p>",
    )
    mark_sent.assert_awaited_once_with(conn, "msg-10")


@pytest.mark.asyncio
async def test_lifecycle_send_handler_uses_trigger_data_email_for_lead_without_user(monkeypatch):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "id": "msg-lead",
        "user_id": "lead-1",
        "campaign_key": "lead_no_register",
        "trigger_data": {"email": "lead@example.com", "company_name": "Acme"},
        "status": "pending",
        "error_message": None,
    })
    monkeypatch.setattr(lifecycle_service, "mark_sent", AsyncMock())
    monkeypatch.setattr(lifecycle_service, "record_delivery_error", AsyncMock())
    send = MagicMock()
    monkeypatch.setattr("app.services.email_service.send_lifecycle_nudge", send)

    handler = LifecycleSendHandler()
    context = MagicMock(job_id="job-lead", worker_id="host:1")

    result = await handler.execute(conn, {"message_id": "msg-lead"}, context)

    assert result["status"] == "succeeded"
    send.assert_called_once()
    assert send.call_args.kwargs["to"] == "lead@example.com"
    assert send.call_args.kwargs["username"] == "Acme"


def test_lifecycle_send_handler_registered_in_registry():
    from app.jobs.registry import get_handler

    handler = get_handler(LIFECYCLE_SEND_KIND)
    assert isinstance(handler, LifecycleSendHandler)