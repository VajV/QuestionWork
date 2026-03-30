"""Tests for email pipeline: handler, runtime service, outbox dispatcher, email_service templates."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.handlers.email_send import EmailSendHandler, EMAIL_SEND_KIND
from app.services import email_outbox_service, email_runtime_service


# ── EmailSendHandler ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_email_send_handler_delivers_pending_outbox_entry(monkeypatch):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "id": "outbox-1",
        "email_address": "user@example.com",
        "template_key": "welcome",
        "template_params": {"username": "Alice"},
        "status": "pending",
        "attempt_count": 0,
    })
    conn.execute = AsyncMock()
    deliver = MagicMock()
    monkeypatch.setattr(email_outbox_service, "_deliver", deliver)

    handler = EmailSendHandler()
    context = MagicMock(job_id="job-1", worker_id="host:1")

    result = await handler.execute(conn, {"outbox_id": "outbox-1"}, context)

    assert result["status"] == "succeeded"
    assert result["outbox_id"] == "outbox-1"
    assert result["template_key"] == "welcome"
    deliver.assert_called_once_with(
        template_key="welcome",
        email_address="user@example.com",
        params={"username": "Alice"},
    )
    conn.execute.assert_awaited_once()
    assert "sent" in conn.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_email_send_handler_ignores_already_sent_entries(monkeypatch):
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "id": "outbox-2",
        "email_address": "user@example.com",
        "template_key": "welcome",
        "template_params": {},
        "status": "sent",
        "attempt_count": 1,
    })

    handler = EmailSendHandler()
    context = MagicMock(job_id="job-2", worker_id="host:1")

    result = await handler.execute(conn, {"outbox_id": "outbox-2"}, context)

    assert result["status"] == "ignored"
    assert result["reason"] == "already-sent"


@pytest.mark.asyncio
async def test_email_send_handler_raises_on_missing_outbox_id():
    handler = EmailSendHandler()
    context = MagicMock(job_id="job-3", worker_id="host:1")
    conn = AsyncMock()

    with pytest.raises(ValueError, match="outbox_id is required"):
        await handler.execute(conn, {}, context)


@pytest.mark.asyncio
async def test_email_send_handler_raises_on_not_found():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)

    handler = EmailSendHandler()
    context = MagicMock(job_id="job-4", worker_id="host:1")

    with pytest.raises(ValueError, match="not found"):
        await handler.execute(conn, {"outbox_id": "missing"}, context)


@pytest.mark.asyncio
async def test_email_send_handler_updates_attempt_on_failure(monkeypatch):
    import smtplib

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={
        "id": "outbox-3",
        "email_address": "user@example.com",
        "template_key": "welcome",
        "template_params": {"username": "Bob"},
        "status": "pending",
        "attempt_count": 0,
    })
    conn.execute = AsyncMock()
    monkeypatch.setattr(email_outbox_service, "_deliver", MagicMock(side_effect=smtplib.SMTPException("test")))

    handler = EmailSendHandler()
    context = MagicMock(job_id="job-5", worker_id="host:1")

    with pytest.raises(smtplib.SMTPException):
        await handler.execute(conn, {"outbox_id": "outbox-3"}, context)

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args.args
    assert args[1] == "outbox-3"  # outbox_id
    assert args[2] == 1  # attempt_count
    assert args[3] == "pending"  # status (still retryable)


def test_email_send_handler_retryable_for_smtp():
    import smtplib
    handler = EmailSendHandler()
    assert handler.is_retryable(smtplib.SMTPException("fail"))
    assert handler.is_retryable(OSError("conn reset"))
    assert handler.is_retryable(TimeoutError("timed out"))
    assert not handler.is_retryable(ValueError("bad data"))


def test_email_send_handler_backoff():
    handler = EmailSendHandler()
    assert handler.backoff_seconds(1, None) == 60
    assert handler.backoff_seconds(2, None) == 120
    assert handler.backoff_seconds(3, None) == 180


def test_email_send_handler_protocol_compliance():
    handler = EmailSendHandler()
    assert handler.kind == EMAIL_SEND_KIND
    assert handler.kind == "email.send"
    assert handler.queue_name == "default"
    assert handler.max_attempts == 3
    assert handler.transaction_isolation == "default"


# ── Registry ──────────────────────────────────────────────────────────────────


def test_email_send_handler_registered_in_registry():
    from app.jobs.registry import get_handler
    handler = get_handler("email.send")
    assert isinstance(handler, EmailSendHandler)


# ── email_runtime_service ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_schedule_email_outbox_jobs_creates_jobs_for_pending_entries(monkeypatch):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {"id": "outbox-10"},
        {"id": "outbox-11"},
    ])
    create_job = AsyncMock()
    monkeypatch.setattr(email_runtime_service.job_repository, "create_job", create_job)

    created = await email_runtime_service.schedule_email_outbox_jobs(conn)

    assert created == 2
    assert "NOT EXISTS" in conn.fetch.await_args.args[0]
    assert create_job.await_count == 2
    first_kwargs = create_job.await_args_list[0].kwargs
    assert first_kwargs["kind"] == EMAIL_SEND_KIND
    assert first_kwargs["queue_name"] == "default"
    assert first_kwargs["dedupe_key"] == "email:outbox:outbox-10"
    assert first_kwargs["entity_type"] == "email_outbox"
    assert first_kwargs["entity_id"] == "outbox-10"
    assert first_kwargs["payload_json"] == {"outbox_id": "outbox-10"}


@pytest.mark.asyncio
async def test_schedule_email_outbox_jobs_returns_zero_when_no_pending(monkeypatch):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(email_runtime_service.job_repository, "create_job", AsyncMock())

    created = await email_runtime_service.schedule_email_outbox_jobs(conn)

    assert created == 0


# ── email_outbox_service dispatcher ──────────────────────────────────────────


def test_outbox_dispatcher_supports_all_template_keys(monkeypatch):
    # Patch _enabled to return True so dispatcher actually calls functions
    monkeypatch.setattr("app.services.email_service._enabled", lambda: True)
    # Patch _send so nothing actually goes out
    monkeypatch.setattr("app.services.email_service._send", lambda msg: None)

    expected_keys = [
        "quest_assigned",
        "quest_completed",
        "welcome",
        "password_reset",
        "review_received",
        "withdrawal_status",
        "lifecycle_nudge",
    ]
    for key in expected_keys:
        # Should not raise
        email_outbox_service._deliver(
            template_key=key,
            email_address="test@example.com",
            params={
                "username": "Test",
                "quest_title": "Test Quest",
                "xp_gained": 100,
                "reset_link": "https://example.com/reset",
                "reviewer_username": "Reviewer",
                "rating": 5,
                "comment": "Great!",
                "amount": "100",
                "currency": "RUB",
                "withdrawal_status": "approved",
                "subject": "Test",
                "body_html": "<p>Test</p>",
            },
        )


def test_outbox_dispatcher_logs_unknown_key(monkeypatch):
    monkeypatch.setattr("app.services.email_service._enabled", lambda: True)
    # Should not raise for unknown keys, just log warning
    email_outbox_service._deliver(
        template_key="unknown_template",
        email_address="test@example.com",
        params={},
    )


# ── email_service new templates ──────────────────────────────────────────────


def test_send_welcome_does_nothing_when_disabled(monkeypatch):
    monkeypatch.setattr("app.services.email_service._enabled", lambda: False)
    from app.services.email_service import send_welcome
    # Should return without error
    send_welcome(to="test@example.com", username="TestUser")


def test_send_password_reset_does_nothing_when_disabled(monkeypatch):
    monkeypatch.setattr("app.services.email_service._enabled", lambda: False)
    from app.services.email_service import send_password_reset
    send_password_reset(to="test@example.com", username="TestUser", reset_link="https://example.com/reset")


def test_send_withdrawal_status_does_nothing_when_disabled(monkeypatch):
    monkeypatch.setattr("app.services.email_service._enabled", lambda: False)
    from app.services.email_service import send_withdrawal_status
    send_withdrawal_status(to="test@example.com", username="TestUser", amount="100", currency="RUB", status="approved")


def test_send_welcome_builds_correct_html(monkeypatch):
    monkeypatch.setattr("app.services.email_service._enabled", lambda: True)
    sent_messages = []
    monkeypatch.setattr("app.services.email_service._send", lambda msg: sent_messages.append(msg))

    from app.services.email_service import send_welcome
    send_welcome(to="user@test.com", username="Alice")

    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert msg["To"] == "user@test.com"
    assert "Добро пожаловать" in msg["Subject"]


def test_send_password_reset_escapes_link(monkeypatch):
    monkeypatch.setattr("app.services.email_service._enabled", lambda: True)
    sent_messages = []
    monkeypatch.setattr("app.services.email_service._send", lambda msg: sent_messages.append(msg))

    from app.services.email_service import send_password_reset
    send_password_reset(
        to="user@test.com",
        username="<script>alert(1)</script>",
        reset_link="https://example.com/reset?token=abc",
    )

    assert len(sent_messages) == 1
    msg = sent_messages[0]
    # HTML part should have escaped username
    html_part = msg.get_payload()[1].get_payload(decode=True).decode("utf-8")
    assert "<script>" not in html_part
    assert "&lt;script&gt;" in html_part


def test_send_withdrawal_status_shows_correct_labels(monkeypatch):
    monkeypatch.setattr("app.services.email_service._enabled", lambda: True)
    sent_messages = []
    monkeypatch.setattr("app.services.email_service._send", lambda msg: sent_messages.append(msg))

    from app.services.email_service import send_withdrawal_status
    send_withdrawal_status(to="user@test.com", username="Bob", amount="500", currency="RUB", status="approved")

    assert len(sent_messages) == 1
    assert "одобрен" in sent_messages[0]["Subject"]
