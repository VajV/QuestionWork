"""ARQ job handler for processing email outbox entries."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from typing import Any

from app.jobs.context import JobContext
from app.jobs.enums import QUEUE_DEFAULT
from app.services import email_outbox_service

logger = logging.getLogger(__name__)

EMAIL_SEND_KIND = "email.send"


class EmailSendHandler:
    kind = EMAIL_SEND_KIND
    queue_name = QUEUE_DEFAULT
    max_attempts = 3
    transaction_isolation = "default"

    def backoff_seconds(self, attempt_no: int, error_code: str | None) -> int:
        return attempt_no * 60

    def is_retryable(self, error: Exception) -> bool:
        return isinstance(error, (smtplib.SMTPException, OSError, TimeoutError))

    async def execute(self, conn: Any, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        outbox_id = str(payload.get("outbox_id") or "").strip()
        if not outbox_id:
            raise ValueError("outbox_id is required for email.send jobs")

        row = await conn.fetchrow(
            """
            SELECT id, email_address, template_key, template_params, status, attempt_count
            FROM email_outbox
            WHERE id = $1
            """,
            outbox_id,
        )
        if row is None:
            raise ValueError(f"Email outbox entry {outbox_id} not found")

        if row["status"] != "pending":
            return {
                "kind": self.kind,
                "status": "ignored",
                "reason": f"already-{row['status']}",
                "outbox_id": outbox_id,
                "job_id": context.job_id,
            }

        template_key = row["template_key"]
        params = dict(row["template_params"]) if row["template_params"] else {}
        email_address = row["email_address"]

        try:
            await asyncio.to_thread(
                email_outbox_service._deliver,
                template_key=template_key,
                email_address=email_address,
                params=params,
            )
            await conn.execute(
                """
                UPDATE email_outbox
                SET status = 'sent', sent_at = NOW(), attempt_count = attempt_count + 1
                WHERE id = $1
                """,
                outbox_id,
            )
            logger.info("Email sent via job: outbox_id=%s template=%s to=%s", outbox_id, template_key, email_address)
            return {
                "kind": self.kind,
                "status": "succeeded",
                "outbox_id": outbox_id,
                "template_key": template_key,
                "job_id": context.job_id,
            }
        except Exception as exc:
            attempt = row["attempt_count"] + 1
            new_status = "failed" if attempt >= email_outbox_service.MAX_ATTEMPTS else "pending"
            await conn.execute(
                """
                UPDATE email_outbox
                SET attempt_count = $2, status = $3, error_message = $4
                WHERE id = $1
                """,
                outbox_id,
                attempt,
                new_status,
                str(exc)[:500],
            )
            logger.warning("Email send failed: outbox_id=%s attempt=%d error=%s", outbox_id, attempt, exc)
            raise
