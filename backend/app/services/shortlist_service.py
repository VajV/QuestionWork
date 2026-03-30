"""Business logic for client shortlists."""

import secrets

import asyncpg


async def add_to_shortlist(
    conn: asyncpg.Connection, client_id: str, freelancer_id: str,
) -> dict:
    """Add a freelancer to the client's shortlist. Idempotent."""
    shortlist_id = f"sl_{secrets.token_hex(8)}"
    row = await conn.fetchrow(
        """
        INSERT INTO shortlists (id, client_id, freelancer_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (client_id, freelancer_id) DO NOTHING
        RETURNING id, client_id, freelancer_id, created_at
        """,
        shortlist_id, client_id, freelancer_id,
    )
    if not row:
        row = await conn.fetchrow(
            "SELECT id, client_id, freelancer_id, created_at FROM shortlists WHERE client_id = $1 AND freelancer_id = $2",
            client_id, freelancer_id,
        )
    return dict(row) if row else {}


async def remove_from_shortlist(
    conn: asyncpg.Connection, client_id: str, freelancer_id: str,
) -> bool:
    """Remove a freelancer from the client's shortlist."""
    result = await conn.execute(
        "DELETE FROM shortlists WHERE client_id = $1 AND freelancer_id = $2",
        client_id, freelancer_id,
    )
    return result.endswith("1")


async def get_shortlist(
    conn: asyncpg.Connection, client_id: str, limit: int = 50, offset: int = 0,
) -> dict:
    """Return the client's shortlist with total count."""
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM shortlists WHERE client_id = $1", client_id,
    )
    rows = await conn.fetch(
        """
        SELECT id, client_id, freelancer_id, created_at
        FROM shortlists
        WHERE client_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        client_id, limit, offset,
    )
    return {
        "entries": [dict(r) for r in rows],
        "total": int(total or 0),
    }


async def get_shortlisted_ids(
    conn: asyncpg.Connection, client_id: str,
) -> list[str]:
    """Return just the freelancer IDs in the shortlist (for quick icon checks)."""
    rows = await conn.fetch(
        "SELECT freelancer_id FROM shortlists WHERE client_id = $1",
        client_id,
    )
    return [r["freelancer_id"] for r in rows]
