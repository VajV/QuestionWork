from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

try:
    from dotenv import load_dotenv

    load_dotenv(_BACKEND / ".env")
except ImportError:
    pass

from app.core.config import settings
from app.db.session import acquire_db_connection, close_db_pool, ensure_db_pool


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a short post-deploy smoke for the withdrawal auto-approve cutover"
    )
    parser.add_argument("--health-url", default="http://127.0.0.1:8001/health")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001/api/v1")
    parser.add_argument("--admin-username", default="admin")
    parser.add_argument("--admin-password", default=os.getenv("OPS_SMOKE_ADMIN_PASSWORD"))
    parser.add_argument("--recent-minutes", type=int, default=180)
    parser.add_argument("--job-limit", type=int, default=10)
    parser.add_argument("--require-flag-enabled", action="store_true", default=True)
    parser.add_argument("--allow-flag-disabled", dest="require_flag_enabled", action="store_false")
    parser.add_argument("--require-recent-job", action="store_true")
    parser.add_argument("--require-successful-job", action="store_true")
    parser.add_argument("--require-audit-linkage", action="store_true")
    return parser.parse_args()


def _json_request(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, body: dict[str, Any] | None = None) -> Any:
    payload = None
    request_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = Request(url, data=payload, headers=request_headers, method=method)
    with urlopen(request, timeout=10) as response:
        raw = response.read().decode("utf-8")
    if not raw:
        return None
    return json.loads(raw)


def _health_check(url: str) -> dict[str, Any]:
    data = _json_request(url)
    if isinstance(data, dict):
        return data
    return {"raw": data}


def _login_for_admin_token(*, api_base_url: str, username: str, password: str) -> str:
    response = _json_request(
        f"{api_base_url}/auth/login",
        method="POST",
        body={"username": username, "password": password},
    )
    token = response.get("access_token")
    if not token:
        raise RuntimeError("Admin login succeeded but access_token is missing")
    return str(token)


def _fetch_active_heartbeats(*, api_base_url: str, token: str) -> dict[str, Any]:
    return _json_request(
        f"{api_base_url}/admin/runtime/heartbeats?active_only=true&limit=100",
        headers={"Authorization": f"Bearer {token}"},
    )


def _find_legacy_processes() -> list[dict[str, Any]]:
    if platform.system().lower().startswith("win"):
        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'process_withdrawals\\.py' } | Select-Object ProcessId, Name, CommandLine | ConvertTo-Json -Compress",
        ]
    else:
        command = ["ps", "-eo", "pid=,comm=,args="]

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    stdout = (result.stdout or "").strip()
    if result.returncode != 0:
        return [{"error": (result.stderr or "").strip() or "process query failed"}]

    if platform.system().lower().startswith("win"):
        if not stdout:
            return []
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            return [{"raw": stdout}]
        if isinstance(parsed, list):
            return parsed
        return [parsed]

    matches: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if "process_withdrawals.py" not in line:
            continue
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        matches.append({"pid": parts[0], "name": parts[1], "command_line": parts[2]})
    return matches


async def _fetch_recent_withdrawal_jobs(*, recent_minutes: int, job_limit: int) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=recent_minutes)
    await ensure_db_pool()
    try:
        async with acquire_db_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    j.id,
                    j.status,
                    j.command_id,
                    j.entity_id,
                    j.attempt_count,
                    j.queue_publish_attempts,
                    j.created_at,
                    j.started_at,
                    j.finished_at,
                    j.last_error_code,
                    j.last_error,
                    j.request_id,
                    j.trace_id,
                    EXISTS(
                        SELECT 1
                        FROM admin_logs al
                        WHERE al.job_id = j.id
                    ) AS has_admin_log
                FROM background_jobs j
                WHERE j.kind = 'money.withdrawal.auto_approve'
                  AND j.created_at >= $1
                ORDER BY j.created_at DESC
                LIMIT $2
                """,
                cutoff,
                job_limit,
            )
            return [
                {
                    "id": str(row["id"]),
                    "status": row["status"],
                    "command_id": str(row["command_id"]) if row["command_id"] is not None else None,
                    "entity_id": str(row["entity_id"]) if row["entity_id"] is not None else None,
                    "attempt_count": int(row["attempt_count"]),
                    "queue_publish_attempts": int(row["queue_publish_attempts"]),
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                    "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
                    "last_error_code": row["last_error_code"],
                    "last_error": row["last_error"],
                    "request_id": row["request_id"],
                    "trace_id": row["trace_id"],
                    "has_admin_log": bool(row["has_admin_log"]),
                }
                for row in rows
            ]
    finally:
        await close_db_pool()


def _evaluate_checks(
    *,
    require_flag_enabled: bool,
    require_recent_job: bool,
    require_successful_job: bool,
    require_audit_linkage: bool,
    heartbeats: dict[str, Any],
    legacy_processes: list[dict[str, Any]],
    recent_jobs: list[dict[str, Any]],
) -> dict[str, bool]:
    runtimes = heartbeats.get("runtimes", []) if isinstance(heartbeats, dict) else []
    active_runtime_kinds = {str(runtime.get("runtime_kind")) for runtime in runtimes if not runtime.get("is_stale")}
    successful_jobs = [job for job in recent_jobs if job.get("status") == "succeeded"]
    linked_successful_jobs = [job for job in successful_jobs if job.get("has_admin_log")]

    checks = {
        "flag_enabled": bool(settings.WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED),
        "worker_heartbeat_active": "worker" in active_runtime_kinds,
        "scheduler_heartbeat_active": "scheduler" in active_runtime_kinds,
        "legacy_process_not_running": len(legacy_processes) == 0,
        "recent_job_present": len(recent_jobs) > 0,
        "successful_job_present": len(successful_jobs) > 0,
        "successful_job_has_audit_linkage": len(linked_successful_jobs) > 0,
    }

    if not require_flag_enabled:
        checks["flag_enabled"] = True
    if not require_recent_job:
        checks["recent_job_present"] = True
    if not require_successful_job:
        checks["successful_job_present"] = True
    if not require_audit_linkage:
        checks["successful_job_has_audit_linkage"] = True
    return checks


def main() -> int:
    args = _parse_args()
    admin_password = args.admin_password or settings.ADMIN_DEFAULT_PASSWORD
    if not admin_password:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "Admin password is required. Pass --admin-password or set OPS_SMOKE_ADMIN_PASSWORD/ADMIN_DEFAULT_PASSWORD.",
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 1

    try:
        health = _health_check(args.health_url)
        token = _login_for_admin_token(
            api_base_url=args.api_base_url,
            username=args.admin_username,
            password=admin_password,
        )
        heartbeats = _fetch_active_heartbeats(api_base_url=args.api_base_url, token=token)
        legacy_processes = _find_legacy_processes()
        recent_jobs = asyncio.run(
            _fetch_recent_withdrawal_jobs(
                recent_minutes=args.recent_minutes,
                job_limit=args.job_limit,
            )
        )
        checks = _evaluate_checks(
            require_flag_enabled=args.require_flag_enabled,
            require_recent_job=args.require_recent_job,
            require_successful_job=args.require_successful_job,
            require_audit_linkage=args.require_audit_linkage,
            heartbeats=heartbeats,
            legacy_processes=legacy_processes,
            recent_jobs=recent_jobs,
        )
    except (HTTPError, URLError, RuntimeError, OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=True, indent=2))
        return 1

    result = {
        "status": "ok" if all(checks.values()) else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health": health,
        "checks": checks,
        "heartbeats": heartbeats,
        "legacy_processes": legacy_processes,
        "recent_withdrawal_jobs": recent_jobs,
    }
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if all(checks.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())