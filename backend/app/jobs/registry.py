"""Handler registry for trust-layer jobs."""

from __future__ import annotations

from app.jobs.context import JobHandler
from app.jobs.handlers.email_send import EmailSendHandler
from app.jobs.handlers.event_lifecycle import EventFinalizeHandler
from app.jobs.handlers.lifecycle_send import LifecycleSendHandler
from app.jobs.handlers.ops_noop import OpsNoopHandler
from app.jobs.handlers.withdrawal_auto_approve import WithdrawalAutoApproveHandler


_HANDLERS: dict[str, JobHandler] = {
    OpsNoopHandler.kind: OpsNoopHandler(),
    WithdrawalAutoApproveHandler.kind: WithdrawalAutoApproveHandler(),
    EmailSendHandler.kind: EmailSendHandler(),
    LifecycleSendHandler.kind: LifecycleSendHandler(),
    EventFinalizeHandler.kind: EventFinalizeHandler(),
}


def get_handler(kind: str) -> JobHandler:
    try:
        return _HANDLERS[kind]
    except KeyError as exc:
        raise KeyError(f"Unknown job kind: {kind}") from exc


def get_registered_handlers() -> dict[str, JobHandler]:
    return dict(_HANDLERS)
