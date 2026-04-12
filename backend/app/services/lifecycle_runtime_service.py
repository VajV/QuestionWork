"""Trust-layer scheduling helpers for lifecycle message delivery."""

from __future__ import annotations

from uuid import uuid4

import asyncpg

from app.jobs.enums import QUEUE_DEFAULT
from app.jobs.handlers.lifecycle_send import LIFECYCLE_SEND_KIND
from app.repositories import job_repository

LIFECYCLE_MESSAGE_DEDUPE_PREFIX = "lifecycle:message"


def build_lifecycle_message_dedupe_key(message_id: str) -> str:
    return f"{LIFECYCLE_MESSAGE_DEDUPE_PREFIX}:{message_id}"


async def schedule_due_lifecycle_jobs(
    conn: asyncpg.Connection,
    *,
    batch_limit: int = 50,
) -> int:
    rows = await conn.fetch(
        """
        SELECT lm.id
        FROM lifecycle_messages lm
        WHERE lm.status = 'pending'
          AND lm.send_after <= NOW()
          AND NOT EXISTS (
              SELECT 1
              FROM background_jobs bj
              WHERE bj.dedupe_key = $2 || ':' || lm.id::text
          )
        ORDER BY lm.send_after ASC
        LIMIT $1
        """,
        batch_limit,
        LIFECYCLE_MESSAGE_DEDUPE_PREFIX,
    )

    created = 0
    for row in rows:
        message_id = str(row["id"])
        try:
            await job_repository.create_job(
                conn,
                kind=LIFECYCLE_SEND_KIND,
                queue_name=QUEUE_DEFAULT,
                dedupe_key=build_lifecycle_message_dedupe_key(message_id),
                payload_json={"message_id": message_id},
                max_attempts=3,
                trace_id=f"trace-{uuid4().hex[:12]}",
                request_id=f"sched-{uuid4().hex[:12]}",
                entity_type="lifecycle_message",
                entity_id=message_id,
            )
        except asyncpg.UniqueViolationError:
            continue
        created += 1

    return created