"""
Endpoints для работы с пользователями
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.db.session import get_db_connection
from app.models.user import GradeEnum, UserBadge, UserProfile, UserRoleEnum, UserStats, row_to_user_profile
from app.core.otel_utils import db_span

router = APIRouter(prefix="/users", tags=["Пользователи"])


def _require_user_auth(authorization: Optional[str] = None) -> None:
    """Standalone helper — validates that a Bearer token header was supplied.
    Actual token verification happens in get_current_user inside quests.py;
    here we just guard unauthenticated callers.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(
    user_id: str, conn: asyncpg.Connection = Depends(get_db_connection)
):
    with db_span("db.fetchrow", query="SELECT * FROM users WHERE id = $1", params=[user_id]):
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден",
        )
    return row_to_user_profile(row)


@router.get("/", response_model=List[UserProfile])
async def get_all_users(
    skip: int = 0,
    limit: int = Query(default=20, le=100),
    grade: Optional[str] = None,
    role: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    _require_user_auth(authorization)
    query = "SELECT * FROM users WHERE 1=1"
    args = []
    arg_idx = 1

    if grade:
        query += f" AND grade = ${arg_idx}"
        args.append(grade)
        arg_idx += 1
    if role:
        query += f" AND role = ${arg_idx}"
        args.append(role)
        arg_idx += 1

    query += f" ORDER BY created_at DESC LIMIT ${arg_idx} OFFSET ${arg_idx + 1}"
    args.extend([limit, skip])

    with db_span("db.fetch", query=query, params=args):
        rows = await conn.fetch(query, *args)
    return [row_to_user_profile(row) for row in rows]


@router.get("/{user_id}/stats", response_model=UserStats)
async def get_user_stats(
    user_id: str, conn: asyncpg.Connection = Depends(get_db_connection)
):
    with db_span("db.fetchrow", query="SELECT stats_int, stats_dex, stats_cha FROM users WHERE id = $1", params=[user_id]):
        row = await conn.fetchrow(
            "SELECT stats_int, stats_dex, stats_cha FROM users WHERE id = $1", user_id
        )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден",
        )
    return UserStats(
        int=row["stats_int"],
        dex=row["stats_dex"],
        cha=row["stats_cha"],
    )
