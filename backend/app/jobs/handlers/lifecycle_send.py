"""ARQ job handler for lifecycle CRM message delivery."""

from __future__ import annotations

import logging
import smtplib
from typing import Any

from app.jobs.context import JobContext
from app.jobs.enums import QUEUE_DEFAULT
from app.services import email_service, lifecycle_service

logger = logging.getLogger(__name__)

LIFECYCLE_SEND_KIND = "lifecycle.send"


class LifecycleSendHandler:
    kind = LIFECYCLE_SEND_KIND
    queue_name = QUEUE_DEFAULT
    max_attempts = 3
    transaction_isolation = "default"

    def backoff_seconds(self, attempt_no: int, error_code: str | None) -> int:
        return attempt_no * 60

    def is_retryable(self, error: Exception) -> bool:
        return isinstance(error, (smtplib.SMTPException, OSError, TimeoutError))

    async def execute(self, conn: Any, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        message_id = str(payload.get("message_id") or "").strip()
        if not message_id:
            raise ValueError("message_id is required for lifecycle.send jobs")

        row = await conn.fetchrow(
            """
            SELECT id, user_id, campaign_key, trigger_data, status, error_message
            FROM lifecycle_messages
            WHERE id = $1
            """,
            message_id,
        )
        if row is None:
            raise ValueError(f"Lifecycle message {message_id} not found")

        if row["status"] != "pending":
            return {
                "kind": self.kind,
                "status": "ignored",
                "reason": f"already-{row['status']}",
                "message_id": message_id,
                "job_id": context.job_id,
            }

        trigger_data = dict(row["trigger_data"]) if row["trigger_data"] else {}
        recipient = await lifecycle_service.resolve_delivery_recipient(
            conn,
            user_id=str(row["user_id"]),
            campaign_key=str(row["campaign_key"]),
            trigger_data=trigger_data,
        )
        if recipient is None:
            await lifecycle_service.suppress(conn, message_id)
            return {
                "kind": self.kind,
                "status": "suppressed",
                "reason": "missing-recipient",
                "message_id": message_id,
                "job_id": context.job_id,
            }

        subject, body_html = lifecycle_service.build_lifecycle_email(str(row["campaign_key"]), trigger_data)

        try:
            email_service.send_lifecycle_nudge(
                to=recipient["email"],
                username=recipient["username"],
                subject=subject,
                body_html=body_html,
            )
            await lifecycle_service.mark_sent(conn, message_id)
            logger.info(
                "Lifecycle message sent via job: message_id=%s campaign=%s to=%s",
                message_id,
                row["campaign_key"],
                recipient["email"],
            )
            return {
                "kind": self.kind,
                "status": "succeeded",
                "message_id": message_id,
                "campaign_key": str(row["campaign_key"]),
                "job_id": context.job_id,
            }
        except Exception as exc:
            await lifecycle_service.record_delivery_error(conn, message_id, str(exc))
            logger.warning(
                "Lifecycle send failed: message_id=%s campaign=%s error=%s",
                message_id,
                row["campaign_key"],
                exc,
            )
            if not self.is_retryable(exc):
                await lifecycle_service.mark_failed(conn, message_id, str(exc))
            raise