from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg

MIN_CONTACT_GAP = timedelta(hours=18)
_PROCESSABLE_STATUSES = ("new", "nurturing")

_CADENCE = {
    "intake": {
        "next_stage": "follow_up_1",
        "status": "nurturing",
        "delay": timedelta(days=3),
        "subject": "Уточним рамку задачи и следующий шаг",
    },
    "follow_up_1": {
        "next_stage": "follow_up_2",
        "status": "nurturing",
        "delay": timedelta(days=5),
        "subject": "Подбор исполнителя и контрактный маршрут",
    },
    "follow_up_2": {
        "next_stage": "paused",
        "status": "paused",
        "delay": None,
        "subject": "Запрос сохранён, можно вернуться к нему позже",
    },
}


def _normalize_stage(stage: Optional[str]) -> str:
    if stage in _CADENCE:
        return stage
    return "intake"


def _build_touch(row: asyncpg.Record | dict, now: datetime) -> dict:
    current_stage = _normalize_stage(row.get("nurture_stage") if isinstance(row, dict) else row["nurture_stage"])
    cadence = _CADENCE[current_stage]
    next_contact_at = now + cadence["delay"] if cadence["delay"] is not None else None
    company_name = row.get("company_name") if isinstance(row, dict) else row["company_name"]
    use_case = row.get("use_case") if isinstance(row, dict) else row["use_case"]

    return {
        "lead_id": row.get("id") if isinstance(row, dict) else row["id"],
        "email": row.get("email") if isinstance(row, dict) else row["email"],
        "company_name": company_name,
        "current_stage": current_stage,
        "nurture_stage": cadence["next_stage"],
        "status": cadence["status"],
        "next_contact_at": next_contact_at,
        "subject": cadence["subject"],
        "message": (
            f"{company_name}, у вас сохранён запрос по сценарию '{use_case}'. "
            "Если задача уже созрела, следующий шаг — пройти client flow и зафиксировать контрактные рамки."
        ),
    }


async def process_due_leads(
    conn: asyncpg.Connection,
    *,
    now: Optional[datetime] = None,
    limit: int = 50,
    dry_run: bool = False,
) -> dict:
    evaluation_time = now or datetime.now(timezone.utc)
    recent_cutoff = evaluation_time - MIN_CONTACT_GAP

    async with conn.transaction():
        rows = await conn.fetch(
            """
            SELECT
                id,
                email,
                company_name,
                use_case,
                status,
                nurture_stage,
                last_contacted_at,
                next_contact_at,
                converted_user_id,
                created_at
            FROM growth_leads
            WHERE converted_user_id IS NULL
              AND status = ANY($1::text[])
              AND COALESCE(next_contact_at, created_at) <= $2
              AND (last_contacted_at IS NULL OR last_contacted_at <= $3)
            ORDER BY COALESCE(next_contact_at, created_at) ASC, created_at ASC
            LIMIT $4
            FOR UPDATE SKIP LOCKED
            """,
            list(_PROCESSABLE_STATUSES),
            evaluation_time,
            recent_cutoff,
            limit,
        )

        planned_touches = []
        for row in rows:
            touch = _build_touch(row, evaluation_time)
            planned_touches.append(touch)

            if dry_run:
                continue

            await conn.execute(
                """
                UPDATE growth_leads
                SET status = $2,
                    nurture_stage = $3,
                    last_contacted_at = $4,
                    next_contact_at = $5
                WHERE id = $1
                """,
                touch["lead_id"],
                touch["status"],
                touch["nurture_stage"],
                evaluation_time,
                touch["next_contact_at"],
            )

    return {
        "processed": len(planned_touches),
        "dry_run": dry_run,
        "planned_touches": planned_touches,
    }