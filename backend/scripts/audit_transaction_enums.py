"""Preflight audit for transaction type/status values before enum-check rollout."""

from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

from app.services.wallet_service import ALLOWED_TRANSACTION_STATUSES, ALLOWED_TRANSACTION_TYPES


async def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(database_url)
    try:
        invalid_types = await conn.fetch(
            """
            SELECT type, COUNT(*) AS row_count
            FROM transactions
            WHERE type IS NULL OR NOT (type = ANY($1::text[]))
            GROUP BY type
            ORDER BY row_count DESC, type NULLS FIRST
            """,
            list(ALLOWED_TRANSACTION_TYPES),
        )
        invalid_statuses = await conn.fetch(
            """
            SELECT status, COUNT(*) AS row_count
            FROM transactions
            WHERE status IS NULL OR NOT (status = ANY($1::text[]))
            GROUP BY status
            ORDER BY row_count DESC, status NULLS FIRST
            """,
            list(ALLOWED_TRANSACTION_STATUSES),
        )
    finally:
        await conn.close()

    if invalid_types:
        print("Invalid transaction types detected:")
        for row in invalid_types:
            print(f"  type={row['type']!r} rows={row['row_count']}")

    if invalid_statuses:
        print("Invalid transaction statuses detected:")
        for row in invalid_statuses:
            print(f"  status={row['status']!r} rows={row['row_count']}")

    if invalid_types or invalid_statuses:
        return 1

    print("Transaction enum audit passed: no invalid types or statuses found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))