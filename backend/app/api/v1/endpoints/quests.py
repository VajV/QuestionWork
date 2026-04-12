"""
Endpoints для работы с квестами — thin controller layer.

Business logic delegated to app.services.quest_service.
Auth dependencies imported from app.api.deps.
"""

import logging
from decimal import Decimal
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.deps import get_optional_user, require_auth
from app.core.ratelimit import check_rate_limit, check_user_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.quest import (
    Quest,
    QuestApplicationCreate,
    QuestCompletionCreate,
    QuestCreate,
    QuestInviteCreate,
    QuestInviteResponse,
    QuestListResponse,
    QuestRevisionRequest,
    QuestUpdate,
    QuestStatusEnum,
    TrainingQuestCreate,
    RaidQuestCreate,
    RaidJoinRequest,
    RaidPartyResponse,
    QuestChainCreate,
    ChainDetailResponse,
    ChainListResponse,
)
from app.models.matching import FreelancerRecommendationListResponse
from app.models.user import GradeEnum, UserProfile
from app.services import matching_service, quest_service
from app.services.wallet_service import EscrowMismatchError, InsufficientFundsError


ESCROW_CONFLICT_DETAIL = "Quest payment state is inconsistent. Please contact support."

logger = logging.getLogger(__name__)


class AssignQuestRequest(BaseModel):
    freelancer_id: str = Field(..., min_length=1, description="ID of the freelancer to assign")

router = APIRouter(prefix="/quests", tags=["Quests"])


async def _quest_mutation_rate_limit(
    request: Request,
    current_user: UserProfile,
    *,
    action: str,
    limit: int,
    window_seconds: int,
) -> None:
    ip = get_client_ip(request)
    await check_rate_limit(ip, action=action, limit=limit, window_seconds=window_seconds)
    await check_user_rate_limit(
        current_user.id,
        action=action,
        limit=limit,
        window_seconds=window_seconds,
    )


async def _quest_read_rate_limit(request: Request) -> None:
    """P2-19: rate limit GET endpoints (60 req/min per IP)."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="quest_read", limit=60, window_seconds=60)


# ============================================
# Endpoints — thin controllers delegating to quest_service
# ============================================


@router.get("/", response_model=QuestListResponse)
async def get_all_quests(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    status_filter: Optional[QuestStatusEnum] = None,
    grade_filter: Optional[GradeEnum] = None,
    skill_filter: Optional[str] = None,
    min_budget: Optional[Decimal] = None,
    max_budget: Optional[Decimal] = None,
    user_id: Optional[str] = None,
    current_user: Optional[UserProfile] = Depends(get_optional_user),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Получить список всех квестов с фильтрацией"""
    await _quest_read_rate_limit(request)
    if user_id and not current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication is required to filter quests by user_id",
        )

    if (
        user_id
        and current_user
        and current_user.role != "admin"
        and current_user.id != user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only filter quests for your own user_id",
        )

    return await quest_service.list_quests(
        conn,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        grade_filter=grade_filter,
        skill_filter=skill_filter,
        min_budget=min_budget,
        max_budget=max_budget,
        user_id=user_id,
        current_user=current_user,
    )


@router.get("/{quest_id}", response_model=Quest)
async def get_quest(
    quest_id: str,
    request: Request,
    current_user: Optional[UserProfile] = Depends(get_optional_user),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Получить детали квеста по ID"""
    await _quest_read_rate_limit(request)
    quest = await quest_service.get_quest_by_id(conn, quest_id, current_user)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )
    return quest


@router.get("/{quest_id}/recommended-freelancers", response_model=FreelancerRecommendationListResponse)
async def get_recommended_freelancers(
    quest_id: str,
    request: Request,
    limit: int = Query(default=10, ge=1, le=20),
    current_user: Optional[UserProfile] = Depends(get_optional_user),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await _quest_read_rate_limit(request)
    quest = await quest_service.get_quest_by_id(conn, quest_id, current_user)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quest not found",
        )
    payload = await matching_service.match_freelancers_for_quest(conn, quest_id, limit=limit)
    return FreelancerRecommendationListResponse(**payload)


@router.post("/", response_model=Quest, status_code=status.HTTP_201_CREATED)
async def create_quest(
    request: Request,
    quest_data: QuestCreate,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Создать новый квест. Клиенты и администраторы могут создавать квесты."""
    await _quest_mutation_rate_limit(
        request,
        current_user,
        action="create_quest",
        limit=10,
        window_seconds=60,
    )
    if current_user.role not in {"client", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients and admins can create quests",
        )
    return await quest_service.create_quest(conn, quest_data, current_user)


@router.patch("/{quest_id}", response_model=Quest)
async def update_quest(
    quest_id: str,
    request: Request,
    quest_data: QuestUpdate,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Обновить черновик или неназначенный контракт."""
    await _quest_mutation_rate_limit(
        request,
        current_user,
        action="update_quest",
        limit=20,
        window_seconds=60,
    )
    try:
        return await quest_service.update_quest(conn, quest_id, quest_data, current_user)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{quest_id}/publish")
async def publish_quest(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Опубликовать черновик на биржу."""
    await _quest_mutation_rate_limit(
        request,
        current_user,
        action="publish_quest",
        limit=20,
        window_seconds=60,
    )
    try:
        quest = await quest_service.publish_quest(conn, quest_id, current_user)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return {"message": "Quest published successfully", "quest": quest}


@router.get("/{quest_id}/history")
async def get_quest_history(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Получить историю смен статусов по контракту."""
    await _quest_read_rate_limit(request)
    try:
        history = await quest_service.get_quest_status_history(conn, quest_id, current_user)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return {"history": history}


@router.post("/{quest_id}/apply")
async def apply_to_quest(
    quest_id: str,
    application_data: QuestApplicationCreate,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Откликнуться на квест"""
    await _quest_mutation_rate_limit(
        request,
        current_user,
        action="apply_quest",
        limit=20,
        window_seconds=60,
    )
    try:
        application = await quest_service.apply_to_quest(
            conn, quest_id, application_data, current_user
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return {"message": "Application submitted successfully", "application": application}


@router.post("/{quest_id}/invite", response_model=QuestInviteResponse)
async def invite_freelancer(
    quest_id: str,
    invite_data: QuestInviteCreate,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Пригласить фрилансера откликнуться на открытый квест."""
    await _quest_mutation_rate_limit(
        request,
        current_user,
        action="invite_freelancer",
        limit=20,
        window_seconds=60,
    )
    try:
        return await quest_service.invite_freelancer_to_quest(
            conn,
            quest_id,
            invite_data.freelancer_id,
            current_user,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{quest_id}/assign")
async def assign_quest(
    quest_id: str,
    request: Request,
    freelancer_id: Optional[str] = Query(default=None, min_length=1),
    body: Optional[AssignQuestRequest] = None,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Назначить исполнителя на квест"""
    await _quest_mutation_rate_limit(
        request,
        current_user,
        action="assign_quest",
        limit=20,
        window_seconds=60,
    )
    selected_freelancer_id = body.freelancer_id if body else freelancer_id
    if not selected_freelancer_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="freelancer_id is required in request body or query string",
        )
    try:
        quest = await quest_service.assign_freelancer(
            conn, quest_id, selected_freelancer_id, current_user
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InsufficientFundsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Freelancer assigned successfully. Awaiting start.", "quest": quest}


@router.post("/{quest_id}/start")
async def start_quest(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Начать квест (назначенный исполнитель)"""
    await _quest_mutation_rate_limit(
        request,
        current_user,
        action="start_quest",
        limit=20,
        window_seconds=60,
    )
    try:
        quest = await quest_service.start_quest(conn, quest_id, current_user)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return {"message": "Quest started successfully", "quest": quest}


@router.post("/{quest_id}/complete")
async def complete_quest(
    quest_id: str,
    request: Request,
    completion_data: Optional[QuestCompletionCreate] = None,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Завершить квест (исполнитель)"""
    await _quest_mutation_rate_limit(
        request,
        current_user,
        action="complete_quest",
        limit=20,
        window_seconds=60,
    )
    try:
        quest, xp_reward = await quest_service.mark_quest_complete(
            conn, quest_id, completion_data, current_user
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return {
        "message": "Quest marked as completed. Awaiting client confirmation.",
        "quest": quest,
        "xp_earned": xp_reward,
    }


@router.post("/{quest_id}/confirm")
async def confirm_quest_completion(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """
    Подтвердить завершение квеста (клиент).

    Atomically: XP update + transaction log + wallet credit inside DB transaction.
    """
    await _quest_mutation_rate_limit(
        request,
        current_user,
        action="confirm_quest",
        limit=20,
        window_seconds=60,
    )
    try:
        result = await quest_service.confirm_quest_completion(
            conn, quest_id, current_user
        )
    except EscrowMismatchError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ESCROW_CONFLICT_DETAIL)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InsufficientFundsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result


@router.post("/{quest_id}/request-revision")
async def request_quest_revision(
    quest_id: str,
    revision_data: QuestRevisionRequest,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Запросить доработки по завершённому квесту (клиент)."""
    await _quest_mutation_rate_limit(
        request,
        current_user,
        action="request_quest_revision",
        limit=20,
        window_seconds=60,
    )
    try:
        quest = await quest_service.request_quest_revision(
            conn, quest_id, revision_data, current_user
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return {
        "message": "Revision requested successfully. Awaiting freelancer updates.",
        "quest": quest,
    }


@router.post("/{quest_id}/cancel")
async def cancel_quest(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Отменить квест"""
    await _quest_mutation_rate_limit(
        request,
        current_user,
        action="cancel_quest",
        limit=20,
        window_seconds=60,
    )
    try:
        result = await quest_service.cancel_quest(conn, quest_id, current_user)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return result


@router.get("/{quest_id}/applications")
async def get_quest_applications(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Получить список откликов на квест"""
    await _quest_read_rate_limit(request)
    try:
        result = await quest_service.get_quest_applications(
            conn, quest_id, current_user
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return result


# ============================================
# PvE Training Quest Endpoints
# ============================================


@router.get("/training/list", response_model=QuestListResponse)
async def list_training_quests(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    grade: Optional[GradeEnum] = None,
    skill: Optional[str] = None,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """List available PvE training quests."""
    await _quest_read_rate_limit(request)
    return await quest_service.list_training_quests(
        conn,
        page=page,
        page_size=page_size,
        grade_filter=grade,
        skill_filter=skill,
    )


@router.post("/training/create", response_model=Quest, status_code=status.HTTP_201_CREATED)
async def create_training_quest(
    request: Request,
    data: TrainingQuestCreate,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Create a new PvE training quest (admin only)."""
    await _quest_mutation_rate_limit(
        request, current_user,
        action="create_training_quest", limit=20, window_seconds=60,
    )
    try:
        return await quest_service.create_training_quest(conn, data, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/training/{quest_id}/accept", response_model=Quest)
async def accept_training_quest(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Freelancer accepts and starts a training quest (auto-assign, no application)."""
    await _quest_mutation_rate_limit(
        request, current_user,
        action="accept_training_quest", limit=10, window_seconds=60,
    )
    try:
        return await quest_service.accept_training_quest(conn, quest_id, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.post("/training/{quest_id}/complete")
async def complete_training_quest(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Freelancer completes a training quest — auto-confirm, grant capped XP."""
    await _quest_mutation_rate_limit(
        request, current_user,
        action="complete_training_quest", limit=10, window_seconds=60,
    )
    try:
        return await quest_service.complete_training_quest(conn, quest_id, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


# ============================================
# Co-op Raid Quest Endpoints
# ============================================


@router.get("/raid/list", response_model=QuestListResponse)
async def list_raid_quests(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    grade: Optional[GradeEnum] = None,
    skill: Optional[str] = None,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """List available co-op raid quests."""
    await _quest_read_rate_limit(request)
    return await quest_service.list_raid_quests(
        conn, page=page, page_size=page_size,
        grade_filter=grade, skill_filter=skill,
    )


@router.post("/raid/create", response_model=Quest, status_code=201)
async def create_raid_quest(
    request: Request,
    data: RaidQuestCreate,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Create a new co-op raid quest (client or admin)."""
    await _quest_mutation_rate_limit(
        request, current_user,
        action="create_raid_quest", limit=5, window_seconds=60,
    )
    try:
        return await quest_service.create_raid_quest(conn, data, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/raid/{quest_id}/join", response_model=RaidPartyResponse)
async def join_raid_quest(
    quest_id: str,
    body: RaidJoinRequest,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Freelancer joins a raid quest in a specific role slot."""
    await _quest_mutation_rate_limit(
        request, current_user,
        action="join_raid_quest", limit=10, window_seconds=60,
    )
    try:
        return await quest_service.join_raid_quest(conn, quest_id, body.role_slot, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.post("/raid/{quest_id}/leave", response_model=RaidPartyResponse)
async def leave_raid_quest(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Freelancer leaves a raid quest before it starts."""
    await _quest_mutation_rate_limit(
        request, current_user,
        action="leave_raid_quest", limit=10, window_seconds=60,
    )
    try:
        return await quest_service.leave_raid_quest(conn, quest_id, current_user)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.get("/raid/{quest_id}/party", response_model=RaidPartyResponse)
async def get_raid_party(
    quest_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get current raid party state."""
    await _quest_read_rate_limit(request)
    try:
        return await quest_service.get_raid_party(conn, quest_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.post("/raid/{quest_id}/start", response_model=Quest)
async def start_raid_quest(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Client or admin starts the raid (moves to in_progress)."""
    await _quest_mutation_rate_limit(
        request, current_user,
        action="start_raid_quest", limit=5, window_seconds=60,
    )
    try:
        return await quest_service.start_raid_quest(conn, quest_id, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.post("/raid/{quest_id}/complete")
async def complete_raid_quest(
    quest_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Raid member marks the raid quest as completed."""
    await _quest_mutation_rate_limit(
        request, current_user,
        action="complete_raid_quest", limit=5, window_seconds=60,
    )
    try:
        return await quest_service.complete_raid_quest(conn, quest_id, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


# ────────────────────────────────────────────
# Legendary Quest Chains
# ────────────────────────────────────────────

@router.get("/chains/list", response_model=ChainListResponse)
async def list_quest_chains(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """List all legendary quest chains."""
    await _quest_read_rate_limit(request)
    return await quest_service.list_quest_chains(conn, page=page, page_size=page_size)


@router.get("/chains/{chain_id}", response_model=ChainDetailResponse)
async def get_chain_detail(
    chain_id: str,
    request: Request,
    current_user: UserProfile | None = Depends(get_optional_user),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get full chain detail with steps, quests, and optional user progress."""
    await _quest_read_rate_limit(request)
    user_id = current_user.id if current_user else None
    try:
        return await quest_service.get_chain_detail(conn, chain_id, user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/chains/create", response_model=ChainDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_quest_chain(
    body: QuestChainCreate,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Create a new legendary quest chain (admin only)."""
    await _quest_mutation_rate_limit(
        request, current_user,
        action="create_quest_chain", limit=5, window_seconds=60,
    )
    try:
        return await quest_service.create_quest_chain(conn, body, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/chains/my-progress")
async def get_my_chain_progress(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get current user's progress across all chains."""
    await _quest_read_rate_limit(request)
    progress = await quest_service.get_user_chain_progress_list(conn, current_user.id)
    return {"progress": [p.model_dump() for p in progress]}
