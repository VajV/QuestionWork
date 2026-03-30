"""Trust-layer scheduling helpers for email outbox processing via ARQ."""

from __future__ import annotations

from uuid import uuid4

import asyncpg

from app.jobs.enums import QUEUE_DEFAULT
from app.jobs.handlers.email_send import EMAIL_SEND_KIND
from app.repositories import job_repository

EMAIL_OUTBOX_DEDUPE_PREFIX = "email:outbox"


def build_email_outbox_dedupe_key(outbox_id: str) -> str:
    return f"{EMAIL_OUTBOX_DEDUPE_PREFIX}:{outbox_id}"


async def schedule_email_outbox_jobs(
    conn: asyncpg.Connection,
    *,
    batch_limit: int = 50,
) -> int:
    """Find pending email_outbox rows and create email.send jobs for each."""
    rows = await conn.fetch(
        """
        SELECT eo.id
        FROM email_outbox eo
        WHERE eo.status = 'pending'
          AND eo.send_after <= NOW()
          AND eo.attempt_count < 3
          AND NOT EXISTS (
              SELECT 1
              FROM background_jobs bj
              WHERE bj.dedupe_key = $2 || ':' || eo.id::text
                AND bj.status IN ('queued', 'running', 'retry_scheduled')
          )
        ORDER BY eo.send_after ASC
        LIMIT $1
        """,
        batch_limit,
        EMAIL_OUTBOX_DEDUPE_PREFIX,
    )

    created = 0
    for row in rows:
        outbox_id = str(row["id"])
        try:
            await job_repository.create_job(
                conn,
                kind=EMAIL_SEND_KIND,
                queue_name=QUEUE_DEFAULT,
                dedupe_key=build_email_outbox_dedupe_key(outbox_id),
                payload_json={"outbox_id": outbox_id},
                max_attempts=3,
                trace_id=f"trace-{uuid4().hex[:12]}",
                request_id=f"sched-{uuid4().hex[:12]}",
                entity_type="email_outbox",
                entity_id=outbox_id,
            )
        except asyncpg.UniqueViolationError:
            continue
        created += 1

    return created
