from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any
from urllib.request import urlopen
from uuid import uuid4

from app.db.session import acquire_db_connection, close_db_pool, ensure_db_pool
from app.jobs.enums import QUEUE_OPS
from app.repositories import command_repository, job_repository


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a live trust-layer smoke test with ops.noop")
    parser.add_argument("--health-url", default="http://127.0.0.1:8001/health")
    parser.add_argument("--poll-seconds", type=int, default=45)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    return parser.parse_args()


async def _fetch_attempts(conn, *, job_id: str) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT attempt_no, worker_id, status, started_at, finished_at, error_code, error_text
        FROM background_job_attempts
        WHERE job_id = $1
        ORDER BY attempt_no ASC
        """,
        job_id,
    )
    return [
        {
            "attempt_no": int(row["attempt_no"]),
            "worker_id": row["worker_id"],
            "status": row["status"],
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
            "error_code": row["error_code"],
            "error_text": row["error_text"],
        }
        for row in rows
    ]


async def _fetch_heartbeats(conn) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT runtime_kind, runtime_id, hostname, pid, started_at, last_seen_at, meta_json
        FROM runtime_heartbeats
        WHERE runtime_kind IN ('worker', 'scheduler')
        ORDER BY runtime_kind, last_seen_at DESC
        """
    )
    return [
        {
            "runtime_kind": row["runtime_kind"],
            "runtime_id": row["runtime_id"],
            "hostname": row["hostname"],
            "pid": int(row["pid"]),
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
            "meta_json": row["meta_json"],
        }
        for row in rows[:6]
    ]


def _health_check(url: str) -> str:
    with urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


async def _run_smoke(*, health_url: str, poll_seconds: int, poll_interval: float) -> dict[str, Any]:
    health = _health_check(health_url)
    trace_id = f"trace-{uuid4().hex[:12]}"
    request_id = f"req-{uuid4().hex[:12]}"
    dedupe_key = f"smoke-{uuid4().hex}"

    await ensure_db_pool()
    try:
        async with acquire_db_connection() as conn:
            async with conn.transaction():
                command = await command_repository.create_command(
                    conn,
                    command_kind="ops.noop",
                    dedupe_key=dedupe_key,
                    request_id=request_id,
                    trace_id=trace_id,
                    request_ip="127.0.0.1",
                    request_user_agent="trust-layer-smoke",
                    payload_json={"source": "live-smoke", "kind": "ops.noop"},
                )
                job = await job_repository.create_job(
                    conn,
                    kind="ops.noop",
                    queue_name=QUEUE_OPS,
                    dedupe_key=dedupe_key,
                    payload_json={"source": "live-smoke", "hello": "world"},
                    command_id=command["id"],
                    request_id=request_id,
                    trace_id=trace_id,
                    max_attempts=1,
                )

            command_id = str(command["id"])
            job_id = str(job["id"])
            command_status_history = [str(command["status"])]
            job_status_history = [str(job["status"])]

            final_command = command
            final_job = job
            attempts: list[dict[str, Any]] = []
            heartbeats: list[dict[str, Any]] = []

            for _ in range(int(poll_seconds / poll_interval)):
                await asyncio.sleep(poll_interval)
                final_command = await command_repository.get_command_by_id(conn, command_id)
                final_job = await job_repository.get_job_by_id(conn, job_id)

                command_status = str(final_command["status"])
                job_status = str(final_job["status"])

                if command_status_history[-1] != command_status:
                    command_status_history.append(command_status)
                if job_status_history[-1] != job_status:
                    job_status_history.append(job_status)

                if command_status in {"succeeded", "failed", "cancelled"} and job_status in {"succeeded", "failed", "dead_letter"}:
                    attempts = await _fetch_attempts(conn, job_id=job_id)
                    heartbeats = await _fetch_heartbeats(conn)
                    break
            else:
                attempts = await _fetch_attempts(conn, job_id=job_id)
                heartbeats = await _fetch_heartbeats(conn)
                raise TimeoutError(
                    json.dumps(
                        {
                            "message": "Timed out waiting for ops.noop completion",
                            "command_id": command_id,
                            "job_id": job_id,
                            "command_status_history": command_status_history,
                            "job_status_history": job_status_history,
                            "command": {
                                "status": str(final_command["status"]),
                                "started_at": final_command["started_at"].isoformat() if final_command["started_at"] else None,
                                "finished_at": final_command["finished_at"].isoformat() if final_command["finished_at"] else None,
                                "error_code": final_command["error_code"],
                                "error_text": final_command["error_text"],
                            },
                            "job": {
                                "status": str(final_job["status"]),
                                "queue_publish_attempts": int(final_job["queue_publish_attempts"]),
                                "enqueued_at": final_job["enqueued_at"].isoformat() if final_job["enqueued_at"] else None,
                                "started_at": final_job["started_at"].isoformat() if final_job["started_at"] else None,
                                "last_heartbeat_at": final_job["last_heartbeat_at"].isoformat() if final_job["last_heartbeat_at"] else None,
                                "finished_at": final_job["finished_at"].isoformat() if final_job["finished_at"] else None,
                                "last_enqueue_error": final_job["last_enqueue_error"],
                                "last_error_code": final_job["last_error_code"],
                                "last_error": final_job["last_error"],
                                "locked_by": final_job["locked_by"],
                            },
                            "attempts": attempts,
                            "heartbeats": heartbeats,
                        },
                        ensure_ascii=True,
                    )
                )

            return {
                "health": health,
                "command_id": command_id,
                "job_id": job_id,
                "command_status_history": command_status_history,
                "job_status_history": job_status_history,
                "command": {
                    "status": str(final_command["status"]),
                    "started_at": final_command["started_at"].isoformat() if final_command["started_at"] else None,
                    "finished_at": final_command["finished_at"].isoformat() if final_command["finished_at"] else None,
                    "result_json": final_command["result_json"],
                    "error_code": final_command["error_code"],
                    "error_text": final_command["error_text"],
                },
                "job": {
                    "status": str(final_job["status"]),
                    "locked_by": final_job["locked_by"],
                    "lock_token": final_job["lock_token"],
                    "attempt_count": int(final_job["attempt_count"]),
                    "queue_publish_attempts": int(final_job["queue_publish_attempts"]),
                    "enqueued_at": final_job["enqueued_at"].isoformat() if final_job["enqueued_at"] else None,
                    "started_at": final_job["started_at"].isoformat() if final_job["started_at"] else None,
                    "last_heartbeat_at": final_job["last_heartbeat_at"].isoformat() if final_job["last_heartbeat_at"] else None,
                    "finished_at": final_job["finished_at"].isoformat() if final_job["finished_at"] else None,
                    "last_enqueue_error": final_job["last_enqueue_error"],
                    "last_error_code": final_job["last_error_code"],
                    "last_error": final_job["last_error"],
                },
                "attempts": attempts,
                "heartbeats": heartbeats,
            }
    finally:
        await close_db_pool()


def main() -> int:
    args = _parse_args()
    try:
        result = asyncio.run(
            _run_smoke(
                health_url=args.health_url,
                poll_seconds=args.poll_seconds,
                poll_interval=args.poll_interval,
            )
        )
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=True, indent=2, default=str))
        return 1

    print(json.dumps(result, ensure_ascii=True, indent=2, default=str))
    if result["command"]["status"] != "succeeded" or result["job"]["status"] != "succeeded":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())