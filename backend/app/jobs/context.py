"""Typed execution context and handler contract for trust-layer jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol


HeartbeatCallable = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class JobContext:
    worker_id: str
    job_id: str | None = None
    trace_id: str | None = None
    request_id: str | None = None
    heartbeat: HeartbeatCallable | None = None
    now_factory: Callable[[], datetime] = field(default=lambda: datetime.now(timezone.utc))


class JobHandler(Protocol):
    kind: str
    queue_name: str
    max_attempts: int
    transaction_isolation: str

    def backoff_seconds(self, attempt_no: int, error_code: str | None) -> int: ...
    def is_retryable(self, error: Exception) -> bool: ...
    async def execute(self, conn: Any, payload: dict[str, Any], context: JobContext) -> dict[str, Any]: ...
