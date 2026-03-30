"""Background job handlers for event lifecycle automation."""

from __future__ import annotations

from typing import Any

from app.jobs.context import JobContext
from app.jobs.enums import QUEUE_OPS
from app.services import event_service

EVENT_FINALIZE_KIND = "event_finalize"


class EventFinalizeHandler:
    kind = EVENT_FINALIZE_KIND
    queue_name = QUEUE_OPS
    max_attempts = 3
    transaction_isolation = "default"

    def backoff_seconds(self, attempt_no: int, error_code: str | None) -> int:
        return attempt_no * 15

    def is_retryable(self, error: Exception) -> bool:
        return not isinstance(error, ValueError)

    async def execute(self, conn: Any, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        event_id = str(payload.get("event_id") or "").strip()
        if not event_id:
            raise ValueError("event_id is required for event finalize jobs")

        async with conn.transaction():
            result = await event_service.finalize_event(conn, event_id=event_id)

        return {
            "kind": self.kind,
            "status": "succeeded",
            "event_id": event_id,
            "job_id": context.job_id,
            **result,
        }
