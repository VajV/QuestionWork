"""
Template service — CRUD for quest templates (reusable quest blueprints).

Templates are personal to each client.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


async def create_template(
    conn: asyncpg.Connection,
    owner_id: str,
    *,
    name: str,
    title: str,
    description: str = "",
    required_grade: str = "novice",
    skills: list[str] | None = None,
    budget = 0,
    currency: str = "RUB",
    is_urgent: bool = False,
    required_portfolio: bool = False,
) -> dict:
    """Create a new quest template."""
    template_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    skills = skills or []

    await conn.execute(
        """
        INSERT INTO quest_templates
            (id, owner_id, name, title, description, required_grade,
             skills, budget, currency, is_urgent, required_portfolio,
             created_at, updated_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        """,
        template_id,
        owner_id,
        name,
        title,
        description,
        required_grade,
        json.dumps(skills),
        budget,
        currency,
        is_urgent,
        required_portfolio,
        now,
        now,
    )

    return _to_dict(
        template_id, owner_id, name, title, description, required_grade,
        skills, budget, currency, is_urgent, required_portfolio, now, now,
    )


async def list_templates(
    conn: asyncpg.Connection,
    owner_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List templates belonging to a user."""
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM quest_templates WHERE owner_id = $1",
        owner_id,
    )
    rows = await conn.fetch(
        """
        SELECT * FROM quest_templates
        WHERE owner_id = $1
        ORDER BY updated_at DESC
        LIMIT $2 OFFSET $3
        """,
        owner_id,
        limit,
        offset,
    )
    return {
        "templates": [_row_to_dict(r) for r in rows],
        "total": total or 0,
    }


async def get_template(
    conn: asyncpg.Connection,
    template_id: str,
    owner_id: str,
) -> dict | None:
    """Get a single template (must belong to owner)."""
    row = await conn.fetchrow(
        "SELECT * FROM quest_templates WHERE id = $1 AND owner_id = $2",
        template_id,
        owner_id,
    )
    return _row_to_dict(row) if row else None


async def update_template(
    conn: asyncpg.Connection,
    template_id: str,
    owner_id: str,
    **fields,
) -> dict | None:
    """Update mutable fields. Returns updated template or None if not found."""
    existing = await conn.fetchrow(
        "SELECT * FROM quest_templates WHERE id = $1 AND owner_id = $2",
        template_id,
        owner_id,
    )
    if not existing:
        return None

    allowed = {
        "name", "title", "description", "required_grade",
        "skills", "budget", "currency", "is_urgent", "required_portfolio",
    }
    sets = []
    values: list = []
    idx = 1
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        if k == "skills":
            v = json.dumps(v)
        idx += 1
        sets.append(f"{k} = ${idx}")
        values.append(v)

    if not sets:
        return _row_to_dict(existing)

    now = datetime.now(timezone.utc)
    idx += 1
    sets.append(f"updated_at = ${idx}")
    values.append(now)

    query = f"UPDATE quest_templates SET {', '.join(sets)} WHERE id = $1 RETURNING *"
    row = await conn.fetchrow(query, template_id, *values)
    return _row_to_dict(row) if row else None


async def delete_template(
    conn: asyncpg.Connection,
    template_id: str,
    owner_id: str,
) -> bool:
    """Delete a template. Returns True if deleted."""
    result = await conn.execute(
        "DELETE FROM quest_templates WHERE id = $1 AND owner_id = $2",
        template_id,
        owner_id,
    )
    return result == "DELETE 1"


# ────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────

def _row_to_dict(row: asyncpg.Record) -> dict:
    skills_raw = row["skills"]
    if isinstance(skills_raw, str):
        try:
            skills = json.loads(skills_raw)
        except json.JSONDecodeError:
            logger.warning("Malformed skills JSON in template %s", row["id"])
            skills = []
    elif isinstance(skills_raw, list):
        skills = skills_raw
    else:
        skills = []

    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "name": row["name"],
        "title": row["title"],
        "description": row["description"],
        "required_grade": row["required_grade"],
        "skills": skills,
        "budget": row["budget"],
        "currency": row["currency"],
        "is_urgent": row["is_urgent"],
        "required_portfolio": row["required_portfolio"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def _to_dict(
    id: str, owner_id: str, name: str, title: str, description: str,
    required_grade: str, skills: list, budget: Decimal, currency: str,
    is_urgent: bool, required_portfolio: bool,
    created_at: datetime, updated_at: datetime,
) -> dict:
    return {
        "id": id,
        "owner_id": owner_id,
        "name": name,
        "title": title,
        "description": description,
        "required_grade": required_grade,
        "skills": skills,
        "budget": budget,
        "currency": currency,
        "is_urgent": is_urgent,
        "required_portfolio": required_portfolio,
        "created_at": created_at.isoformat(),
        "updated_at": updated_at.isoformat(),
    }
