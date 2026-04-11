"""
Endpoints для системы классов — выбор, подтверждение, информация.

Только для фрилансеров. Разблокируется на уровне 5.
"""

import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.character_class import (
    ClassListResponse,
    ClassSelectRequest,
    ClassSelectResponse,
    UserClassInfo,
    PerkTreeResponse,
    PerkUnlockRequest,
    PerkUnlockResponse,
    AbilityInfo,
    AbilityActivateRequest,
    AbilityActivateResponse,
)
from app.models.user import UserProfile
from app.services import class_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/classes", tags=["Classes"])


@router.get("/", response_model=ClassListResponse)
async def list_classes(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
):
    """List all available character classes."""
    await check_rate_limit(get_client_ip(request), action="class_read", limit=60, window_seconds=60)
    return class_service.list_classes(
        user_level=current_user.level,
        current_class=current_user.character_class,
    )


@router.get("/me", response_model=UserClassInfo)
async def get_my_class(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get current user's class info and progression."""
    await check_rate_limit(get_client_ip(request), action="class_read", limit=60, window_seconds=60)
    info = await class_service.get_user_class_info(conn, current_user.id)
    if info is None:
        return class_service.build_empty_user_class_info()
    return info


@router.post("/select", response_model=ClassSelectResponse)
async def select_class(
    request: Request,
    body: ClassSelectRequest,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Select a character class. Starts a 24h trial period."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="class_select", limit=10, window_seconds=60)
    try:
        async with conn.transaction():
            result = await class_service.select_class(
                conn, current_user, body.class_id, trial=True
            )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/confirm", response_model=ClassSelectResponse)
async def confirm_class(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Confirm the current trial class as permanent."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="class_confirm", limit=10, window_seconds=60)
    try:
        async with conn.transaction():
            result = await class_service.confirm_class(conn, current_user)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/reset")
async def reset_class(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Reset the current class. 30-day cooldown before new selection."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="class_reset", limit=5, window_seconds=60)
    try:
        async with conn.transaction():
            result = await class_service.reset_class(conn, current_user)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ────────────────────────────────────────────
# Phase 2: Perk tree
# ────────────────────────────────────────────

@router.get("/perks", response_model=PerkTreeResponse)
async def get_perk_tree(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get user's perk tree for their current class."""
    await check_rate_limit(get_client_ip(request), action="class_read", limit=60, window_seconds=60)
    try:
        return await class_service.get_user_perk_tree(conn, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/perks/unlock", response_model=PerkUnlockResponse)
async def unlock_perk(
    request: Request,
    body: PerkUnlockRequest,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Unlock a perk from the class perk tree."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="perk_unlock", limit=20, window_seconds=60)
    try:
        async with conn.transaction():
            return await class_service.unlock_perk(conn, current_user.id, body.perk_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ────────────────────────────────────────────
# Phase 2: Active abilities
# ────────────────────────────────────────────

@router.get("/abilities", response_model=list[AbilityInfo])
async def get_abilities(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get all abilities for user's current class with status."""
    await check_rate_limit(get_client_ip(request), action="class_read", limit=60, window_seconds=60)
    return await class_service.get_user_abilities(conn, current_user.id)


@router.post("/abilities/activate", response_model=AbilityActivateResponse)
async def activate_ability(
    request: Request,
    body: AbilityActivateRequest,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Activate an ability (e.g. Rage Mode)."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="ability_activate", limit=30, window_seconds=60)
    try:
        async with conn.transaction():
            return await class_service.activate_ability(conn, current_user.id, body.ability_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/abilities/{ability_id}/activate", response_model=AbilityActivateResponse)
async def activate_ability_by_path(
    ability_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Activate an ability using the path-param contract from the idea doc."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="ability_activate", limit=30, window_seconds=60)
    try:
        async with conn.transaction():
            return await class_service.activate_ability(conn, current_user.id, ability_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))