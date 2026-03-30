"""ARQ bootstrap helpers for the trust-layer runtime."""

from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID

from arq.connections import ArqRedis, RedisSettings, create_pool

from app.core.config import settings
from app.core.redis_client import get_arq_redis_url
from app.jobs.enums import QUEUE_DEFAULT


def build_redis_settings(redis_url: str | None = None) -> RedisSettings:
    return RedisSettings.from_dsn(redis_url or get_arq_redis_url())


def validate_job_message(payload: dict[str, Any]) -> dict[str, str | None]:
    allowed_keys = {"job_id", "trace_id", "request_id"}
    unknown_keys = set(payload) - allowed_keys
    if unknown_keys:
        raise ValueError(f"Unsupported job payload keys: {sorted(unknown_keys)}")

    job_id_raw = payload.get("job_id")
    if job_id_raw is None:
        raise ValueError("job payload must include non-empty job_id")
    if not isinstance(job_id_raw, (str, UUID)):
        raise ValueError("job payload must include non-empty job_id")

    job_id = str(job_id_raw).strip()
    if not job_id:
        raise ValueError("job payload must include non-empty job_id")

    trace_id = payload.get("trace_id")
    request_id = payload.get("request_id")
    if trace_id is not None and not isinstance(trace_id, str):
        raise ValueError("trace_id must be a string when provided")
    if request_id is not None and not isinstance(request_id, str):
        raise ValueError("request_id must be a string when provided")

    return {
        "job_id": job_id,
        "trace_id": trace_id,
        "request_id": request_id,
    }


async def create_arq_pool(redis_url: str | None = None) -> ArqRedis:
    return await create_pool(build_redis_settings(redis_url))


async def enqueue_job_message(
    redis: ArqRedis,
    *,
    job_id: str,
    function_name: str = "process_job_message",
    queue_name: str | None = None,
    trace_id: str | None = None,
    request_id: str | None = None,
) -> Any:
    payload = validate_job_message(
        {
            "job_id": job_id,
            "trace_id": trace_id,
            "request_id": request_id,
        }
    )
    return await redis.enqueue_job(function_name, payload, _queue_name=queue_name or settings.JOB_DEFAULT_QUEUE_NAME)


def build_worker_settings(
    *,
    functions: Sequence[Any],
    queue_name: str = QUEUE_DEFAULT,
    on_startup: Any = None,
    on_shutdown: Any = None,
) -> dict[str, Any]:
    settings_dict: dict[str, Any] = {
        "functions": list(functions),
        "queue_name": queue_name,
        "redis_settings": build_redis_settings(),
    }
    if on_startup is not None:
        settings_dict["on_startup"] = on_startup
    if on_shutdown is not None:
        settings_dict["on_shutdown"] = on_shutdown
    return settings_dict
