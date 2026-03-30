import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.lead import LeadCreateRequest, LeadResponse
from app.services import lead_service

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    body: LeadCreateRequest,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="lead_capture", limit=5, window_seconds=300)

    try:
        result = await lead_service.create_lead(
            conn,
            email=body.email,
            company_name=body.company_name,
            contact_name=body.contact_name,
            use_case=body.use_case,
            budget_band=body.budget_band,
            message=body.message,
            source=body.source,
            utm_source=body.utm_source,
            utm_medium=body.utm_medium,
            utm_campaign=body.utm_campaign,
            utm_term=body.utm_term,
            utm_content=body.utm_content,
            ref=body.ref,
            landing_path=body.landing_path,
        )
        return LeadResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))