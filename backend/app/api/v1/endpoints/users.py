"""Endpoints для работы с пользователями."""

import logging
from decimal import Decimal
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import require_auth, _USER_SAFE_COLUMNS
from app.db.session import get_db_connection
from app.models.marketplace import ArtifactCabinet, ArtifactEquipResponse, PlayerCardCollection, SoloCardDrop
from app.models.matching import QuestRecommendationListResponse
from app.models.user import PublicUserProfile, ReputationStats, FactionAlignment, TrustScoreResponse, UserProfile, UserStats, _safe_json_list, row_to_user_profile, to_public_user_profile
from app.core.otel_utils import db_span
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.core.rewards import compute_reputation_stats, compute_user_faction_alignment
from app.services import badge_service, guild_card_service, matching_service, trust_score_service


class ProfileUpdateRequest(BaseModel):
    bio: Optional[str] = Field(None, max_length=500)
    skills: Optional[List[str]] = Field(None, max_length=20)
    availability_status: Optional[str] = Field(None, max_length=32)
    portfolio_summary: Optional[str] = Field(None, max_length=500)
    portfolio_links: Optional[List[str]] = Field(None, max_length=8)

    @field_validator("skills")
    @classmethod
    def validate_skill_items(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            for s in v:
                if len(s) > 50:
                    raise ValueError("Each skill must be ≤ 50 characters")
        return v


class AvatarUploadResponse(BaseModel):
    avatar_url: str = Field(..., max_length=500)


AVATAR_UPLOAD_DIR = Path(__file__).resolve().parents[4] / "uploads" / "avatars"
ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_AVATAR_MIME_TO_EXTENSIONS = {
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/webp": {".webp"},
}
MAX_AVATAR_BYTES = 512 * 1024


router = APIRouter(prefix="/users", tags=["Пользователи"])
logger = logging.getLogger(__name__)


def _validate_avatar_upload(file: UploadFile, content: bytes) -> str:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported avatar file extension")

    allowed_extensions = ALLOWED_AVATAR_MIME_TO_EXTENSIONS.get(file.content_type or "")
    if not allowed_extensions or extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported avatar file type")

    if not content:
        raise HTTPException(status_code=400, detail="Avatar file is empty")

    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Avatar file exceeds size limit")

    return extension


async def _fetch_proof_fields(conn: asyncpg.Connection, user_id: str) -> dict:
    """Return proof metrics for a single user from cached cols + quest counts."""
    row = await conn.fetchrow(
        """
        SELECT
            u.avg_rating,
            u.review_count,
            u.trust_score,
            u.trust_score_updated_at,
            u.availability_status,
            u.portfolio_summary,
            COALESCE(u.portfolio_links, '[]'::jsonb) AS portfolio_links,
            COALESCE(q.confirmed, 0) AS confirmed_quest_count,
            COALESCE(q.active, 0) AS active_quest_count,
            q.avg_budget AS avg_budget,
            CASE WHEN COALESCE(q.total, 0) > 0
                 THEN ROUND(COALESCE(q.confirmed, 0)::numeric / q.total * 100, 1)
                 ELSE NULL
            END AS completion_rate
        FROM users u
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (WHERE status IN ('completed', 'confirmed')) AS confirmed,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status IN ('assigned', 'in_progress', 'revision_requested')) AS active,
                AVG(budget) FILTER (WHERE status IN ('completed', 'confirmed')) AS avg_budget
            FROM quests
            WHERE assigned_to = u.id
              AND status NOT IN ('draft', 'open')
        ) q ON TRUE
        WHERE u.id = $1
        """,
        user_id,
    )
    if not row:
        return {}
    try:
        return {
            "avg_rating": float(row["avg_rating"]) if row["avg_rating"] is not None else None,
            "review_count": int(row["review_count"] or 0),
            "trust_score": float(row["trust_score"]) if row["trust_score"] is not None else None,
            "trust_score_updated_at": row["trust_score_updated_at"],
            "confirmed_quest_count": int(row["confirmed_quest_count"]),
            "completion_rate": float(row["completion_rate"]) if row["completion_rate"] is not None else None,
            "availability_status": row["availability_status"],
            "portfolio_summary": row["portfolio_summary"],
            "portfolio_links": _safe_json_list(row["portfolio_links"]),
            "active_quest_count": int(row["active_quest_count"] or 0),
            "avg_budget": row["avg_budget"],
        }
    except (KeyError, TypeError):
        return {}


async def _fetch_proof_batch(conn: asyncpg.Connection, user_ids: list[str]) -> dict[str, dict]:
    """Batch-fetch proof metrics for multiple users."""
    if not user_ids:
        return {}
    rows = await conn.fetch(
        """
        SELECT
            u.id,
            u.avg_rating,
            u.review_count,
            u.trust_score,
            u.trust_score_updated_at,
            u.availability_status,
            u.portfolio_summary,
            COALESCE(u.portfolio_links, '[]'::jsonb) AS portfolio_links,
            COALESCE(q.confirmed, 0) AS confirmed_quest_count,
            COALESCE(q.active, 0) AS active_quest_count,
            q.avg_budget AS avg_budget,
            CASE WHEN COALESCE(q.total, 0) > 0
                 THEN ROUND(COALESCE(q.confirmed, 0)::numeric / q.total * 100, 1)
                 ELSE NULL
            END AS completion_rate
        FROM users u
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (WHERE status IN ('completed', 'confirmed')) AS confirmed,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status IN ('assigned', 'in_progress', 'revision_requested')) AS active,
                AVG(budget) FILTER (WHERE status IN ('completed', 'confirmed')) AS avg_budget
            FROM quests
            WHERE assigned_to = u.id
              AND status NOT IN ('draft', 'open')
        ) q ON TRUE
        WHERE u.id = ANY($1::text[])
        """,
        user_ids,
    )
    result: dict[str, dict] = {}
    for r in rows:
        try:
            result[r["id"]] = {
                "avg_rating": float(r["avg_rating"]) if r["avg_rating"] is not None else None,
                "review_count": int(r["review_count"] or 0),
                "trust_score": float(r["trust_score"]) if r["trust_score"] is not None else None,
                "trust_score_updated_at": r["trust_score_updated_at"],
                "confirmed_quest_count": int(r["confirmed_quest_count"]),
                "completion_rate": float(r["completion_rate"]) if r["completion_rate"] is not None else None,
                "availability_status": r["availability_status"],
                "portfolio_summary": r["portfolio_summary"],
                "portfolio_links": _safe_json_list(r["portfolio_links"]),
                "active_quest_count": int(r["active_quest_count"] or 0),
                "avg_budget": r["avg_budget"],
            }
        except (KeyError, TypeError):
            continue
    return result


def _to_budget_band(avg_budget: Decimal | float | int | None) -> Optional[str]:
    if avg_budget is None:
        return None
    value = Decimal(str(avg_budget))
    if value < Decimal("15000"):
        return "up_to_15k"
    if value < Decimal("50000"):
        return "15k_to_50k"
    if value < Decimal("150000"):
        return "50k_to_150k"
    return "150k_plus"


def _to_response_time_hint(active_quest_count: int, confirmed_quest_count: int, review_count: int) -> str:
    if active_quest_count >= 2:
        return "Сейчас сфокусирован на активных задачах"
    if active_quest_count == 1:
        return "Обычно отвечает выборочно из-за текущей загрузки"
    if confirmed_quest_count >= 6 or review_count >= 6:
        return "Обычно отвечает в течение рабочего дня"
    if confirmed_quest_count >= 2 or review_count >= 2:
        return "Недавно активен, ответ обычно не затягивается"
    return "Нужна первая подтверждённая история отклика"


def _build_public_profile_payload(profile: UserProfile, proof: dict) -> dict:
    completed_items = [
        bool((profile.bio or "").strip()),
        len([skill for skill in profile.skills if str(skill).strip()]) >= 2,
        bool(proof.get("availability_status")),
        bool(proof.get("portfolio_links") or proof.get("portfolio_summary")),
        bool((proof.get("review_count") or 0) > 0 or (proof.get("confirmed_quest_count") or 0) > 0),
    ]
    completed_count = sum(1 for item in completed_items if item)
    completeness = int(round((completed_count / len(completed_items)) * 100)) if completed_items else 0
    onboarding_completed = completed_count == len(completed_items)
    profile_completeness = max(completeness, int(profile.profile_completeness_percent or 0))

    rep_stats = compute_reputation_stats(
        avg_rating=proof.get("avg_rating"),
        completion_rate=proof.get("completion_rate"),
        trust_score=proof.get("trust_score"),
        confirmed_quest_count=int(proof.get("confirmed_quest_count") or 0),
        review_count=int(proof.get("review_count") or 0),
        level=profile.level,
        grade=profile.grade,
        profile_completeness_percent=profile_completeness,
    )

    faction_alignment = compute_user_faction_alignment(
        confirmed_quest_count=int(proof.get("confirmed_quest_count") or 0),
        active_quest_count=int(proof.get("active_quest_count") or 0),
        review_count=int(proof.get("review_count") or 0),
        avg_rating=proof.get("avg_rating"),
        completion_rate=proof.get("completion_rate"),
        trust_score=proof.get("trust_score"),
    )

    return {
        "avg_rating": proof.get("avg_rating"),
        "review_count": int(proof.get("review_count") or 0),
        "trust_score": proof.get("trust_score"),
        "trust_score_updated_at": proof.get("trust_score_updated_at"),
        "confirmed_quest_count": int(proof.get("confirmed_quest_count") or 0),
        "completion_rate": proof.get("completion_rate"),
        "typical_budget_band": _to_budget_band(proof.get("avg_budget")),
        "availability_status": proof.get("availability_status") or profile.availability_status,
        "response_time_hint": _to_response_time_hint(
            int(proof.get("active_quest_count") or 0),
            int(proof.get("confirmed_quest_count") or 0),
            int(proof.get("review_count") or 0),
        ),
        "portfolio_links": proof.get("portfolio_links") or profile.portfolio_links,
        "portfolio_summary": proof.get("portfolio_summary") or profile.portfolio_summary,
        "onboarding_completed": onboarding_completed,
        "onboarding_completed_at": profile.onboarding_completed_at,
        "profile_completeness_percent": profile_completeness,
        "reputation_stats": rep_stats,
        "faction_alignment": faction_alignment,
    }


@router.get("/me", response_model=UserProfile)
async def get_my_profile(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return the authenticated user's full profile including is_banned and email.

    P1-14 FIX: refreshUser must fetch from this endpoint (not the public /users/{id})
    to keep is_banned, email, and other private fields up-to-date on the client.
    """
    await check_rate_limit(get_client_ip(request), action="user_read", limit=60, window_seconds=60)
    row = await conn.fetchrow(
        f"SELECT {_USER_SAFE_COLUMNS} FROM users WHERE id = $1",
        current_user.id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return row_to_user_profile(row)


@router.patch("/me")
async def update_my_profile(
    request: Request,
    body: ProfileUpdateRequest,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Allow authenticated user to update their own bio and skills."""
    await check_rate_limit(get_client_ip(request), action="update_profile", limit=10, window_seconds=60)

    sets: list[str] = []
    args: list = []
    idx = 1

    if body.bio is not None:
        sets.append(f"bio = ${idx}")
        args.append(body.bio.strip())
        idx += 1

    if body.skills is not None:
        cleaned = [s.strip() for s in body.skills if s.strip()][:20]
        sets.append(f"skills = to_jsonb(${idx}::text[])")
        args.append(cleaned)
        idx += 1

    if body.availability_status is not None:
        sets.append(f"availability_status = ${idx}")
        args.append(body.availability_status.strip() or None)
        idx += 1

    if body.portfolio_summary is not None:
        sets.append(f"portfolio_summary = ${idx}")
        args.append(body.portfolio_summary.strip() or None)
        idx += 1

    if body.portfolio_links is not None:
        cleaned_links = [link.strip() for link in body.portfolio_links if link.strip()][:8]
        sets.append(f"portfolio_links = to_jsonb(${idx}::text[])")
        args.append(cleaned_links)
        idx += 1

    if not sets:
        raise HTTPException(status_code=400, detail="Нечего обновлять")

    proof = await _fetch_proof_fields(conn, current_user.id)
    merged_bio = body.bio.strip() if body.bio is not None else (current_user.bio or "")
    merged_skills = [s.strip() for s in body.skills if s.strip()][:20] if body.skills is not None else current_user.skills
    merged_availability = body.availability_status.strip() if body.availability_status is not None and body.availability_status.strip() else current_user.availability_status
    merged_portfolio_summary = body.portfolio_summary.strip() if body.portfolio_summary is not None and body.portfolio_summary.strip() else current_user.portfolio_summary
    merged_portfolio_links = [link.strip() for link in body.portfolio_links if link.strip()][:8] if body.portfolio_links is not None else current_user.portfolio_links
    merged_profile = current_user.model_copy(
        update={
            "bio": merged_bio or None,
            "skills": merged_skills,
            "availability_status": merged_availability,
            "portfolio_summary": merged_portfolio_summary,
            "portfolio_links": merged_portfolio_links,
        }
    )
    public_payload = _build_public_profile_payload(merged_profile, proof)

    sets.append(f"onboarding_completed = ${idx}")
    args.append(public_payload["onboarding_completed"])
    idx += 1

    sets.append(
        f"onboarding_completed_at = CASE WHEN ${idx}::boolean THEN COALESCE(onboarding_completed_at, NOW()) ELSE NULL END"
    )
    args.append(public_payload["onboarding_completed"])
    idx += 1

    sets.append(f"profile_completeness_percent = ${idx}")
    args.append(public_payload["profile_completeness_percent"])
    idx += 1

    sets.append(f"updated_at = NOW()")
    args.append(current_user.id)

    sql = f"UPDATE users SET {', '.join(sets)} WHERE id = ${idx} RETURNING {_USER_SAFE_COLUMNS}"
    async with conn.transaction():
        row = await conn.fetchrow(sql, *args)

    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    profile = row_to_user_profile(row)
    refreshed_proof = await _fetch_proof_fields(conn, current_user.id)
    return to_public_user_profile(profile, **_build_public_profile_payload(profile, refreshed_proof))


@router.post("/me/avatar", response_model=AvatarUploadResponse)
async def upload_my_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="avatar_upload", limit=2, window_seconds=3600)

    content = await file.read()
    extension = _validate_avatar_upload(file, content)

    AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{current_user.id}-{uuid4().hex}{extension}"
    destination = AVATAR_UPLOAD_DIR / filename
    public_path = f"/uploads/avatars/{filename}"
    destination.write_bytes(content)

    try:
        async with conn.transaction():
            row = await conn.fetchrow(
                f"UPDATE users SET avatar_url = $1, updated_at = NOW() WHERE id = $2 RETURNING {_USER_SAFE_COLUMNS}",
                public_path,
                current_user.id,
            )
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    if not row:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return AvatarUploadResponse(avatar_url=public_path)


@router.post("/onboarding/complete", status_code=200)
async def complete_onboarding(
    request: Request,
    current_user=Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Mark onboarding as completed and award the Recruit badge."""
    await check_rate_limit(get_client_ip(request), action="onboarding_complete", limit=5, window_seconds=60)
    user_id = current_user.id
    async with conn.transaction():
        await conn.execute(
            """
            UPDATE users
            SET onboarding_completed = TRUE,
                onboarding_completed_at = COALESCE(onboarding_completed_at, NOW())
            WHERE id = $1
            """,
            user_id,
        )
        result = await badge_service.check_and_award(conn, user_id, "registration", {})
    return {"ok": True, "badges_earned": [b.dict() for b in result.newly_earned]}


@router.get("/me/artifacts", response_model=ArtifactCabinet)
async def get_my_artifacts(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="get_user", limit=60, window_seconds=60)
    cabinet = await guild_card_service.list_user_artifacts(conn, user_id=current_user.id)
    return ArtifactCabinet(**cabinet)


@router.post("/me/artifacts/{artifact_id}/equip", response_model=ArtifactEquipResponse)
async def equip_my_artifact(
    artifact_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="equip_artifact", limit=20, window_seconds=60)
    try:
        artifact = await guild_card_service.equip_user_artifact(
            conn,
            user_id=current_user.id,
            artifact_id=artifact_id,
        )
        cabinet = await guild_card_service.list_user_artifacts(conn, user_id=current_user.id)
        return ArtifactEquipResponse(
            artifact=artifact,
            cabinet=ArtifactCabinet(**cabinet),
            message="Artifact equipped.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/me/artifacts/{artifact_id}/unequip", response_model=ArtifactEquipResponse)
async def unequip_my_artifact(
    artifact_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="unequip_artifact", limit=20, window_seconds=60)
    try:
        artifact = await guild_card_service.unequip_user_artifact(
            conn,
            user_id=current_user.id,
            artifact_id=artifact_id,
        )
        cabinet = await guild_card_service.list_user_artifacts(conn, user_id=current_user.id)
        return ArtifactEquipResponse(
            artifact=artifact,
            cabinet=ArtifactCabinet(**cabinet),
            message="Artifact unequipped.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/me/player-cards", response_model=PlayerCardCollection)
async def get_my_player_cards(
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Return the authenticated freelancer's solo card drops from player_card_drops."""
    await check_rate_limit(get_client_ip(request), action="get_user", limit=60, window_seconds=60)
    if current_user.role != "freelancer":
        return PlayerCardCollection(drops=[], total=0)

    try:
        rows = await conn.fetch(
            """
            SELECT id, card_code, name, rarity, family, description, accent,
                   item_category, quest_id, dropped_at
            FROM player_card_drops
            WHERE freelancer_id = $1
            ORDER BY dropped_at DESC
            """,
            current_user.id,
        )
    except asyncpg.UndefinedTableError:
        logger.warning(
            "player_card_drops table is missing; returning empty player cards for user %s",
            current_user.id,
        )
        return PlayerCardCollection(drops=[], total=0)

    drops = [
        SoloCardDrop(
            id=str(row["id"]),
            card_code=str(row["card_code"]),
            name=str(row["name"]),
            rarity=row["rarity"],
            family=str(row["family"]),
            description=str(row["description"]),
            accent=str(row["accent"]),
            item_category=row["item_category"],
            quest_id=str(row["quest_id"]),
            dropped_at=row["dropped_at"],
        )
        for row in rows
    ]
    return PlayerCardCollection(drops=drops, total=len(drops))


@router.get("/me/recommended-quests", response_model=QuestRecommendationListResponse)
async def get_my_recommended_quests(
    request: Request,
    limit: int = Query(default=10, ge=1, le=20),
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="get_user", limit=60, window_seconds=60)
    if current_user.role != "freelancer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only freelancers can access recommended quests")
    payload = await matching_service.recommend_quests_for_user(conn, current_user.id, limit=limit)
    return QuestRecommendationListResponse(**payload)


@router.get("/{user_id}", response_model=PublicUserProfile)
async def get_user_profile(
    user_id: str, request: Request, conn: asyncpg.Connection = Depends(get_db_connection)
):
    await check_rate_limit(get_client_ip(request), action="get_user", limit=60, window_seconds=60)
    _q = f"SELECT {_USER_SAFE_COLUMNS} FROM users WHERE id = $1"
    with db_span("db.fetchrow", query=_q, params=[user_id]):
        row = await conn.fetchrow(_q, user_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )
    proof = await _fetch_proof_fields(conn, user_id)
    profile = row_to_user_profile(row)
    return to_public_user_profile(profile, **_build_public_profile_payload(profile, proof))


@router.get("/{user_id}/trust-score", response_model=TrustScoreResponse)
async def get_user_trust_score(
    user_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="get_user", limit=60, window_seconds=60)
    payload = await trust_score_service.get_cached_trust_score(conn, user_id)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден",
        )
    return TrustScoreResponse(**payload)


@router.get("/")
async def get_all_users(
    request: Request,
    skip: int = 0,
    limit: int = Query(default=20, le=100),
    grade: Optional[str] = None,
    role: Optional[str] = None,
    sort_by: str = Query(default="created_at", pattern="^(created_at|xp|level|username)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="list_users", limit=30, window_seconds=60)
    base = "FROM users WHERE 1=1"
    args = []
    arg_idx = 1

    if grade:
        base += f" AND grade = ${arg_idx}"
        args.append(grade)
        arg_idx += 1
    if role:
        base += f" AND role = ${arg_idx}"
        args.append(role)
        arg_idx += 1

    total = await conn.fetchval(f"SELECT COUNT(*) {base}", *args)

    # SAFETY: f-string interpolation below is safe ONLY because:
    # 1. order_column comes from a whitelist map (see order_column_map) — never raw user input
    # 2. order_direction is validated to be exactly "ASC" or "DESC" — no injection vector
    # Do NOT copy this pattern without preserving both guards.
    order_column_map = {
        "created_at": "created_at",
        "xp": "xp",
        "level": "level",
        "username": "username",
    }
    order_column = order_column_map.get(sort_by, "created_at")
    order_direction = "ASC" if sort_order.lower() == "asc" else "DESC"

    query = (
        f'SELECT {_USER_SAFE_COLUMNS} {base} ORDER BY "{order_column}" {order_direction}, created_at DESC'
        f" LIMIT ${arg_idx} OFFSET ${arg_idx + 1}"
    )
    args.extend([limit, skip])

    with db_span("db.fetch", query=query, params=args):
        rows = await conn.fetch(query, *args)
    profiles = [row_to_user_profile(row) for row in rows]
    proof_map = await _fetch_proof_batch(conn, [p.id for p in profiles])
    return {
        "users": [
            to_public_user_profile(p, **_build_public_profile_payload(p, proof_map.get(p.id, {})))
            for p in profiles
        ],
        "total": int(total or 0),
        "limit": limit,
        "offset": skip,
        "has_more": (skip + limit) < (total or 0),
    }


@router.get("/{user_id}/stats", response_model=UserStats)
async def get_user_stats(
    user_id: str,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    await check_rate_limit(get_client_ip(request), action="get_user_stats", limit=60, window_seconds=60)
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
