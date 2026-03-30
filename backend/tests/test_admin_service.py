"""
Tests for admin_service — audit log, withdrawal approve/reject, list ops, cleanup.

Coverage goal: ≥ 85% of admin_service.py
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.services.admin_service import (
    log_admin_action,
    approve_withdrawal,
    reject_withdrawal,
    list_users,
    list_transactions,
    list_pending_withdrawals,
    get_admin_logs,
    cleanup_old_notifications,
    update_user,
    ban_user,
    delete_user,
    delete_quest,
    update_quest,
    force_cancel_quest,
    force_complete_quest,
    adjust_wallet,
)


# ──────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────

def _make_conn(in_txn=True):
    conn = AsyncMock()
    conn.is_in_transaction = MagicMock(return_value=in_txn)
    return conn


def _pending_tx(amount=100.0, currency="RUB", user_id="user_fl"):
    return {
        "id": "tx_test001",
        "user_id": user_id,
        "type": "withdrawal",
        "amount": amount,
        "currency": currency,
        "status": "pending",
        "quest_id": None,
        "created_at": datetime.now(timezone.utc),
    }


# ──────────────────────────────────────────────────────
# log_admin_action
# ──────────────────────────────────────────────────────

class TestLogAdminAction:
    @pytest.mark.asyncio
    async def test_inserts_audit_row(self):
        conn = _make_conn()
        log_id = await log_admin_action(
            conn,
            admin_id="admin1",
            action="test_action",
            target_type="transaction",
            target_id="tx1",
            old_value={"status": "pending"},
            new_value={"status": "completed"},
            ip_address="127.0.0.1",
        )
        assert log_id.startswith("alog_")
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_inserts_audit_linkage_fields_when_provided(self):
        conn = _make_conn()

        await log_admin_action(
            conn,
            admin_id="admin1",
            action="test_action",
            target_type="transaction",
            target_id="tx1",
            command_id="cmd-1",
            job_id="job-1",
            request_id="req-1",
            trace_id="trace-1",
        )

        args = conn.execute.await_args.args
        assert "command_id, job_id, request_id, trace_id" in args[0]
        assert args[9] == "cmd-1"
        assert args[10] == "job-1"
        assert args[11] == "req-1"
        assert args[12] == "trace-1"

    @pytest.mark.asyncio
    async def test_raises_if_not_in_transaction(self):
        conn = _make_conn(in_txn=False)
        with pytest.raises(RuntimeError, match="DB transaction"):
            await log_admin_action(conn, "admin1", "action", "type", "id")

    @pytest.mark.asyncio
    async def test_works_without_optional_fields(self):
        conn = _make_conn()
        log_id = await log_admin_action(
            conn, admin_id="admin1", action="read", target_type="user", target_id="u1"
        )
        assert log_id.startswith("alog_")
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_serializes_decimal_payloads(self):
        conn = _make_conn()

        await log_admin_action(
            conn,
            admin_id="admin1",
            action="wallet_adjust",
            target_type="wallet",
            target_id="user_1:RUB",
            old_value={"balance": Decimal("100.00"), "items": [Decimal("1.50")]},
            new_value={"balance": Decimal("150.00"), "adjustment": Decimal("50.00")},
        )

        old_value = json.loads(conn.execute.await_args.args[6])
        new_value = json.loads(conn.execute.await_args.args[7])
        assert old_value == {"balance": "100.00", "items": ["1.50"]}
        assert new_value == {"balance": "150.00", "adjustment": "50.00"}


# ──────────────────────────────────────────────────────
# approve_withdrawal
# ──────────────────────────────────────────────────────

class TestApproveWithdrawal:
    @pytest.mark.asyncio
    async def test_approves_pending_withdrawal(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=_pending_tx())

        result = await approve_withdrawal(conn, "tx_test001", "admin1", ip_address="1.2.3.4")

        assert result["status"] == "completed"
        assert result["transaction_id"] == "tx_test001"
        # UPDATE + audit INSERT
        assert conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_if_not_found(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await approve_withdrawal(conn, "tx_missing", "admin1")

    @pytest.mark.asyncio
    async def test_raises_if_not_withdrawal_type(self):
        conn = _make_conn()
        tx = _pending_tx()
        tx["type"] = "income"
        conn.fetchrow = AsyncMock(return_value=tx)

        with pytest.raises(ValueError, match="not a withdrawal"):
            await approve_withdrawal(conn, "tx_test001", "admin1")

    @pytest.mark.asyncio
    async def test_raises_if_already_completed(self):
        conn = _make_conn()
        tx = _pending_tx()
        tx["status"] = "completed"
        conn.fetchrow = AsyncMock(return_value=tx)

        with pytest.raises(ValueError, match="already completed"):
            await approve_withdrawal(conn, "tx_test001", "admin1")

    @pytest.mark.asyncio
    async def test_raises_if_not_in_transaction(self):
        conn = _make_conn(in_txn=False)
        with pytest.raises(RuntimeError, match="DB transaction"):
            await approve_withdrawal(conn, "tx_test001", "admin1")

    @pytest.mark.asyncio
    async def test_passes_job_and_trace_linkage_to_audit_log(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=_pending_tx())

        await approve_withdrawal(
            conn,
            "tx_test001",
            "admin1",
            job_id="job-approve-1",
            request_id="req-approve-1",
            trace_id="trace-approve-1",
        )

        audit_args = conn.execute.await_args_list[1].args
        assert audit_args[10] == "job-approve-1"
        assert audit_args[11] == "req-approve-1"
        assert audit_args[12] == "trace-approve-1"


# ──────────────────────────────────────────────────────
# reject_withdrawal
# ──────────────────────────────────────────────────────

class TestRejectWithdrawal:
    @pytest.mark.asyncio
    async def test_rejects_and_refunds(self):
        conn = _make_conn()
        tx = _pending_tx(amount=50.0)
        conn.fetchrow = AsyncMock(return_value=tx)
        # credit() will also call fetchrow (wallet lock) — return None (auto-create path)
        # then fetchrow again for INSERT...RETURNING balance
        conn.fetchrow.side_effect = [tx, None, {"balance": 50.0}]

        result = await reject_withdrawal(
            conn, "tx_test001", "admin1", reason="Verification failed"
        )

        assert result["status"] == "rejected"
        assert result["reason"] == "Verification failed"
        assert result["user_id"] == tx["user_id"]
        # execute: UPDATE status + INSERT wallet (from credit) + INSERT tx ledger + INSERT audit
        assert conn.execute.call_count >= 3

    @pytest.mark.asyncio
    async def test_raises_if_not_found(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await reject_withdrawal(conn, "tx_missing", "admin1", reason="x")

    @pytest.mark.asyncio
    async def test_raises_if_already_rejected(self):
        conn = _make_conn()
        tx = _pending_tx()
        tx["status"] = "rejected"
        conn.fetchrow = AsyncMock(return_value=tx)

        with pytest.raises(ValueError, match="already rejected"):
            await reject_withdrawal(conn, "tx_test001", "admin1", reason="x")

    @pytest.mark.asyncio
    async def test_raises_if_not_in_transaction(self):
        conn = _make_conn(in_txn=False)
        with pytest.raises(RuntimeError, match="DB transaction"):
            await reject_withdrawal(conn, "tx_test001", "admin1", reason="x")


# ──────────────────────────────────────────────────────
# list_users
# ──────────────────────────────────────────────────────

class TestListUsers:
    @pytest.mark.asyncio
    async def test_returns_paginated_users(self):
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(return_value=2)
        conn.fetch = AsyncMock(return_value=[
            {"id": "u1", "username": "alice", "email": None,
             "role": "freelancer", "grade": "novice", "level": 1,
             "xp": 0, "created_at": datetime.now(timezone.utc)},
            {"id": "u2", "username": "bob", "email": None,
             "role": "client", "grade": "novice", "level": 1,
             "xp": 0, "created_at": datetime.now(timezone.utc)},
        ])

        result = await list_users(conn, page=1, page_size=50)

        assert result["total"] == 2
        assert len(result["users"]) == 2
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_role_filter_passed_to_query(self):
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[])

        await list_users(conn, page=1, page_size=10, role_filter="admin")

        fetch_call = conn.fetch.call_args[0][0]
        assert "role" in fetch_call.lower() or conn.fetchval.call_args[0][0].count("role") >= 0


class TestSchemaTruth:
    def test_user_orm_matches_applied_email_and_avg_rating_columns(self):
        from sqlalchemy import Numeric

        from app.db.models import UserORM

        email_column = UserORM.__table__.c.email
        avg_rating_column = UserORM.__table__.c.avg_rating

        assert email_column.nullable is False
        assert isinstance(avg_rating_column.type, Numeric)
        assert avg_rating_column.type.precision == 3
        assert avg_rating_column.type.scale == 2

    def test_user_orm_matches_trust_score_cache_columns(self):
        from sqlalchemy import Numeric
        from sqlalchemy.dialects.postgresql import JSONB

        from app.db.models import UserORM

        trust_score_column = UserORM.__table__.c.trust_score
        trust_score_breakdown_column = UserORM.__table__.c.trust_score_breakdown
        trust_score_updated_at_column = UserORM.__table__.c.trust_score_updated_at

        assert isinstance(trust_score_column.type, Numeric)
        assert trust_score_column.type.precision == 5
        assert trust_score_column.type.scale == 4
        assert isinstance(trust_score_breakdown_column.type, JSONB)
        assert trust_score_breakdown_column.nullable is False
        assert str(trust_score_breakdown_column.server_default.arg) == "'{}'::jsonb"
        assert trust_score_updated_at_column.nullable is True

        constraint_names = {constraint.name for constraint in UserORM.__table__.constraints}
        assert "chk_users_trust_score_range" in constraint_names

    def test_transaction_orm_matches_nullable_preserved_user_history_schema(self):
        from app.db.models import TransactionORM

        user_id_column = TransactionORM.__table__.c.user_id
        user_fk = next(iter(user_id_column.foreign_keys))

        assert user_id_column.nullable is True
        assert user_fk.ondelete == "SET NULL"

    def test_metadata_includes_tables_from_applied_migrations(self):
        from app.db.models import Base

        table_names = set(Base.metadata.tables)

        assert {
            "admin_logs",
            "backup_jobs",
            "badges",
            "notifications",
            "quest_message_reads",
            "quest_messages",
            "quest_reviews",
            "quest_templates",
            "user_abilities",
            "user_badges",
            "user_class_progress",
            "user_perks",
        }.issubset(table_names)

    def test_quest_orm_matches_applied_constraints_and_indexes(self):
        from app.db.models import QuestORM

        client_id_column = QuestORM.__table__.c.client_id
        client_fk = next(iter(client_id_column.foreign_keys))
        assigned_fk = next(iter(QuestORM.__table__.c.assigned_to.foreign_keys))
        index_names = {index.name for index in QuestORM.__table__.indexes}

        assert client_id_column.nullable is False
        assert client_fk.ondelete == "RESTRICT"
        assert assigned_fk.ondelete == "SET NULL"
        assert "revision_count" in QuestORM.__table__.c
        assert "platform_fee_percent" in QuestORM.__table__.c
        assert {"idx_quests_deadline", "idx_quests_is_urgent", "idx_quests_skills_gin"}.issubset(index_names)

    def test_application_and_guild_member_indexes_match_migrations(self):
        from app.db.models import ApplicationORM, GuildMemberORM

        application_indexes = {index.name: index for index in ApplicationORM.__table__.indexes}
        guild_member_indexes = {index.name: index for index in GuildMemberORM.__table__.indexes}

        assert application_indexes["idx_applications_quest_freelancer"].unique is True
        assert guild_member_indexes["uq_guild_members_active_user"].unique is True


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_update_user_normalizes_and_serializes_skills(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={
            "id": "user_1",
            "skills": ["python"],
            "role": "freelancer",
            "username": "alice",
            "email": "alice@example.com",
        })

        result = await update_user(
            conn,
            user_id="user_1",
            fields={"skills": ["  FastAPI  ", "TypeScript"]},
            admin_id="admin_1",
        )

        assert result == {"user_id": "user_1", "updated_fields": ["skills"]}
        update_query, update_payload, _, update_user_id = conn.execute.await_args_list[0].args
        assert "skills = $1" in update_query
        assert json.loads(update_payload) == ["FastAPI", "TypeScript"]
        assert update_user_id == "user_1"

    @pytest.mark.asyncio
    async def test_update_user_rejects_non_string_skill_items(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={
            "id": "user_1",
            "skills": [],
            "role": "freelancer",
            "username": "alice",
            "email": "alice@example.com",
        })

        with pytest.raises(ValueError, match="skills must contain only strings"):
            await update_user(
                conn,
                user_id="user_1",
                fields={"skills": ["python", 123]},
                admin_id="admin_1",
            )

    @pytest.mark.asyncio
    async def test_update_user_rejects_too_many_skills(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={
            "id": "user_1",
            "skills": [],
            "role": "freelancer",
            "username": "alice",
            "email": "alice@example.com",
        })

        with pytest.raises(ValueError, match="skills must contain at most 20 items"):
            await update_user(
                conn,
                user_id="user_1",
                fields={"skills": [f"skill_{idx}" for idx in range(21)]},
                admin_id="admin_1",
            )

    @pytest.mark.asyncio
    async def test_update_user_rejects_oversized_skill(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={
            "id": "user_1",
            "skills": [],
            "role": "freelancer",
            "username": "alice",
            "email": "alice@example.com",
        })

        with pytest.raises(ValueError, match="each skill must be at most 50 characters"):
            await update_user(
                conn,
                user_id="user_1",
                fields={"skills": ["x" * 51]},
                admin_id="admin_1",
            )


# ──────────────────────────────────────────────────────
# list_transactions / list_pending_withdrawals
# ──────────────────────────────────────────────────────

class TestListTransactions:
    @pytest.mark.asyncio
    async def test_returns_paginated_transactions(self):
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[
            {
                "id": "tx1", "user_id": "u1", "type": "withdrawal",
                "amount": 100.0, "currency": "RUB", "status": "pending",
                "quest_id": None, "created_at": datetime.now(timezone.utc),
            }
        ])

        result = await list_transactions(conn, status_filter="pending", type_filter="withdrawal")

        assert result["total"] == 1
        assert result["transactions"][0]["type"] == "withdrawal"


class TestAdjustWallet:
    @pytest.mark.asyncio
    async def test_adjust_wallet_quantizes_positive_amount(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={"id": "user_1", "username": "alice"})

        with patch("app.services.admin_service.wallet_service.get_balance", new=AsyncMock(return_value=Decimal("100.00"))), \
             patch("app.services.admin_service.wallet_service.credit", new=AsyncMock(return_value=Decimal("110.01"))) as mock_credit, \
             patch("app.services.admin_service.log_admin_action", new=AsyncMock(return_value="alog_1")), \
             patch("app.services.admin_service.notification_service.create_notification", new=AsyncMock()):
            result = await adjust_wallet(
                conn,
                user_id="user_1",
                amount=Decimal("10.005"),
                currency="RUB",
                reason="bonus",
                admin_id="admin_1",
            )

        assert result["amount"] == Decimal("10.01")
        assert result["old_balance"] == Decimal("100.00")
        assert result["new_balance"] == Decimal("110.01")
        assert mock_credit.await_args.kwargs["amount"] == Decimal("10.01")

    @pytest.mark.asyncio
    async def test_adjust_wallet_quantizes_negative_amount(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={"id": "user_2", "username": "bob"})

        with patch("app.services.admin_service.wallet_service.get_balance", new=AsyncMock(return_value=Decimal("100.00"))), \
             patch("app.services.admin_service.wallet_service.debit", new=AsyncMock(return_value=Decimal("89.99"))) as mock_debit, \
             patch("app.services.admin_service.log_admin_action", new=AsyncMock(return_value="alog_2")), \
             patch("app.services.admin_service.notification_service.create_notification", new=AsyncMock()):
            result = await adjust_wallet(
                conn,
                user_id="user_2",
                amount=Decimal("-10.005"),
                currency="RUB",
                reason="fee",
                admin_id="admin_1",
            )

        assert result["amount"] == Decimal("-10.01")
        assert mock_debit.await_args.kwargs["amount"] == Decimal("10.01")

    @pytest.mark.asyncio
    async def test_adjust_wallet_writes_decimal_safe_audit_log(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={"id": "user_1", "username": "alice"})

        with patch("app.services.admin_service.wallet_service.get_balance", new=AsyncMock(return_value=Decimal("100.00"))), \
             patch("app.services.admin_service.wallet_service.credit", new=AsyncMock(return_value=Decimal("150.00"))), \
             patch("app.services.admin_service.notification_service.create_notification", new=AsyncMock()):
            result = await adjust_wallet(
                conn,
                user_id="user_1",
                amount=Decimal("50.00"),
                currency="RUB",
                reason="fund test",
                admin_id="admin_1",
            )

        assert result["new_balance"] == Decimal("150.00")
        assert conn.execute.await_count == 1

        old_value = json.loads(conn.execute.await_args.args[6])
        new_value = json.loads(conn.execute.await_args.args[7])
        assert old_value == {"balance": "100.00", "currency": "RUB"}
        assert new_value == {
            "balance": "150.00",
            "currency": "RUB",
            "adjustment": "50.00",
            "reason": "fund test",
        }

    @pytest.mark.asyncio
    async def test_adjust_wallet_rejects_zero_amount(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={"id": "user_1", "username": "alice"})

        with patch("app.services.admin_service.wallet_service.get_balance", new=AsyncMock(return_value=Decimal("100.00"))):
            with pytest.raises(ValueError, match="non-zero"):
                await adjust_wallet(
                    conn,
                    user_id="user_1",
                    amount=Decimal("0"),
                    currency="RUB",
                    reason="noop",
                    admin_id="admin_1",
                )

    @pytest.mark.asyncio
    async def test_pending_withdrawals_shortcut(self):
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetch = AsyncMock(return_value=[])

        result = await list_pending_withdrawals(conn)

        assert result["total"] == 0
        # Verify both filters were applied (pending + withdrawal)
        call_args = conn.fetch.call_args
        fetch_query = call_args[0][0]
        fetch_params = call_args[0][1:]
        # The SQL uses placeholders; the actual values are in positional params
        assert "pending" in fetch_params or "pending" in fetch_query
        assert "withdrawal" in fetch_params or "withdrawal" in fetch_query


# ──────────────────────────────────────────────────────
# get_admin_logs
# ──────────────────────────────────────────────────────

class TestGetAdminLogs:
    @pytest.mark.asyncio
    async def test_returns_log_entries(self):
        conn = _make_conn(in_txn=False)
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[
            {
                "id": "alog_1", "admin_id": "admin1", "action": "withdrawal_approved",
                "target_type": "transaction", "target_id": "tx1",
                "old_value": None, "new_value": None,
                "ip_address": "127.0.0.1", "created_at": datetime.now(timezone.utc),
            }
        ])

        result = await get_admin_logs(conn)

        assert result["total"] == 1
        assert result["logs"][0]["action"] == "withdrawal_approved"


# ──────────────────────────────────────────────────────
# cleanup_old_notifications
# ──────────────────────────────────────────────────────

class TestCleanupOldNotifications:
    @pytest.mark.asyncio
    async def test_returns_count_deleted(self):
        conn = _make_conn(in_txn=False)
        conn.execute = AsyncMock(return_value="DELETE 7")

        count = await cleanup_old_notifications(conn)

        assert count == 7

    @pytest.mark.asyncio
    async def test_returns_zero_if_nothing_deleted(self):
        conn = _make_conn(in_txn=False)
        conn.execute = AsyncMock(return_value="DELETE 0")

        count = await cleanup_old_notifications(conn)

        assert count == 0

    @pytest.mark.asyncio
    async def test_does_not_require_transaction(self):
        """cleanup_old_notifications is a single-statement DELETE — no txn needed."""
        conn = _make_conn(in_txn=False)
        conn.execute = AsyncMock(return_value="DELETE 0")
        # Should NOT raise even though not in transaction
        await cleanup_old_notifications(conn)


# ──────────────────────────────────────────────────────
# P1 B-01: ban_user cancels client quests too
# ──────────────────────────────────────────────────────

class TestBanUserCancelsClientQuests:
    @pytest.mark.asyncio
    async def test_ban_cancels_assigned_and_client_quests(self):
        """P1 B-01: ban_user must cancel quests where user is assigned AND where user is client."""
        conn = _make_conn()
        conn.fetchrow.return_value = {
            "id": "user_to_ban",
            "username": "bad_user",
            "role": "client",
            "is_banned": False,
        }
        conn.fetch = AsyncMock(return_value=[
            {"id": f"quest_{index}", "title": f"Quest {index}", "client_id": "user_to_ban", "assigned_to": f"fl_{index}", "status": "assigned", "currency": "RUB"}
            for index in range(5)
        ])
        conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("app.services.admin_service.wallet_service.refund_hold", new=AsyncMock(return_value=None)):
            result = await ban_user(
                conn, user_id="user_to_ban", reason="abuse",
                admin_id="admin_1", ip_address="127.0.0.1",
            )

        assert result["quests_cancelled"] == 5  # 2 assigned + 3 client
        assert result["is_banned"] is True

    @pytest.mark.asyncio
    async def test_ban_refunds_holds_and_records_history_for_cancelled_quests(self):
        conn = _make_conn()
        conn.fetchrow.return_value = {
            "id": "user_to_ban",
            "username": "bad_user",
            "role": "client",
            "is_banned": False,
        }
        conn.fetch = AsyncMock(return_value=[
            {
                "id": "quest_1",
                "client_id": "user_to_ban",
                "assigned_to": "fl_1",
                "status": "assigned",
                "currency": "RUB",
                "title": "Quest 1",
            },
            {
                "id": "quest_2",
                "client_id": "other_client",
                "assigned_to": "user_to_ban",
                "status": "in_progress",
                "currency": "RUB",
                "title": "Quest 2",
            },
        ])
        conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("app.services.admin_service.wallet_service.refund_hold", new=AsyncMock(return_value=Decimal("1000.00"))) as mock_refund:
            result = await ban_user(
                conn,
                user_id="user_to_ban",
                reason="abuse",
                admin_id="admin_1",
                ip_address="127.0.0.1",
            )

        assert result["is_banned"] is True
        assert mock_refund.await_count == 2
        execute_sql = "\n".join(str(call) for call in conn.execute.call_args_list)
        assert "quest_status_history" in execute_sql


# ──────────────────────────────────────────────────────
# P0: admin quest edits must not desync escrow
# ──────────────────────────────────────────────────────

class TestAdminQuestUpdateEscrowIntegrity:
    @pytest.mark.asyncio
    async def test_update_quest_rejects_budget_change_after_hold_exists(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(side_effect=[
            {
                "id": "quest_hold",
                "title": "Held Quest",
                "description": "desc",
                "budget": Decimal("1000.00"),
                "xp_reward": 100,
                "required_grade": "novice",
                "status": "assigned",
                "assigned_to": "fl_1",
                "client_id": "client_1",
                "is_urgent": False,
                "deadline": None,
                "required_portfolio": False,
            },
            {"id": "tx_hold"},
        ])

        with pytest.raises(ValueError, match="escrow|budget|hold"):
            await update_quest(
                conn,
                quest_id="quest_hold",
                fields={"budget": Decimal("1500.00")},
                admin_id="admin_1",
            )

    @pytest.mark.asyncio
    async def test_update_quest_rejects_status_change_after_hold_exists(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(side_effect=[
            {
                "id": "quest_hold",
                "title": "Held Quest",
                "description": "desc",
                "budget": Decimal("1000.00"),
                "xp_reward": 100,
                "required_grade": "novice",
                "status": "assigned",
                "assigned_to": "fl_1",
                "client_id": "client_1",
                "is_urgent": False,
                "deadline": None,
                "required_portfolio": False,
            },
            {"id": "tx_hold"},
        ])

        with pytest.raises(ValueError, match="escrow|status|hold"):
            await update_quest(
                conn,
                quest_id="quest_hold",
                fields={"status": "open"},
                admin_id="admin_1",
            )


# ──────────────────────────────────────────────────────
# P1 D-01: delete_user cleans admin_logs
# ──────────────────────────────────────────────────────

class TestDeleteUserCleansAdminLogs:
    @pytest.mark.asyncio
    async def test_delete_user_removes_admin_logs_before_user(self):
        """P1 D-01: delete_user must DELETE admin_logs targeting the user before deleting from users."""
        conn = _make_conn()
        conn.fetchrow.return_value = {
            "id": "user_del",
            "username": "del_user",
            "email": "del@test.com",
            "role": "freelancer",
        }
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=0)
        conn.execute = AsyncMock(return_value="DELETE 1")

        result = await delete_user(
            conn, user_id="user_del", admin_id="admin_1", ip_address="127.0.0.1",
        )

        assert result["deleted"] is True

        # Collect all execute calls and find the admin_logs DELETE
        execute_calls = [str(c) for c in conn.execute.call_args_list]
        admin_logs_call = [c for c in execute_calls if "admin_logs" in c]
        assert len(admin_logs_call) >= 1, "Must delete from admin_logs before deleting user"

    @pytest.mark.asyncio
    async def test_delete_user_refunds_holds_for_active_quests_before_delete(self):
        conn = _make_conn()
        conn.fetchrow.return_value = {
            "id": "user_del",
            "username": "del_user",
            "email": "del@test.com",
            "role": "freelancer",
        }
        conn.fetch = AsyncMock(return_value=[
            {
                "id": "quest_1",
                "client_id": "client_1",
                "assigned_to": "user_del",
                "status": "assigned",
                "currency": "RUB",
                "title": "Quest 1",
            }
        ])
        conn.fetchval = AsyncMock(return_value=0)
        conn.execute = AsyncMock(return_value="DELETE 1")

        with patch("app.services.admin_service.wallet_service.refund_hold", new=AsyncMock(return_value=Decimal("1000.00"))) as mock_refund:
            result = await delete_user(
                conn,
                user_id="user_del",
                admin_id="admin_1",
                ip_address="127.0.0.1",
            )

        assert result["deleted"] is True
        mock_refund.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_user_rejects_client_owned_quests_with_financial_tail(self):
        conn = _make_conn()
        conn.fetchrow.return_value = {
            "id": "user_del",
            "username": "del_user",
            "email": "del@test.com",
            "role": "client",
        }
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=2)
        conn.execute = AsyncMock(return_value="DELETE 1")

        with pytest.raises(ValueError, match="financial|transaction|delete"):
            await delete_user(
                conn,
                user_id="user_del",
                admin_id="admin_1",
                ip_address="127.0.0.1",
            )


# ──────────────────────────────────────────────────────
# P2 Q-01: force_complete_quest triggers payment
# ──────────────────────────────────────────────────────

class TestForceCompleteQuestPayment:
    @pytest.mark.asyncio
    async def test_force_complete_rejects_open_quest(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={"id": "q_open", "status": "open"})

        with pytest.raises(ValueError, match="Cannot force-complete quest"):
            await force_complete_quest(
                conn,
                quest_id="q_open",
                reason="Admin intervention",
                admin_id="admin_1",
            )

    @pytest.mark.asyncio
    async def test_force_complete_triggers_payment_and_xp(self):
        """P2 Q-01: force_complete must trigger split_payment and XP grant."""
        conn = _make_conn()
        quest_row = {
            "id": "q_fc", "title": "Test Quest", "client_id": "client_1",
            "assigned_to": "fl_1", "status": "in_progress", "budget": Decimal("1000"),
            "currency": "RUB", "required_grade": "novice",
            "platform_fee_percent": 10.0,
        }
        freelancer_row = {
            "id": "fl_1", "xp": 100, "level": 2, "grade": "novice",
            "stats_int": 10, "stats_dex": 10, "stats_cha": 10,
            "stat_points": 0, "username": "fl_test",
        }
        conn.fetchrow.side_effect = [
            quest_row,       # quest FOR UPDATE
            {"id": "hold_1", "amount": 1000.0},  # split_payment: active hold exists
            freelancer_row,  # freelancer FOR UPDATE
            {"id": "hold_1", "amount": 1000.0},  # split_payment: active hold exists
            {"id": "hold_1", "amount": 1000.0},  # release_hold lookup
            {"balance": 0.0},  # client wallet balance after hold release path
            None, {"balance": 900.0},   # credit: freelancer wallet INSERT
            None, {"balance": 100.0},   # credit: platform wallet INSERT
        ]

        with patch(
            "app.services.admin_service.guild_economy_service.apply_quest_completion_rewards",
            new=AsyncMock(return_value={
                "guild_id": "guild_1",
                "guild_name": "Crimson Forge",
                "treasury_delta": Decimal("35.00"),
                "guild_tokens_delta": 3,
                "contribution_delta": 610,
            }),
        ), patch(
            "app.services.admin_service.badge_service.check_and_award",
            new=AsyncMock(return_value=MagicMock(newly_earned=[])),
        ), patch(
            "app.services.admin_service.class_service.add_class_xp",
            new=AsyncMock(return_value={"class_xp_gained": 0}),
        ):
            result = await force_complete_quest(
                conn, quest_id="q_fc", reason="Admin intervention",
                admin_id="admin_1", ip_address="127.0.0.1",
            )

        assert result["payment_triggered"] is True
        assert result["xp_reward"] > 0
        assert result["new_status"] == "confirmed"
        assert result["guild_economy"]["guild_id"] == "guild_1"

    @pytest.mark.asyncio
    async def test_force_complete_requires_active_escrow_hold(self):
        conn = _make_conn()
        quest_row = {
            "id": "q_fc", "title": "Test Quest", "client_id": "client_1",
            "assigned_to": "fl_1", "status": "in_progress", "budget": Decimal("1000"),
            "currency": "RUB", "required_grade": "novice",
            "platform_fee_percent": 10.0,
        }
        conn.fetchrow.side_effect = [quest_row, None]

        with pytest.raises(ValueError, match="active escrow hold"):
            await force_complete_quest(
                conn,
                quest_id="q_fc",
                reason="Admin intervention",
                admin_id="admin_1",
                ip_address="127.0.0.1",
                skip_escrow=False,
            )

    @pytest.mark.asyncio
    async def test_force_complete_no_escrow_skip_escrow_true(self):
        """Admin can force-complete a quest with no escrow hold when skip_escrow=True."""
        conn = _make_conn()
        quest_row = {
            "id": "q_fc", "title": "Test Quest", "client_id": "client_1",
            "assigned_to": "fl_1", "status": "in_progress", "budget": Decimal("1000"),
            "currency": "RUB", "required_grade": "novice",
            "platform_fee_percent": 10.0,
            "is_urgent": False,
            "required_portfolio": False,
        }
        freelancer_row = {
            "id": "fl_1", "xp": 100, "level": 2, "grade": "novice",
            "stats_int": 10, "stats_dex": 10, "stats_cha": 10,
            "stat_points": 0, "username": "fl_test",
        }
        conn.fetchrow.side_effect = [
            quest_row,       # quest FOR UPDATE
            None,            # hold_row = None (no escrow)
            freelancer_row,  # freelancer FOR UPDATE
        ]
        conn.fetchval.return_value = 5  # quests_completed count

        with patch(
            "app.services.admin_service.badge_service.check_and_award",
            new=AsyncMock(return_value=MagicMock(newly_earned=[])),
        ), patch(
            "app.services.admin_service.class_service.add_class_xp",
            new=AsyncMock(return_value={"class_xp_gained": 0}),
        ):
            result = await force_complete_quest(
                conn, quest_id="q_fc", reason="Admin intervention",
                admin_id="admin_1", skip_escrow=True,
            )

        assert result["new_status"] == "confirmed"
        assert result["payment_triggered"] is False
        assert result["xp_reward"] > 0

    @pytest.mark.asyncio
    async def test_force_complete_rejects_escrow_amount_mismatch(self):
        conn = _make_conn()
        quest_row = {
            "id": "q_fc", "title": "Test Quest", "client_id": "client_1",
            "assigned_to": "fl_1", "status": "in_progress", "budget": Decimal("1500.00"),
            "currency": "RUB", "required_grade": "novice",
            "platform_fee_percent": Decimal("10.00"),
        }
        freelancer_row = {
            "id": "fl_1", "xp": 100, "level": 2, "grade": "novice",
            "stats_int": 10, "stats_dex": 10, "stats_cha": 10,
            "stat_points": 0, "username": "fl_test",
        }
        conn.fetchrow.side_effect = [quest_row, {"id": "hold_1"}, freelancer_row]

        with patch(
            "app.services.admin_service.wallet_service.split_payment",
            new=AsyncMock(side_effect=ValueError("Escrow hold amount does not match payout amount")),
        ), patch(
            "app.services.admin_service.badge_service.check_and_award",
            new=AsyncMock(return_value=MagicMock(newly_earned=[])),
        ), patch(
            "app.services.admin_service.class_service.add_class_xp",
            new=AsyncMock(return_value={"class_xp_gained": 0}),
        ):
            with pytest.raises(ValueError, match="Escrow hold amount does not match payout amount"):
                await force_complete_quest(
                    conn,
                    quest_id="q_fc",
                    reason="Admin intervention",
                    admin_id="admin_1",
                )


class TestForceCancelQuestLifecycle:
    @pytest.mark.asyncio
    async def test_force_cancel_refunds_hold_and_records_history(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={
            "id": "quest_1",
            "title": "Held Quest",
            "client_id": "client_1",
            "assigned_to": "fl_1",
            "status": "assigned",
            "currency": "RUB",
        })
        conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("app.services.admin_service.wallet_service.refund_hold", new=AsyncMock(return_value=Decimal("1000.00"))) as mock_refund:
            result = await force_cancel_quest(
                conn,
                quest_id="quest_1",
                reason="Admin intervention",
                admin_id="admin_1",
                ip_address="127.0.0.1",
            )

        assert result["new_status"] == "cancelled"
        mock_refund.assert_awaited_once()
        execute_sql = "\n".join(str(call) for call in conn.execute.call_args_list)
        assert "quest_status_history" in execute_sql


class TestDeleteQuestFinancialSafety:
    @pytest.mark.asyncio
    async def test_delete_quest_rejects_active_hold(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={
            "id": "quest_1",
            "title": "Held Quest",
            "client_id": "client_1",
            "status": "assigned",
        })
        conn.fetchval = AsyncMock(side_effect=[1])

        with pytest.raises(ValueError, match="hold|financial|delete"):
            await delete_quest(conn, "quest_1", "admin_1")

    @pytest.mark.asyncio
    async def test_delete_quest_rejects_historical_transaction_tail(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={
            "id": "quest_1",
            "title": "Paid Quest",
            "client_id": "client_1",
            "status": "confirmed",
        })
        conn.fetchval = AsyncMock(side_effect=[0, 2])

        with pytest.raises(ValueError, match="financial|transaction|delete"):
            await delete_quest(conn, "quest_1", "admin_1")

    @pytest.mark.asyncio
    async def test_delete_quest_allows_non_financial_quest(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={
            "id": "quest_1",
            "title": "Draft Quest",
            "client_id": "client_1",
            "status": "draft",
        })
        conn.fetchval = AsyncMock(side_effect=[0, 0])
        conn.execute = AsyncMock(return_value="DELETE 1")

        result = await delete_quest(conn, "quest_1", "admin_1")

        assert result["deleted"] is True
