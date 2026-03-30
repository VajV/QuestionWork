"""Internal no-op job handler used to validate the job runtime."""

from __future__ import annotations

from typing import Any

from app.jobs.context import JobContext
from app.jobs.enums import QUEUE_OPS


class OpsNoopHandler:
    kind = "ops.noop"
    queue_name = QUEUE_OPS
    max_attempts = 1
    transaction_isolation = "default"

    def backoff_seconds(self, attempt_no: int, error_code: str | None) -> int:
        return 0

    def is_retryable(self, error: Exception) -> bool:
        return False

    async def execute(self, conn: Any, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "worker_id": context.worker_id,
            "trace_id": context.trace_id,
            "request_id": context.request_id,
            "payload": payload,
        }
