"""
process_withdrawals.py — Idempotent automated withdrawal processor.

Selects pending withdrawal transactions (up to AUTO_APPROVE_LIMIT) and
approves them automatically.  Intended to be run via cron or scheduler.

Key safety properties
─────────────────────
1. PostgreSQL advisory lock  (pg_try_advisory_lock) — only one instance
   of this script may run at a time.  A second invocation exits cleanly
   without touching any data.
2. SELECT … FOR UPDATE SKIP LOCKED — each row is locked for the duration
   of its approval transaction.  Concurrent runners cannot process the
   same withdrawal twice.
3. Per-row transactions — a failure on one withdrawal rolls back only that
   row; the batch continues.

Usage:
    python scripts/process_withdrawals.py             # live run
    python scripts/process_withdrawals.py --dry-run   # preview only
    python scripts/process_withdrawals.py --limit 20  # process at most 20

Environment:
    DATABASE_URL                   (required)
    WITHDRAWAL_AUTO_APPROVE_LIMIT  (default 50.0)
    WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED
    SENTRY_DSN                     (optional — errors forwarded to Sentry)
    SLACK_WEBHOOK_URL              (optional — summary/errors posted to Slack)

Cron example (run every 5 minutes):
    */5 * * * * cd /app/backend && .venv/bin/python scripts/process_withdrawals.py >> /var/log/withdrawals.log 2>&1
"""

import argparse
import asyncio
import logging
import sys
import os

# ── Path setup ──────────────────────────────────────────────────────
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
from app.core.logging_config import setup_logging
from app.core.alerts import capture_exception, slack_error, slack_ok
from app.services import admin_service, notification_service

SYSTEM_ACTOR_ID = "system"  # used as admin_id in audit log for auto-approvals

# Advisory lock key: stable integer so it never conflicts with other pg locks.
_ADVISORY_LOCK_KEY = 1_234_567_890

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("process_withdrawals")

LEGACY_PROCESSOR_GUARD_MESSAGE = (
    "process_withdrawals.py must not run while WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED=true. "
    "Disable the legacy cron/task before using the new withdrawal job path."
)


def _ensure_legacy_processor_allowed() -> None:
    if not settings.WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED:
        return

    logger.error(LEGACY_PROCESSOR_GUARD_MESSAGE)
    raise RuntimeError(LEGACY_PROCESSOR_GUARD_MESSAGE)


async def run(*, dry_run: bool = False, batch_limit: int = 100) -> int:
    """
    Main processor loop.

    Returns the number of withdrawals that were (or would be) approved.
    Returns 0 immediately if a concurrent instance already holds the advisory lock.
    """
    _ensure_legacy_processor_allowed()

    logger.info(
        f"Starting withdrawal processor — "
        f"dry_run={dry_run}, batch_limit={batch_limit}, "
        f"auto_approve_limit={settings.WITHDRAWAL_AUTO_APPROVE_LIMIT}"
    )

    pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=3)
    processed = 0
    errors = 0

    try:
        async with pool.acquire() as lock_conn:
            # ── 1. Acquire session-level advisory lock ────────────────────
            # pg_try_advisory_lock is non-blocking: returns FALSE if another
            # session already holds the lock, so two parallel cron invocations
            # are impossible.
            lock_acquired = await lock_conn.fetchval(
                "SELECT pg_try_advisory_lock($1)", _ADVISORY_LOCK_KEY
            )
            if not lock_acquired:
                logger.warning(
                    "Another instance of process_withdrawals is already running "
                    "(advisory lock held by another session). Exiting cleanly."
                )
                return 0

            try:
                # ── 2. Fetch candidates using FOR UPDATE SKIP LOCKED ──────
                # SKIP LOCKED means rows already locked by a concurrent
                # transaction are silently skipped — correct for queue consumers.
                rows = await lock_conn.fetch(
                    """
                    SELECT id, user_id, amount, currency
                    FROM transactions
                    WHERE type = 'withdrawal'
                      AND status = 'pending'
                      AND amount <= $1
                    ORDER BY created_at ASC
                    LIMIT $2
                    FOR UPDATE SKIP LOCKED
                    """,
                    settings.WITHDRAWAL_AUTO_APPROVE_LIMIT,
                    batch_limit,
                )

                if not rows:
                    logger.info("No eligible pending withdrawals found.")
                    return 0

                logger.info(f"Found {len(rows)} eligible withdrawal(s) to process.")

                # ── 3. Process each row in its own savepoint ──────────────
                for row in rows:
                    tx_id = row["id"]
                    user_id = row["user_id"]
                    amount = float(row["amount"])
                    currency = row["currency"]

                    if dry_run:
                        logger.info(
                            f"[DRY-RUN] Would approve {tx_id}: "
                            f"{amount} {currency} for user {user_id}"
                        )
                        processed += 1
                        continue

                    try:
                        async with lock_conn.transaction():
                            actor_exists = await lock_conn.fetchval(
                                "SELECT 1 FROM users WHERE id = $1", SYSTEM_ACTOR_ID
                            )
                            actor_id = (
                                SYSTEM_ACTOR_ID if actor_exists else settings.PLATFORM_USER_ID
                            )

                            result = await admin_service.approve_withdrawal(
                                lock_conn,
                                transaction_id=tx_id,
                                admin_id=actor_id,
                                ip_address="127.0.0.1 (auto-processor)",
                            )
                            await notification_service.create_notification(
                                lock_conn,
                                user_id=user_id,
                                title="Withdrawal Approved",
                                message=(
                                    f"Your withdrawal of {amount} {currency} "
                                    "has been automatically approved and is being processed."
                                ),
                                event_type="withdrawal_approved",
                            )

                        logger.info(
                            f"Approved withdrawal {tx_id}: "
                            f"{amount} {currency} for user {user_id}"
                        )
                        processed += 1

                    except Exception as exc:  # noqa: BLE001
                        logger.error(
                            f"Failed to process withdrawal {tx_id}: {exc}", exc_info=True
                        )
                        capture_exception(exc, extra={"tx_id": tx_id, "user_id": user_id})
                        errors += 1

            finally:
                # Explicitly release; also auto-released when session closes.
                await lock_conn.execute(
                    "SELECT pg_advisory_unlock($1)", _ADVISORY_LOCK_KEY
                )

    finally:
        await pool.close()

    # ── 4. Post-run reporting ─────────────────────────────────────────────
    summary = (
        f"Withdrawal processor finished — "
        f"processed={processed}, errors={errors}, dry_run={dry_run}"
    )
    logger.info(summary)

    if errors > 0:
        slack_error(
            title=f"Withdrawal Processor: {errors} error(s) occurred",
            detail=f"{processed} approved, {errors} failed. See application logs.",
        )
    elif processed > 0 and not dry_run:
        slack_ok(
            title=f"Withdrawal Processor: {processed} approval(s) sent",
            detail=(
                f"All eligible withdrawals ≤ {settings.WITHDRAWAL_AUTO_APPROVE_LIMIT} processed."
            ),
        )

    return processed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-approve small pending withdrawals."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be processed without making any changes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        metavar="N",
        help="Maximum number of withdrawals to process in one run (default: 100).",
    )
    args = parser.parse_args()

    count = asyncio.run(run(dry_run=args.dry_run, batch_limit=args.limit))
    sys.exit(0 if count >= 0 else 1)


if __name__ == "__main__":
    main()
