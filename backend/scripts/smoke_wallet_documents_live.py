from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

try:
    from dotenv import load_dotenv

    load_dotenv(_BACKEND / ".env")
except ImportError:
    pass

from app.core.security import get_password_hash
from app.db.session import acquire_db_connection, close_db_pool, ensure_db_pool


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a live smoke test for wallet receipt and statement downloads"
    )
    parser.add_argument("--health-url", default="http://127.0.0.1:8001/health")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8001/api/v1")
    parser.add_argument("--password", default="Smoke123!")
    return parser.parse_args()


def _request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[bytes, dict[str, str], int]:
    payload = None
    request_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = Request(url, data=payload, headers=request_headers, method=method)
    with urlopen(request, timeout=15) as response:
        return response.read(), dict(response.headers.items()), int(response.status)


def _header_value(headers: dict[str, str], name: str) -> str:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return ""


def _json_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    raw, _, _ = _request(url, method=method, headers=headers, body=body)
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def _health_check(url: str) -> dict[str, Any]:
    payload = _json_request(url)
    if isinstance(payload, dict):
        return payload
    return {"raw": payload}


def _login(api_base_url: str, *, username: str, password: str) -> dict[str, Any]:
    return _json_request(
        f"{api_base_url}/auth/login",
        method="POST",
        body={"username": username, "password": password},
    )


async def _seed_smoke_rows(
    *,
    client_username: str,
    freelancer_username: str,
    password: str,
    suffix: str,
) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    client_id = f"user_smoke_client_{suffix}"
    freelancer_id = f"user_smoke_freelancer_{suffix}"
    quest_id = f"quest_smoke_{suffix}"
    wallet_id = f"wallet_smoke_{suffix}"
    tx_income_id = f"tx_income_{suffix}"
    tx_withdraw_id = f"tx_withdraw_{suffix}"
    password_hash = get_password_hash(password)

    await ensure_db_pool()
    try:
        async with acquire_db_connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO users (
                        id, username, email, password_hash, role, level, grade, xp, xp_to_next,
                        stats_int, stats_dex, stats_cha, stat_points, badges, bio, skills, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, 1, 'novice', 0, 100,
                        10, 10, 10, 0, '[]', NULL, '[]', $6, $6
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        username = EXCLUDED.username,
                        email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        role = EXCLUDED.role,
                        updated_at = EXCLUDED.updated_at
                    """,
                    client_id,
                    client_username,
                    f"{client_username}@example.com",
                    password_hash,
                    "client",
                    now,
                )
                await conn.execute(
                    """
                    INSERT INTO users (
                        id, username, email, password_hash, role, level, grade, xp, xp_to_next,
                        stats_int, stats_dex, stats_cha, stat_points, badges, bio, skills, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, 1, 'novice', 0, 100,
                        10, 10, 10, 0, '[]', NULL, '[]', $6, $6
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        username = EXCLUDED.username,
                        email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        role = EXCLUDED.role,
                        updated_at = EXCLUDED.updated_at
                    """,
                    freelancer_id,
                    freelancer_username,
                    f"{freelancer_username}@example.com",
                    password_hash,
                    "freelancer",
                    now,
                )
                await conn.execute(
                    """
                    INSERT INTO quests (
                        id, client_id, client_username, title, description, required_grade,
                        skills, budget, currency, xp_reward, status, assigned_to,
                        created_at, updated_at, completed_at, is_urgent,
                        required_portfolio, revision_count, platform_fee_percent
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6,
                        $7::jsonb, $8, $9, $10, $11, $12,
                        $13, $13, $13, FALSE,
                        FALSE, 0, $14
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        client_id = EXCLUDED.client_id,
                        client_username = EXCLUDED.client_username,
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        assigned_to = EXCLUDED.assigned_to,
                        status = EXCLUDED.status,
                        budget = EXCLUDED.budget,
                        currency = EXCLUDED.currency,
                        xp_reward = EXCLUDED.xp_reward,
                        completed_at = EXCLUDED.completed_at,
                        updated_at = EXCLUDED.updated_at,
                        platform_fee_percent = EXCLUDED.platform_fee_percent
                    """,
                    quest_id,
                    client_id,
                    client_username,
                    f"Live wallet export smoke {suffix}",
                    "Autogenerated quest for receipt and statement smoke validation.",
                    "novice",
                    json.dumps(["smoke", "invoice"]),
                    Decimal("133.30"),
                    "RUB",
                    120,
                    "confirmed",
                    freelancer_id,
                    now,
                    Decimal("10.00"),
                )
                await conn.execute(
                    """
                    INSERT INTO wallets (id, user_id, currency, balance, version, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, 1, $5, $5)
                    ON CONFLICT (user_id, currency) DO UPDATE SET
                        balance = EXCLUDED.balance,
                        updated_at = EXCLUDED.updated_at
                    """,
                    wallet_id,
                    freelancer_id,
                    "RUB",
                    Decimal("100.00"),
                    now,
                )
                await conn.execute(
                    """
                    INSERT INTO transactions (id, user_id, quest_id, amount, currency, type, status, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (id) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        quest_id = EXCLUDED.quest_id,
                        amount = EXCLUDED.amount,
                        currency = EXCLUDED.currency,
                        type = EXCLUDED.type,
                        status = EXCLUDED.status,
                        created_at = EXCLUDED.created_at
                    """,
                    tx_income_id,
                    freelancer_id,
                    quest_id,
                    Decimal("120.00"),
                    "RUB",
                    "income",
                    "completed",
                    now,
                )
                await conn.execute(
                    """
                    INSERT INTO transactions (id, user_id, quest_id, amount, currency, type, status, created_at)
                    VALUES ($1, $2, NULL, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        quest_id = EXCLUDED.quest_id,
                        amount = EXCLUDED.amount,
                        currency = EXCLUDED.currency,
                        type = EXCLUDED.type,
                        status = EXCLUDED.status,
                        created_at = EXCLUDED.created_at
                    """,
                    tx_withdraw_id,
                    freelancer_id,
                    Decimal("20.00"),
                    "RUB",
                    "withdrawal",
                    "pending",
                    now,
                )
    finally:
        await close_db_pool()

    return {
        "client_id": client_id,
        "freelancer_id": freelancer_id,
        "quest_id": quest_id,
        "receipt_transaction_id": tx_income_id,
        "statement_transaction_id": tx_withdraw_id,
        "statement_date": now.date().isoformat(),
    }


def _validate_binary_pdf(name: str, body: bytes, headers: dict[str, str], status: int) -> dict[str, Any]:
    if status != 200:
        raise RuntimeError(f"{name} returned unexpected status {status}")
    if not body.startswith(b"%PDF"):
        raise RuntimeError(f"{name} did not return PDF bytes")
    return {
        "status": status,
        "content_type": _header_value(headers, "Content-Type"),
        "content_disposition": _header_value(headers, "Content-Disposition"),
        "size_bytes": len(body),
    }


def _validate_csv(body: bytes, headers: dict[str, str], status: int, *, quest_id: str) -> dict[str, Any]:
    if status != 200:
        raise RuntimeError(f"statement csv returned unexpected status {status}")
    text = body.decode("utf-8")
    expected_header = "transaction_id,created_at,type,status,amount,currency,platform_fee,quest_id,quest_title,client_name,freelancer_name"
    if expected_header not in text:
        raise RuntimeError("statement csv header is missing expected accounting columns")
    if quest_id not in text:
        raise RuntimeError("statement csv is missing seeded quest data")
    return {
        "status": status,
        "content_type": _header_value(headers, "Content-Type"),
        "content_disposition": _header_value(headers, "Content-Disposition"),
        "preview": text.splitlines()[:3],
    }


def main() -> int:
    args = _parse_args()
    suffix = uuid4().hex[:8]
    usernames = {
        "freelancer": f"smoke_pdf_f_{suffix}",
        "client": f"smoke_pdf_c_{suffix}",
    }

    try:
        health = _health_check(args.health_url)
        seeded = asyncio.run(
            _seed_smoke_rows(
                client_username=usernames["client"],
                freelancer_username=usernames["freelancer"],
                password=args.password,
                suffix=suffix,
            )
        )
        login = _login(
            args.api_base_url,
            username=usernames["freelancer"],
            password=args.password,
        )
        auth_headers = {"Authorization": f"Bearer {login['access_token']}"}
        receipt_body, receipt_headers, receipt_status = _request(
            f"{args.api_base_url}/wallet/transactions/{seeded['receipt_transaction_id']}/receipt",
            headers=auth_headers,
        )
        statement_pdf_body, statement_pdf_headers, statement_pdf_status = _request(
            f"{args.api_base_url}/wallet/statements?from={seeded['statement_date']}&to={seeded['statement_date']}&format=pdf",
            headers=auth_headers,
        )
        statement_csv_body, statement_csv_headers, statement_csv_status = _request(
            f"{args.api_base_url}/wallet/statements?from={seeded['statement_date']}&to={seeded['statement_date']}&format=csv",
            headers=auth_headers,
        )

        result = {
            "status": "ok",
            "health": health,
            "users": {
                "freelancer": usernames["freelancer"],
                "client": usernames["client"],
            },
            "seeded": seeded,
            "receipt": _validate_binary_pdf("receipt pdf", receipt_body, receipt_headers, receipt_status),
            "statement_pdf": _validate_binary_pdf("statement pdf", statement_pdf_body, statement_pdf_headers, statement_pdf_status),
            "statement_csv": _validate_csv(
                statement_csv_body,
                statement_csv_headers,
                statement_csv_status,
                quest_id=seeded["quest_id"],
            ),
        }
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": f"HTTP {exc.code}",
                    "url": exc.url,
                    "detail": detail,
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())