"""Trust-layer scheduling helpers for automated withdrawal approval."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import asyncpg

from app.jobs.enums import QUEUE_OPS
from app.repositories import job_repository


WITHDRAWAL_AUTO_APPROVE_KIND = "money.withdrawal.auto_approve"
WITHDRAWAL_AUTO_APPROVE_DEDUPE_PREFIX = "withdrawal:auto-approve"


def build_withdrawal_auto_approve_dedupe_key(transaction_id: str) -> str:
    return f"{WITHDRAWAL_AUTO_APPROVE_DEDUPE_PREFIX}:{transaction_id}"


async def schedule_auto_approve_jobs(
    conn: asyncpg.Connection,
    *,
    auto_approve_limit: str,
    batch_limit: int,
) -> int:
    approve_limit = Decimal(str(auto_approve_limit))
    rows = await conn.fetch(
        """
        SELECT t.id, t.user_id, t.amount, t.currency
        FROM transactions t
        WHERE t.type = 'withdrawal'
          AND t.status = 'pending'
          AND t.amount <= $1
          AND NOT EXISTS (
              SELECT 1
              FROM background_jobs bj
              WHERE bj.dedupe_key = $3 || ':' || t.id
                AND bj.status IN ('queued', 'running', 'retry_scheduled')
          )
        ORDER BY t.created_at ASC
        LIMIT $2
        """,
        approve_limit,
        batch_limit,
        WITHDRAWAL_AUTO_APPROVE_DEDUPE_PREFIX,
    )

    created = 0
    for row in rows:
        try:
            await job_repository.create_job(
                conn,
                kind=WITHDRAWAL_AUTO_APPROVE_KIND,
                queue_name=QUEUE_OPS,
                dedupe_key=build_withdrawal_auto_approve_dedupe_key(str(row["id"])),
                payload_json={
                    "transaction_id": str(row["id"]),
                    "user_id": row["user_id"],
                    "amount": str(row["amount"]),
                    "currency": row["currency"],
                },
                max_attempts=3,
                trace_id=f"trace-{uuid4().hex[:12]}",
                request_id=f"sched-{uuid4().hex[:12]}",
                entity_type="transaction",
                entity_id=str(row["id"]),
            )
        except asyncpg.UniqueViolationError:
            continue
        created += 1

    return created