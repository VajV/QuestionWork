"""Backfill persisted trust score cache for existing users.

Usage:
    .venv/Scripts/python.exe scripts/backfill_user_trust_scores.py --dry-run --limit 20
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from app.db.session import acquire_db_connection, close_db_pool
from app.services import trust_score_service


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill cached trust scores for users")
    parser.add_argument("--dry-run", action="store_true", help="Preview computed trust scores without updating rows")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of users to process")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of users fetched per batch")
    return parser.parse_args()


async def _fetch_user_ids(conn, *, limit: int, offset: int) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT id
        FROM users
        ORDER BY created_at ASC, id ASC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    return [str(row["id"]) for row in rows]


def _preview_payload(user_id: str, score: float, breakdown: dict[str, Any]) -> str:
    return json.dumps(
        {
            "user_id": user_id,
            "trust_score": score,
            "breakdown": breakdown,
        },
        ensure_ascii=False,
    )


async def run(*, dry_run: bool = False, limit: int = 100, batch_size: int = 50) -> int:
    processed = 0
    offset = 0

    async with acquire_db_connection() as conn:
        while processed < limit:
            remaining = limit - processed
            current_batch_size = min(batch_size, remaining)
            user_ids = await _fetch_user_ids(conn, limit=current_batch_size, offset=offset)
            if not user_ids:
                break

            for user_id in user_ids:
                if dry_run:
                    inputs = await trust_score_service.fetch_trust_inputs(conn, user_id)
                    if not inputs:
                        continue
                    score, breakdown = trust_score_service.calculate_trust_score(
                        avg_rating_5=inputs["avg_rating_5"],
                        accepted_quests=inputs["accepted_quests"],
                        confirmed_quests=inputs["confirmed_quests"],
                        on_time_quests=inputs["on_time_quests"],
                        grade=inputs["grade"],
                    )
                    print(_preview_payload(user_id, score, breakdown))
                else:
                    async with conn.transaction():
                        result = await trust_score_service.refresh_trust_score(conn, user_id)
                    print(f"refreshed:{user_id}:{result['trust_score'] if result else 'skipped'}")

                processed += 1
                if processed >= limit:
                    break

            offset += len(user_ids)
            print(f"progress processed={processed} limit={limit} dry_run={dry_run}")

    await close_db_pool()
    return processed


def main() -> None:
    args = _parse_args()
    processed = asyncio.run(run(dry_run=args.dry_run, limit=max(1, args.limit), batch_size=max(1, args.batch_size)))
    print(f"done processed={processed} dry_run={args.dry_run}")


if __name__ == "__main__":
    main()