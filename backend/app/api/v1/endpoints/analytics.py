"""Analytics endpoints — first-party funnel event ingestion and KPI reporting."""

from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, Request, status

from app.api.deps import get_optional_user, require_admin
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.analytics import AnalyticsEventBatch, AnalyticsIngestResponse, FunnelKPIs
from app.models.user import UserProfile
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post(
    "/events",
    response_model=AnalyticsIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a batch of analytics events",
)
async def ingest_events(
    body: AnalyticsEventBatch,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
    current_user: Optional[UserProfile] = Depends(get_optional_user),
) -> AnalyticsIngestResponse:
    """Public endpoint (no auth required).

    If a valid Bearer token is present the events are attributed to that user.
    Rate-limited per IP to 120 requests/minute to prevent spam.
    """
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="analytics_ingest", limit=120, window_seconds=60)

    user_id = current_user.id if current_user else None

    events_dicts = [
        {
            "event_name": ev.event_name,
            "session_id": ev.session_id,
            "role": ev.role or (current_user.role.value if current_user else None),
            "source": ev.source,
            "path": ev.path,
            "properties": ev.properties,
            "timestamp": ev.timestamp,
        }
        for ev in body.events
    ]

    ingested = await analytics_service.ingest_events_batch(
        conn, user_id=user_id, events=events_dicts
    )
    return AnalyticsIngestResponse(ingested=ingested)


@router.get(
    "/funnel-kpis",
    response_model=FunnelKPIs,
    summary="Admin: get growth funnel KPIs",
)
async def get_funnel_kpis(
    conn: asyncpg.Connection = Depends(get_db_connection),
    _admin: UserProfile = Depends(require_admin),
) -> FunnelKPIs:
    """Returns all-time funnel conversion counts for the admin growth dashboard."""
    data = await analytics_service.get_funnel_kpis(conn)
    return FunnelKPIs(**data)
