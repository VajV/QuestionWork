"""
Endpoints для работы с квестами — thin controller layer.

Business logic delegated to app.services.quest_service.
Auth dependencies imported from app.api.deps.
"""

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_auth
from app.db.session import get_db_connection
from app.models.quest import (
    Quest,
    QuestApplicationCreate,
    QuestCreate,
    QuestListResponse,
    QuestStatusEnum,
)
from app.models.user import GradeEnum, UserProfile
from app.services import quest_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quests", tags=["Quests"])


# ============================================
# Endpoints — thin controllers delegating to quest_service
# ============================================


@router.get("/", response_model=QuestListResponse)
async def get_all_quests(
    page: int = 1,
    page_size: int = 10,
    status_filter: Optional[QuestStatusEnum] = None,
    grade_filter: Optional[GradeEnum] = None,
    skill_filter: Optional[str] = None,
    min_budget: Optional[float] = None,
    max_budget: Optional[float] = None,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Получить список всех квестов с фильтрацией"""
    return await quest_service.list_quests(
        conn,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        grade_filter=grade_filter,
        skill_filter=skill_filter,
        min_budget=min_budget,
        max_budget=max_budget,
    )


@router.get("/{quest_id}", response_model=Quest)
async def get_quest(
    quest_id: str, conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Получить детали квеста по ID"""
    quest = await quest_service.get_quest_by_id(conn, quest_id)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )
    return quest


@router.post("/", response_model=Quest, status_code=status.HTTP_201_CREATED)
async def create_quest(
    quest_data: QuestCreate,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Создать новый квест. Только клиенты могут создавать квесты."""
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can create quests",
        )
    return await quest_service.create_quest(conn, quest_data, current_user)


@router.post("/{quest_id}/apply")
async def apply_to_quest(
    quest_id: str,
    application_data: QuestApplicationCreate,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Откликнуться на квест"""
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


@router.post("/{quest_id}/assign")
async def assign_quest(
    quest_id: str,
    freelancer_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Назначить исполнителя на квест"""
    try:
        quest = await quest_service.assign_freelancer(
            conn, quest_id, freelancer_id, current_user
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return {"message": "Freelancer assigned successfully", "quest": quest}


@router.post("/{quest_id}/complete")
async def complete_quest(
    quest_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Завершить квест (исполнитель)"""
    try:
        quest, xp_reward = await quest_service.mark_quest_complete(
            conn, quest_id, current_user
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
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """
    Подтвердить завершение квеста (клиент).

    Atomically: XP update + transaction log + wallet credit inside DB transaction.
    """
    try:
        result = await quest_service.confirm_quest_completion(
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


@router.post("/{quest_id}/cancel")
async def cancel_quest(
    quest_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Отменить квест"""
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
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Получить список откликов на квест"""
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
