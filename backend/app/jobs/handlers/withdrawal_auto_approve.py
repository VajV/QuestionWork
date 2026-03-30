"""Background job handler for automated approval of eligible withdrawals."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.jobs.context import JobContext
from app.jobs.enums import QUEUE_OPS
from app.services import admin_service, notification_service
from app.services.withdrawal_runtime_service import WITHDRAWAL_AUTO_APPROVE_KIND


SYSTEM_ACTOR_ID = "system"


class WithdrawalAutoApproveHandler:
    kind = WITHDRAWAL_AUTO_APPROVE_KIND
    queue_name = QUEUE_OPS
    max_attempts = 3
    transaction_isolation = "default"

    def backoff_seconds(self, attempt_no: int, error_code: str | None) -> int:
        return attempt_no * 30

    def is_retryable(self, error: Exception) -> bool:
        return not isinstance(error, ValueError)

    async def execute(self, conn: Any, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        transaction_id = str(payload.get("transaction_id") or "").strip()
        if not transaction_id:
            raise ValueError("transaction_id is required for withdrawal auto-approve jobs")

        async with conn.transaction():
            tx = await conn.fetchrow(
                "SELECT id, user_id, type, status, amount, currency FROM transactions WHERE id = $1 FOR UPDATE",
                transaction_id,
            )
            if tx is None:
                raise ValueError(f"Transaction {transaction_id} not found")
            if tx["type"] != "withdrawal":
                raise ValueError(f"Transaction {transaction_id} is not a withdrawal")
            if tx["status"] != "pending":
                return {
                    "kind": self.kind,
                    "status": "ignored",
                    "reason": f"already-{tx['status']}",
                    "transaction_id": transaction_id,
                    "job_id": context.job_id,
                }

            actor_exists = await conn.fetchval("SELECT 1 FROM users WHERE id = $1", SYSTEM_ACTOR_ID)
            actor_id = SYSTEM_ACTOR_ID if actor_exists else settings.PLATFORM_USER_ID
            result = await admin_service.approve_withdrawal(
                conn,
                transaction_id=transaction_id,
                admin_id=actor_id,
                ip_address="127.0.0.1 (scheduler-auto-approve)",
                job_id=context.job_id,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
            await notification_service.create_notification(
                conn,
                user_id=result["user_id"],
                title="Withdrawal Approved",
                message=(
                    f"Your withdrawal of {result['amount']} {result['currency']} "
                    "has been automatically approved and is being processed."
                ),
                event_type="withdrawal_approved",
            )

        return {
            "kind": self.kind,
            "status": "succeeded",
            "transaction_id": transaction_id,
            "job_id": context.job_id,
            "actor_id": actor_id,
        }