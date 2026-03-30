from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.services import invoice_service


class _InvoiceConn:
    def __init__(self):
        self.users = {
            "freelancer_1": {"username": "freelancer_user"},
            "client_1": {"username": "client_user"},
        }
        self.transactions = {
            "tx_receipt": {
                "id": "tx_receipt",
                "user_id": "freelancer_1",
                "quest_id": "quest_1",
                "amount": Decimal("120.00"),
                "currency": "RUB",
                "type": "income",
                "status": "completed",
                "created_at": datetime(2026, 3, 17, 10, 15, tzinfo=timezone.utc),
            }
        }
        self.statement_rows = [
            {
                "id": "tx_income",
                "user_id": "freelancer_1",
                "quest_id": "quest_1",
                "amount": Decimal("120.00"),
                "currency": "RUB",
                "type": "income",
                "status": "completed",
                "created_at": datetime(2026, 3, 10, 10, 15, tzinfo=timezone.utc),
            },
            {
                "id": "tx_withdraw",
                "user_id": "freelancer_1",
                "quest_id": None,
                "amount": Decimal("20.00"),
                "currency": "RUB",
                "type": "withdrawal",
                "status": "pending",
                "created_at": datetime(2026, 3, 11, 9, 0, tzinfo=timezone.utc),
            },
        ]
        self.quests = {
            "quest_1": {
                "id": "quest_1",
                "title": "Landing page",
                "client_id": "client_1",
                "assigned_to": "freelancer_1",
                "budget": Decimal("133.30"),
                "platform_fee_percent": Decimal("10.0"),
            }
        }

    async def fetchrow(self, query, *args):
        compact = " ".join(query.split())
        if "FROM transactions" in compact:
            tx_id, user_id = args
            tx = self.transactions.get(tx_id)
            if tx and tx["user_id"] == user_id:
                return tx
            return None
        if "FROM users WHERE id = $1" in compact:
            return self.users.get(args[0])
        if "FROM quests WHERE id = $1" in compact:
            return self.quests.get(args[0])
        raise AssertionError(f"Unexpected fetchrow query: {compact}")

    async def fetch(self, query, *args):
        compact = " ".join(query.split())
        if "FROM transactions" in compact:
            user_id = args[0]
            return [row for row in self.statement_rows if row["user_id"] == user_id]
        raise AssertionError(f"Unexpected fetch query: {compact}")


@pytest.mark.asyncio
async def test_get_wallet_receipt_data_derives_counterparty_and_fee():
    conn = _InvoiceConn()

    receipt = await invoice_service.get_wallet_receipt_data(conn, "freelancer_1", "tx_receipt")

    assert receipt["transaction_id"] == "tx_receipt"
    assert receipt["counterparty"] == "client_user"
    assert receipt["client_name"] == "client_user"
    assert receipt["freelancer_name"] == "freelancer_user"
    assert receipt["platform_fee"] == "13.33"
    assert receipt["amount_label"] == "120.00"


@pytest.mark.asyncio
async def test_get_wallet_statement_data_builds_totals_for_range():
    conn = _InvoiceConn()

    statement = await invoice_service.get_wallet_statement_data(
        conn,
        "freelancer_1",
        date(2026, 3, 10),
        date(2026, 3, 11),
    )

    assert statement["transaction_count"] == 2
    assert statement["total_inflow_label"] == "120.00"
    assert statement["total_outflow_label"] == "20.00"
    assert statement["transactions"][0]["id"] == "tx_income"
    assert statement["transactions"][0]["quest_title"] == "Landing page"
    assert statement["transactions"][0]["client_name"] == "client_user"
    assert statement["transactions"][0]["freelancer_name"] == "freelancer_user"
    assert statement["transactions"][0]["platform_fee"] == "13.33"


def test_generate_receipt_pdf_returns_pdf_bytes():
    pdf = invoice_service.generate_receipt_pdf(
        {
            "receipt_id": "receipt-tx_1",
            "transaction_id": "tx_1",
            "account_owner": "freelancer_user",
            "created_at_label": "2026-03-17 10:15 UTC",
            "type": "income",
            "status": "completed",
            "amount_label": "120.00",
            "currency": "RUB",
            "counterparty": "client_user",
            "platform_fee": "13.33",
            "platform_fee_percent": "10.0",
            "quest_title": "Landing page",
            "quest_id": "quest_1",
            "client_name": "client_user",
            "freelancer_name": "freelancer_user",
        }
    )

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500


def test_generate_statement_pdf_and_csv_return_content():
    statement_data = {
        "account_owner": "freelancer_user",
        "date_from": date(2026, 3, 10),
        "date_to": date(2026, 3, 11),
        "period_label": "2026-03-10 .. 2026-03-11",
        "currency": "RUB",
        "transaction_count": 1,
        "total_inflow_label": "120.00",
        "total_outflow_label": "0.00",
        "transactions": [
            {
                "id": "tx_income",
                "quest_id": "quest_1",
                "amount": Decimal("120.00"),
                "amount_label": "120.00",
                "platform_fee": "13.33",
                "currency": "RUB",
                "type": "income",
                "status": "completed",
                "created_at": datetime(2026, 3, 10, 10, 15, tzinfo=timezone.utc),
                "created_at_label": "2026-03-10 10:15 UTC",
                "quest_title": "Landing page",
                "client_name": "client_user",
                "freelancer_name": "freelancer_user",
            }
        ],
    }

    pdf = invoice_service.generate_statement_pdf(statement_data)
    csv_data = invoice_service.generate_statement_csv(statement_data).decode("utf-8")

    assert pdf.startswith(b"%PDF")
    assert "transaction_id,created_at,type,status,amount,currency,platform_fee,quest_id,quest_title,client_name,freelancer_name" in csv_data
    assert "tx_income" in csv_data
    assert "Landing page" in csv_data