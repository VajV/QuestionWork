"""Idempotent processor for captured demand leads."""

import argparse
import asyncio
import logging
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_BACKEND, ".env"))
except ImportError:
    pass

import asyncpg

from app.core.config import settings
from app.services import lead_nurture_service
from app.services import email_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("process_lead_nurture")

_ADVISORY_LOCK_KEY = 1_234_567_891


async def run(*, dry_run: bool = False, batch_limit: int = 50) -> int:
    pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            lock_acquired = await conn.fetchval(
                "SELECT pg_try_advisory_lock($1)", _ADVISORY_LOCK_KEY
            )
            if not lock_acquired:
                logger.warning("Lead nurture processor already running; exiting cleanly.")
                return 0

            try:
                result = await lead_nurture_service.process_due_leads(
                    conn,
                    limit=batch_limit,
                    dry_run=dry_run,
                )
            finally:
                await conn.execute("SELECT pg_advisory_unlock($1)", _ADVISORY_LOCK_KEY)
    finally:
        await pool.close()

    for touch in result["planned_touches"]:
        logger.info(
            "Lead %s -> %s (%s)",
            touch["lead_id"],
            touch["nurture_stage"],
            touch["status"],
        )
        # Send nurture email for each touch (unless dry-run)
        if not dry_run and touch.get("email") and touch.get("subject"):
            try:
                email_service.send_lifecycle_nudge(
                    to=touch["email"],
                    username=touch.get("company_name", ""),
                    subject=touch["subject"],
                    body_html=f"<p>{touch.get('message', '')}</p>",
                )
                logger.info("Nurture email sent to %s", touch["email"])
            except Exception as exc:
                logger.warning("Failed to send nurture email to %s: %s", touch["email"], exc)

    logger.info(
        "Lead nurture finished: processed=%s dry_run=%s",
        result["processed"],
        result["dry_run"],
    )
    return int(result["processed"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Process due nurture touches for captured leads.")
    parser.add_argument("--dry-run", action="store_true", help="Preview due touches without updating rows")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of due leads to process")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, batch_limit=args.limit))


if __name__ == "__main__":
    main()