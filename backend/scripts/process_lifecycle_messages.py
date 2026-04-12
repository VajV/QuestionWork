"""Background worker: process pending lifecycle messages.

Fetches due lifecycle_messages rows, resolves user contact info, dispatches
emails via email_service, then marks each message sent or failed.

Run once (e.g. from a cron job or Task Scheduler):
    cd backend
    .venv/Scripts/python.exe scripts/process_lifecycle_messages.py [--dry-run] [--limit N]
"""

import argparse
import asyncio
import logging
import os
import sys

# Allow imports from app/ when running this script directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg

from app.core.config import settings
from app.services import email_service, lifecycle_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

async def _process_batch(conn: asyncpg.Connection, dry_run: bool, limit: int) -> dict[str, int]:
    messages = await lifecycle_service.get_pending_messages(conn, limit=limit)
    sent = failed = skipped = 0

    for msg in messages:
        msg_id = str(msg["id"])
        user_id = str(msg["user_id"])
        campaign_key = msg["campaign_key"]
        trigger_data: dict = dict(msg["trigger_data"]) if msg["trigger_data"] else {}

        recipient = await lifecycle_service.resolve_delivery_recipient(
            conn,
            user_id=user_id,
            campaign_key=campaign_key,
            trigger_data=trigger_data,
        )
        if recipient is None:
            logger.warning("User %s not found — suppressing lifecycle message %s", user_id, msg_id)
            async with conn.transaction():
                await lifecycle_service.suppress(conn, msg_id)
            skipped += 1
            continue

        email_address = recipient["email"]
        username = recipient["username"]
        subject, body_html = lifecycle_service.build_lifecycle_email(campaign_key, trigger_data)

        if dry_run:
            logger.info(
                "[dry-run] Would send %r to %s (%s) — subject: %s",
                campaign_key, username, email_address, subject,
            )
            sent += 1
            continue

        try:
            email_service.send_lifecycle_nudge(
                to=email_address,
                username=username,
                subject=subject,
                body_html=body_html,
            )
            async with conn.transaction():
                await lifecycle_service.mark_sent(conn, msg_id)
            sent += 1
            logger.info("Sent lifecycle message %s (%s) to %s", msg_id, campaign_key, email_address)
        except Exception as exc:
            async with conn.transaction():
                await lifecycle_service.mark_failed(conn, msg_id, str(exc))
            failed += 1
            logger.error("Failed to deliver lifecycle message %s: %s", msg_id, exc)

    return {"sent": sent, "failed": failed, "skipped": skipped}


async def main(dry_run: bool = False, limit: int = 100, no_scan: bool = False) -> None:
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        # 1. Reactivation scan: enqueue dormant-client and stale-shortlist messages
        if not no_scan:
            if dry_run:
                logger.info("[dry-run] Skipping scan (would call scan_and_enqueue_dormant_clients + stale_shortlists)")
            else:
                dormant_count = await lifecycle_service.scan_and_enqueue_dormant_clients(conn)
                stale_count = await lifecycle_service.scan_and_enqueue_stale_shortlists(conn)
                logger.info("Scan complete — dormant_clients_enqueued=%d stale_shortlists_enqueued=%d", dormant_count, stale_count)

        # 2. Process the outbox
        logger.info("Processing lifecycle messages (dry_run=%s, limit=%d)…", dry_run, limit)
        result = await _process_batch(conn, dry_run=dry_run, limit=limit)
        logger.info("Done — sent=%d failed=%d skipped=%d", result["sent"], result["failed"], result["skipped"])
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process pending lifecycle messages")
    parser.add_argument("--dry-run", action="store_true", help="Log what would be sent but don't send or update DB")
    parser.add_argument("--limit", type=int, default=100, help="Max messages to process per run")
    parser.add_argument("--no-scan", action="store_true", help="Skip the reactivation scan phase (process outbox only)")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit, no_scan=args.no_scan))
