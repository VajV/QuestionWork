"""Wallet receipt and statement document generation."""

from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from io import BytesIO, StringIO

import asyncpg
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.wallet_service import quantize_money


class DocumentNotFoundError(LookupError):
    """Raised when a requested wallet document source row is not found."""


def _ensure_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _format_decimal(value: Decimal | str | int | float | None) -> str:
    if value is None:
        return "-"
    normalized = quantize_money(value)
    return f"{normalized:.2f}"


def _format_timestamp(value: datetime | None) -> str:
    timestamp = _ensure_datetime(value)
    return timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _pdf_safe(value: object | None) -> str:
    if value is None:
        return "-"
    return str(value)


def _build_statement_styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "StatementTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "StatementSection",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "StatementBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
        ),
        "body_right": ParagraphStyle(
            "StatementBodyRight",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            alignment=2,
        ),
        "header": ParagraphStyle(
            "StatementHeader",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
        ),
        "small": ParagraphStyle(
            "StatementSmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#475467"),
        ),
    }


def _statement_paragraph(value: object | None, style: ParagraphStyle, *, allow_markup: bool = False) -> Paragraph:
    text = _pdf_safe(value)
    if allow_markup:
        text = text.replace("&", "&amp;").replace("\n", "<br/>")
    else:
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    return Paragraph(text, style)


def _statement_page_chrome(pdf: canvas.Canvas, doc: SimpleDocTemplate) -> None:
    page_number = pdf.getPageNumber()
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.HexColor("#475467"))
    pdf.drawRightString(doc.pagesize[0] - doc.rightMargin, 10 * mm, f"Page {page_number}")
    pdf.setFillColor(colors.black)


def _statement_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_dt, end_dt


def _is_inflow(tx_type: str) -> bool:
    return tx_type in {"credit", "income", "commission", "quest_payment"}


def _calculate_platform_fee_from_quest(quest: dict | None) -> Decimal | None:
    if not quest:
        return None
    fee_percent = quest.get("platform_fee_percent")
    budget = quest.get("budget")
    if fee_percent is None or budget is None:
        return None
    return quantize_money(Decimal(str(budget)) * Decimal(str(fee_percent)) / Decimal("100"))


async def _resolve_user_label(conn: asyncpg.Connection, user_id: str | None) -> str:
    if not user_id:
        return "-"
    row = await conn.fetchrow("SELECT username FROM users WHERE id = $1", user_id)
    if row and row.get("username"):
        return row["username"]
    return user_id


async def _resolve_quest_context(conn: asyncpg.Connection, quest_id: str | None, owner_user_id: str) -> dict:
    if not quest_id:
        return {
            "quest_title": None,
            "client_name": "-",
            "freelancer_name": "-",
            "counterparty": "-",
            "platform_fee_amount": None,
            "platform_fee_percent": None,
        }

    quest = await conn.fetchrow(
        "SELECT id, title, client_id, assigned_to, platform_fee_percent, budget FROM quests WHERE id = $1",
        quest_id,
    )
    if not quest:
        return {
            "quest_title": None,
            "client_name": "-",
            "freelancer_name": "-",
            "counterparty": "-",
            "platform_fee_amount": None,
            "platform_fee_percent": None,
        }

    client_name = await _resolve_user_label(conn, quest.get("client_id"))
    freelancer_name = await _resolve_user_label(conn, quest.get("assigned_to"))
    counterparty_id: str | None = None
    if quest.get("assigned_to") == owner_user_id:
        counterparty_id = quest.get("client_id")
    elif quest.get("client_id") == owner_user_id:
        counterparty_id = quest.get("assigned_to")

    counterparty = await _resolve_user_label(conn, counterparty_id)
    fee_percent = quest.get("platform_fee_percent")

    return {
        "quest_title": quest.get("title"),
        "client_name": client_name,
        "freelancer_name": freelancer_name,
        "counterparty": counterparty,
        "platform_fee_amount": _calculate_platform_fee_from_quest(quest),
        "platform_fee_percent": fee_percent,
    }


async def get_wallet_receipt_data(
    conn: asyncpg.Connection,
    user_id: str,
    transaction_id: str,
) -> dict:
    tx = await conn.fetchrow(
        """
        SELECT id, user_id, quest_id, amount, currency, type, status, created_at
        FROM transactions
        WHERE id = $1 AND user_id = $2
        """,
        transaction_id,
        user_id,
    )
    if not tx:
        raise DocumentNotFoundError("Transaction not found")

    owner_label = await _resolve_user_label(conn, user_id)
    quest_context = await _resolve_quest_context(conn, tx.get("quest_id"), user_id)
    amount = quantize_money(tx["amount"])
    fee_display = "-"

    exact_platform_fee = quest_context.get("platform_fee_amount")
    if tx["type"] == "platform_fee":
        fee_display = _format_decimal(amount)
    elif exact_platform_fee is not None and tx["type"] in {"income", "quest_payment", "commission", "expense", "hold", "release"}:
        fee_display = _format_decimal(exact_platform_fee)

    created_at = _ensure_datetime(tx.get("created_at"))
    return {
        "receipt_id": f"receipt-{tx['id']}",
        "transaction_id": tx["id"],
        "account_owner": owner_label,
        "created_at": created_at,
        "created_at_label": _format_timestamp(created_at),
        "amount": amount,
        "amount_label": _format_decimal(amount),
        "currency": tx["currency"],
        "type": tx["type"],
        "status": tx["status"],
        "quest_id": tx.get("quest_id"),
        "quest_title": quest_context.get("quest_title"),
        "client_name": quest_context.get("client_name", "-"),
        "freelancer_name": quest_context.get("freelancer_name", "-"),
        "counterparty": quest_context.get("counterparty", "-"),
        "platform_fee": fee_display,
        "platform_fee_percent": quest_context.get("platform_fee_percent"),
    }


async def get_wallet_statement_data(
    conn: asyncpg.Connection,
    user_id: str,
    date_from: date,
    date_to: date,
) -> dict:
    if date_from > date_to:
        raise ValueError("'from' must be less than or equal to 'to'")

    start_dt, end_dt = _statement_bounds(date_from, date_to)
    rows = await conn.fetch(
        """
        SELECT id, user_id, quest_id, amount, currency, type, status, created_at
        FROM transactions
        WHERE user_id = $1
          AND created_at >= $2
          AND created_at < $3
        ORDER BY created_at DESC
        """,
        user_id,
        start_dt,
        end_dt,
    )

    owner_label = await _resolve_user_label(conn, user_id)
    transactions: list[dict] = []
    total_inflow = Decimal("0")
    total_outflow = Decimal("0")
    currency = rows[0]["currency"] if rows else "RUB"
    quest_context_cache: dict[str, dict] = {}

    for row in rows:
        amount = quantize_money(row["amount"])
        created_at = _ensure_datetime(row.get("created_at"))
        quest_id = row.get("quest_id")
        if quest_id and quest_id not in quest_context_cache:
            quest_context_cache[quest_id] = await _resolve_quest_context(conn, quest_id, user_id)
        quest_context = quest_context_cache.get(quest_id, {
            "quest_title": None,
            "client_name": "-",
            "freelancer_name": "-",
            "platform_fee_amount": None,
        })
        transactions.append(
            {
                "id": row["id"],
                "quest_id": quest_id,
                "quest_title": quest_context.get("quest_title") or "-",
                "client_name": quest_context.get("client_name", "-"),
                "freelancer_name": quest_context.get("freelancer_name", "-"),
                "amount": amount,
                "amount_label": _format_decimal(amount),
                "platform_fee": _format_decimal(quest_context.get("platform_fee_amount")),
                "currency": row["currency"],
                "type": row["type"],
                "status": row["status"],
                "created_at": created_at,
                "created_at_label": _format_timestamp(created_at),
            }
        )
        if _is_inflow(row["type"]):
            total_inflow += amount
        else:
            total_outflow += amount

    return {
        "account_owner": owner_label,
        "date_from": date_from,
        "date_to": date_to,
        "period_label": f"{date_from.isoformat()} .. {date_to.isoformat()}",
        "currency": currency,
        "transactions": transactions,
        "transaction_count": len(transactions),
        "total_inflow": quantize_money(total_inflow),
        "total_outflow": quantize_money(total_outflow),
        "total_inflow_label": _format_decimal(total_inflow),
        "total_outflow_label": _format_decimal(total_outflow),
    }


def generate_receipt_pdf(receipt_data: dict) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    top = height - 56

    pdf.setTitle(f"Receipt {receipt_data['transaction_id']}")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(56, top, "QuestionWork Wallet Receipt")

    pdf.setFont("Helvetica", 11)
    lines = [
        ("Receipt ID", receipt_data["receipt_id"]),
        ("Transaction ID", receipt_data["transaction_id"]),
        ("Account owner", receipt_data["account_owner"]),
        ("Date", receipt_data["created_at_label"]),
        ("Type", receipt_data["type"]),
        ("Status", receipt_data["status"]),
        ("Amount", f"{receipt_data['amount_label']} {receipt_data['currency']}"),
        ("Quest title", receipt_data.get("quest_title") or "-"),
        ("Client", receipt_data.get("client_name") or "-"),
        ("Freelancer", receipt_data.get("freelancer_name") or "-"),
        ("Counterparty", receipt_data["counterparty"]),
        ("Platform fee", receipt_data["platform_fee"]),
        ("Fee percent", str(receipt_data.get("platform_fee_percent") or "-")),
        ("Quest ID", receipt_data.get("quest_id") or "-"),
    ]

    y = top - 36
    for label, value in lines:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(56, y, f"{label}:")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(180, y, str(value))
        y -= 22

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def generate_statement_pdf(statement_data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"Statement {statement_data['date_from']} {statement_data['date_to']}",
    )
    styles = _build_statement_styles()

    elements = [
        Paragraph("QuestionWork Wallet Statement", styles["title"]),
        Paragraph("Accounting extract for wallet activity in the selected period.", styles["small"]),
        Spacer(1, 6),
    ]

    summary_table = Table(
        [
            [
                _statement_paragraph("Account owner", styles["section"]),
                _statement_paragraph(statement_data["account_owner"], styles["body"]),
                _statement_paragraph("Period", styles["section"]),
                _statement_paragraph(statement_data["period_label"], styles["body"]),
            ],
            [
                _statement_paragraph("Transactions", styles["section"]),
                _statement_paragraph(statement_data["transaction_count"], styles["body"]),
                _statement_paragraph("Currency", styles["section"]),
                _statement_paragraph(statement_data["currency"], styles["body"]),
            ],
            [
                _statement_paragraph("Total inflow", styles["section"]),
                _statement_paragraph(f"{statement_data['total_inflow_label']} {statement_data['currency']}", styles["body"]),
                _statement_paragraph("Total outflow", styles["section"]),
                _statement_paragraph(f"{statement_data['total_outflow_label']} {statement_data['currency']}", styles["body"]),
            ],
        ],
        colWidths=[30 * mm, 56 * mm, 30 * mm, 56 * mm],
        hAlign="LEFT",
    )
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.extend([summary_table, Spacer(1, 8)])

    table_rows = [[
        _statement_paragraph("Date", styles["header"]),
        _statement_paragraph("Transaction", styles["header"]),
        _statement_paragraph("Type / status", styles["header"]),
        _statement_paragraph("Amount", styles["header"]),
        _statement_paragraph("Platform fee", styles["header"]),
        _statement_paragraph("Quest", styles["header"]),
        _statement_paragraph("Parties", styles["header"]),
    ]]

    transactions = statement_data["transactions"]
    if transactions:
        for tx in transactions:
            table_rows.append([
                _statement_paragraph(tx["created_at_label"], styles["body"]),
                _statement_paragraph(tx["id"], styles["body"]),
                _statement_paragraph(f"{tx['type']}<br/>{tx['status']}", styles["body"], allow_markup=True),
                _statement_paragraph(f"{tx['amount_label']} {tx['currency']}", styles["body_right"]),
                _statement_paragraph(tx.get("platform_fee") or "-", styles["body_right"]),
                _statement_paragraph(f"{tx.get('quest_title') or '-'}<br/>{tx.get('quest_id') or '-'}", styles["body"], allow_markup=True),
                _statement_paragraph(
                    f"Client: {tx.get('client_name') or '-'}<br/>Freelancer: {tx.get('freelancer_name') or '-'}",
                    styles["body"],
                    allow_markup=True,
                ),
            ])
    else:
        table_rows.append([
            _statement_paragraph("No wallet transactions in the selected period.", styles["body"]),
            "",
            "",
            "",
            "",
            "",
            "",
        ])

    transactions_table = Table(
        table_rows,
        colWidths=[28 * mm, 28 * mm, 26 * mm, 24 * mm, 23 * mm, 36 * mm, 28 * mm],
        repeatRows=1,
        hAlign="LEFT",
    )
    transactions_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (3, 1), (4, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    elements.extend([
        Paragraph("Transaction ledger", styles["section"]),
        transactions_table,
        Spacer(1, 8),
    ])

    totals_table = Table(
        [
            [_statement_paragraph("Debit total", styles["section"]), _statement_paragraph(f"{statement_data['total_outflow_label']} {statement_data['currency']}", styles["body_right"])],
            [_statement_paragraph("Credit total", styles["section"]), _statement_paragraph(f"{statement_data['total_inflow_label']} {statement_data['currency']}", styles["body_right"])],
        ],
        colWidths=[38 * mm, 34 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(totals_table)

    doc.build(elements, onFirstPage=_statement_page_chrome, onLaterPages=_statement_page_chrome)
    return buffer.getvalue()


def generate_statement_csv(statement_data: dict) -> bytes:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "transaction_id",
        "created_at",
        "type",
        "status",
        "amount",
        "currency",
        "platform_fee",
        "quest_id",
        "quest_title",
        "client_name",
        "freelancer_name",
    ])
    for tx in statement_data["transactions"]:
        writer.writerow(
            [
                tx["id"],
                tx["created_at"].isoformat(),
                tx["type"],
                tx["status"],
                tx["amount_label"],
                tx["currency"],
                tx.get("platform_fee") or "-",
                tx.get("quest_id") or "",
                tx.get("quest_title") or "",
                tx.get("client_name") or "",
                tx.get("freelancer_name") or "",
            ]
        )
    return output.getvalue().encode("utf-8")