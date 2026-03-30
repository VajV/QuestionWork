from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg


async def create_lead(
    conn: asyncpg.Connection,
    *,
    email: str,
    company_name: str,
    contact_name: str,
    use_case: str,
    budget_band: Optional[str],
    message: Optional[str],
    source: str,
    utm_source: Optional[str],
    utm_medium: Optional[str],
    utm_campaign: Optional[str],
    utm_term: Optional[str],
    utm_content: Optional[str],
    ref: Optional[str],
    landing_path: Optional[str],
) -> dict:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("Email обязателен")

    lead_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    next_contact_at = created_at + timedelta(days=1)

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO growth_leads (
                id,
                email,
                company_name,
                contact_name,
                use_case,
                budget_band,
                message,
                source,
                utm_source,
                utm_medium,
                utm_campaign,
                utm_term,
                utm_content,
                ref,
                landing_path,
                status,
                last_contacted_at,
                next_contact_at,
                nurture_stage,
                converted_user_id,
                created_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
            )
            """,
            lead_id,
            normalized_email,
            company_name,
            contact_name,
            use_case,
            budget_band,
            message,
            source,
            utm_source,
            utm_medium,
            utm_campaign,
            utm_term,
            utm_content,
            ref,
            landing_path,
            "new",
            None,
            next_contact_at,
            "intake",
            None,
            created_at,
        )

    return {
        "id": lead_id,
        "email": normalized_email,
        "company_name": company_name,
        "contact_name": contact_name,
        "use_case": use_case,
        "budget_band": budget_band,
        "message": message,
        "source": source,
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": utm_campaign,
        "utm_term": utm_term,
        "utm_content": utm_content,
        "ref": ref,
        "landing_path": landing_path,
        "status": "new",
        "last_contacted_at": None,
        "next_contact_at": next_contact_at,
        "nurture_stage": "intake",
        "converted_user_id": None,
        "created_at": created_at,
    }