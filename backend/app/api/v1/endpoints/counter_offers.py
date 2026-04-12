"""Counter-offer endpoints — price negotiation on quest applications."""

from decimal import Decimal
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.services import counter_offer_service

router = APIRouter(prefix="/quests", tags=["Counter-Offers"])


class CounterOfferRequest(BaseModel):
    counter_price: Decimal = Field(..., gt=0, le=10_000_000, description="Proposed counter price")
    message: Optional[str] = Field(None, max_length=500)


class CounterOfferRespondRequest(BaseModel):
    accept: bool


class CounterOfferResponse(BaseModel):
    id: str
    quest_id: str
    counter_offer_price: Decimal
    counter_offer_status: str
    counter_offer_message: Optional[str] = None
    counter_offered_at: str


class CounterOfferRespondResponse(BaseModel):
    id: str
    quest_id: str
    counter_offer_status: str
    counter_responded_at: str


@router.post(
    "/{quest_id}/applications/{application_id}/counter-offer",
    response_model=CounterOfferResponse,
    status_code=status.HTTP_200_OK,
    summary="Client sends a counter-offer price",
)
async def make_counter_offer(
    quest_id: str,
    application_id: str,
    body: CounterOfferRequest,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="counter_offer_make", limit=20, window_seconds=60)
    try:
        async with conn.transaction():
            result = await counter_offer_service.make_counter_offer(
                conn,
                quest_id=quest_id,
                application_id=application_id,
                client_id=current_user.id,
                counter_price=body.counter_price,
                message=body.message,
            )
        return CounterOfferResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post(
    "/{quest_id}/applications/{application_id}/counter-offer/respond",
    response_model=CounterOfferRespondResponse,
    status_code=status.HTTP_200_OK,
    summary="Freelancer accepts or declines a counter-offer",
)
async def respond_to_counter_offer(
    quest_id: str,
    application_id: str,
    body: CounterOfferRespondRequest,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="counter_offer_respond", limit=20, window_seconds=60)
    try:
        async with conn.transaction():
            result = await counter_offer_service.respond_to_counter_offer(
                conn,
                quest_id=quest_id,
                application_id=application_id,
                freelancer_id=current_user.id,
                accept=body.accept,
            )
        return CounterOfferRespondResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
