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

# Map campaign_key → (email subject, body_html template fn(trigger_data) → str)
CAMPAIGN_TEMPLATES: dict[str, tuple[str, "callable"]] = {
    "incomplete_profile": (
        "[QuestionWork] Дополните свой профиль",
        lambda _: (
            "<p>Вы зарегистрировались, но ваш профиль ещё не заполнен.</p>"
            "<p><a href='__FRONTEND_URL__/profile/edit' style='color:#7c3aed;'>Заполнить профиль</a>"
            " — это займёт всего 2 минуты!</p>"
        ),
    ),
    "incomplete_quest_draft": (
        "[QuestionWork] У вас есть незавершённый квест-черновик",
        lambda td: (
            f"<p>Квест <strong>#{td.get('quest_id', '')}</strong> остался черновиком.</p>"
            "<p><a href='__FRONTEND_URL__/quests/create' style='color:#7c3aed;'>Завершить создание</a></p>"
        ),
    ),
    "stale_shortlist": (
        "[QuestionWork] Ваш шортлист ждёт действия",
        lambda _: (
            "<p>Вы добавили фрилансеров в шортлист, но ещё не назначили квест.</p>"
            "<p><a href='__FRONTEND_URL__/shortlists' style='color:#7c3aed;'>Посмотреть шортлист</a></p>"
        ),
    ),
    "unreviewed_completion": (
        "[QuestionWork] Оцените выполненный квест",
        lambda td: (
            f"<p>Квест <strong>#{td.get('quest_id', '')}</strong> завершён, но вы ещё не оставили отзыв.</p>"
            "<p><a href='__FRONTEND_URL__/quests' style='color:#7c3aed;'>Оставить отзыв</a></p>"
        ),
    ),
    "dormant_client": (
        "[QuestionWork] Мы скучаем по вам!",
        lambda td: (
            f"<p>Прошло {td.get('days_dormant', '?')} дней с момента вашего последнего квеста.</p>"
            "<p><a href='__FRONTEND_URL__/quests/create' style='color:#7c3aed;'>Разместить новый квест</a></p>"
        ),
    ),
    "lead_no_register": (
        "[QuestionWork] Завершите регистрацию",
        lambda _: (
            "<p>Вы оставили заявку, но так и не зарегистрировались.</p>"
            "<p><a href='__FRONTEND_URL__/auth/register' style='color:#7c3aed;'>Зарегистрироваться</a></p>"
        ),
    ),
    "lead_no_quest": (
        "[QuestionWork] Разместите свой первый квест",
        lambda _: (
            "<p>Вы зарегистрировались как клиент, но ещё не разместили ни одного квеста.</p>"
            "<p><a href='__FRONTEND_URL__/quests/create' style='color:#7c3aed;'>Создать квест</a></p>"
        ),
    ),
}


def _build_body(campaign_key: str, trigger_data: dict) -> tuple[str, str]:
    """Return (subject, body_html) for a campaign key."""
    tpl = CAMPAIGN_TEMPLATES.get(campaign_key)
    if tpl is None:
        return (
            "[QuestionWork] Уведомление",
            "<p>У вас есть новое уведомление от QuestionWork.</p>",
        )
    subject, body_fn = tpl
    body_html = body_fn(trigger_data).replace("__FRONTEND_URL__", settings.FRONTEND_URL)
    return subject, body_html


async def _process_batch(conn: asyncpg.Connection, dry_run: bool, limit: int) -> dict[str, int]:
    messages = await lifecycle_service.get_pending_messages(conn, limit=limit)
    sent = failed = skipped = 0

    for msg in messages:
        msg_id = str(msg["id"])
        user_id = str(msg["user_id"])
        campaign_key = msg["campaign_key"]
        trigger_data: dict = dict(msg["trigger_data"]) if msg["trigger_data"] else {}

        # Resolve user contact info
        user_row = await conn.fetchrow(
            "SELECT email, username FROM users WHERE id = $1::uuid", user_id
        )
        if user_row is None:
            logger.warning("User %s not found — suppressing lifecycle message %s", user_id, msg_id)
            async with conn.transaction():
                await lifecycle_service.suppress(conn, msg_id)
            skipped += 1
            continue

        email_address: str = user_row["email"]
        username: str = user_row["username"]
        subject, body_html = _build_body(campaign_key, trigger_data)

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
