from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from app.core.config import settings
from app.db.session import acquire_db_connection, close_db_pool, ensure_db_pool
from app.jobs.enums import QUEUE_OPS
from app.repositories import command_repository, job_repository


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify live admin runtime endpoints against a real local stack")
    parser.add_argument("--health-url", default="http://127.0.0.1:8001/health")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001/api/v1")
    parser.add_argument("--admin-username", default="admin")
    parser.add_argument(
        "--admin-password",
        default=os.getenv("OPS_SMOKE_ADMIN_PASSWORD") or settings.ADMIN_DEFAULT_PASSWORD,
    )
    parser.add_argument("--poll-seconds", type=int, default=45)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    return parser.parse_args()


def _json_request(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any] | list[Any] | str:
    payload = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=payload, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(json.dumps({"url": url, "status": exc.code, "detail": detail}, ensure_ascii=True)) from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _login_with_password_candidates(api_base_url: str, username: str, password_candidates: list[str]) -> dict[str, Any]:
    last_error: Exception | None = None
    for password in password_candidates:
        try:
            result = _json_request(
                f"{api_base_url}/auth/login",
                method="POST",
                body={"username": username, "password": password},
            )
        except RuntimeError as exc:
            last_error = exc
            continue
        if isinstance(result, dict) and result.get("access_token"):
            result["_verified_password"] = password
            return result
        last_error = RuntimeError("Login did not return an access_token")
    if last_error is not None:
        raise last_error
    raise RuntimeError("No admin password candidates were provided")


async def _create_live_command(*, actor_admin_id: str) -> tuple[str, str]:
    trace_id = f"trace-{uuid4().hex[:12]}"
    request_id = f"req-{uuid4().hex[:12]}"
    dedupe_key = f"verify-admin-runtime-{uuid4().hex}"

    await ensure_db_pool()
    async with acquire_db_connection() as conn:
        async with conn.transaction():
            command = await command_repository.create_command(
                conn,
                command_kind="ops.noop",
                dedupe_key=dedupe_key,
                requested_by_admin_id=actor_admin_id,
                request_ip="127.0.0.1",
                request_user_agent="verify-live-admin-runtime",
                request_id=request_id,
                trace_id=trace_id,
                payload_json={"source": "verify-live-admin-runtime", "kind": "ops.noop"},
            )
            job = await job_repository.create_job(
                conn,
                kind="ops.noop",
                queue_name=QUEUE_OPS,
                dedupe_key=dedupe_key,
                payload_json={"source": "verify-live-admin-runtime", "hello": "world"},
                command_id=command["id"],
                request_id=request_id,
                trace_id=trace_id,
                max_attempts=1,
            )

    return str(command["id"]), str(job["id"])


async def _await_completion(*, command_id: str, job_id: str, poll_seconds: int, poll_interval: float) -> dict[str, Any]:
    async with acquire_db_connection() as conn:
        final_command = None
        final_job = None
        for _ in range(int(poll_seconds / poll_interval)):
            await asyncio.sleep(poll_interval)
            final_command = await command_repository.get_command_by_id(conn, command_id)
            final_job = await job_repository.get_job_by_id(conn, job_id)
            if final_command and final_job:
                if str(final_command["status"]) in {"succeeded", "failed", "cancelled"} and str(final_job["status"]) in {"succeeded", "failed", "dead_letter"}:
                    break
        else:
            raise TimeoutError(
                json.dumps(
                    {
                        "message": "Timed out waiting for admin runtime verification command/job completion",
                        "command_id": command_id,
                        "job_id": job_id,
                        "command_status": None if final_command is None else str(final_command["status"]),
                        "job_status": None if final_job is None else str(final_job["status"]),
                    },
                    ensure_ascii=True,
                )
            )

        return {
            "command_status": str(final_command["status"]),
            "job_status": str(final_job["status"]),
        }


async def _run_verification(args: argparse.Namespace) -> dict[str, Any]:
    try:
        if not args.admin_password:
            raise RuntimeError("Admin password is required. Pass --admin-password or set OPS_SMOKE_ADMIN_PASSWORD/ADMIN_DEFAULT_PASSWORD.")

        health = _json_request(args.health_url)
        password_candidates: list[str] = []
        for candidate in [args.admin_password, settings.ADMIN_DEFAULT_PASSWORD, "admin"]:
            normalized = str(candidate or "").strip()
            if normalized and normalized not in password_candidates:
                password_candidates.append(normalized)

        login = _login_with_password_candidates(
            args.api_base_url,
            args.admin_username,
            password_candidates,
        )
        if not isinstance(login, dict) or not login.get("access_token"):
            raise RuntimeError("Login did not return an access_token")

        access_token = str(login["access_token"])
        auth_headers = {"Authorization": f"Bearer {access_token}"}

        command_id, job_id = await _create_live_command(actor_admin_id=args.admin_username)
        completion = await _await_completion(
            command_id=command_id,
            job_id=job_id,
            poll_seconds=args.poll_seconds,
            poll_interval=args.poll_interval,
        )

        command = _json_request(
            f"{args.api_base_url}/admin/commands/{command_id}",
            headers=auth_headers,
        )
        job = _json_request(
            f"{args.api_base_url}/admin/jobs/{job_id}",
            headers=auth_headers,
        )
        operations = _json_request(
            f"{args.api_base_url}/admin/operations?{urlencode({'action': 'ops.noop', 'actor': args.admin_username})}",
            headers=auth_headers,
        )
        heartbeats = _json_request(
            f"{args.api_base_url}/admin/runtime/heartbeats?{urlencode({'active_only': 'true', 'limit': 100})}",
            headers=auth_headers,
        )

        if not isinstance(command, dict) or command.get("id") != command_id:
            raise RuntimeError("Admin command endpoint did not return the expected command")
        if not isinstance(job, dict) or job.get("id") != job_id:
            raise RuntimeError("Admin job endpoint did not return the expected job")
        if not isinstance(operations, dict) or not any(item.get("command_id") == command_id for item in operations.get("items", [])):
            raise RuntimeError("Admin operations endpoint did not include the verified command")
        if not isinstance(heartbeats, dict):
            raise RuntimeError("Admin runtime heartbeats endpoint did not return JSON")

        runtimes = heartbeats.get("runtimes", [])
        worker_entries = [item for item in runtimes if item.get("runtime_kind") == "worker"]
        scheduler_entries = [item for item in runtimes if item.get("runtime_kind") == "scheduler"]
        if not worker_entries:
            raise RuntimeError("Admin runtime heartbeats did not expose any active worker")
        if not scheduler_entries:
            raise RuntimeError("Admin runtime heartbeats did not expose any active scheduler")
        if heartbeats.get("leader_count", 0) < 1:
            raise RuntimeError("Admin runtime heartbeats did not expose an active scheduler leader")
        if scheduler_entries[0].get("heartbeat_interval_seconds") is None:
            raise RuntimeError("Scheduler heartbeat entry is missing heartbeat_interval_seconds")
        if scheduler_entries[0].get("lease_expires_in_seconds") is None:
            raise RuntimeError("Scheduler heartbeat entry is missing lease_expires_in_seconds")
        if worker_entries[0].get("queue_name") != "ops":
            raise RuntimeError("Worker heartbeat entry is missing the expected queue_name")

        return {
            "health": health,
            "admin_username": args.admin_username,
            "verified_password": login.get("_verified_password"),
            "command_id": command_id,
            "job_id": job_id,
            "completion": completion,
            "command": {
                "status": command.get("status"),
                "job_count": len(command.get("jobs", [])),
                "job_statuses": [item.get("status") for item in command.get("jobs", [])],
            },
            "job": {
                "status": job.get("status"),
                "attempt_count": job.get("attempt_count"),
                "attempt_rows": len(job.get("attempts", [])),
                "command_id": job.get("command_id"),
            },
            "operations": {
                "total": operations.get("total"),
                "matched_command_ids": [item.get("command_id") for item in operations.get("items", [])],
            },
            "heartbeats": {
                "total": heartbeats.get("total"),
                "active_workers": heartbeats.get("active_workers"),
                "active_schedulers": heartbeats.get("active_schedulers"),
                "leader_runtime_id": heartbeats.get("leader_runtime_id"),
                "leader_count": heartbeats.get("leader_count"),
                "runtimes": runtimes[:5],
            },
        }
    finally:
        await close_db_pool()


def main() -> int:
    args = _parse_args()
    try:
        result = asyncio.run(_run_verification(args))
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=True, indent=2, default=str))
        return 1

    print(json.dumps(result, ensure_ascii=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())