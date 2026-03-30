"""
Endpoints для шаблонов квестов (quest templates).

POST   /templates/               — создать шаблон (auth, client/admin)
GET    /templates/                — список шаблонов текущего пользователя (auth)
GET    /templates/{template_id}  — получить шаблон (auth, owner only)
PUT    /templates/{template_id}  — обновить шаблон (auth, owner only)
DELETE /templates/{template_id}  — удалить шаблон (auth, owner only)
POST   /templates/{template_id}/create-quest — создать квест из шаблона (auth)
"""

import logging
from decimal import Decimal
from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.deps import require_auth
from app.core.ratelimit import check_rate_limit, get_client_ip
from app.db.session import get_db_connection
from app.models.user import UserProfile
from app.models.quest import QuestCreate, Quest, GradeEnum, CurrencyEnum
from app.services import template_service, quest_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["Шаблоны квестов"])


# ── Schemas ────────────────────────────────────────────────────────────────

class CreateTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Название шаблона")
    title: str = Field(..., min_length=5, max_length=200, description="Заголовок квеста")
    description: str = Field("", max_length=5000, description="Описание")
    required_grade: str = Field("novice", description="Мин. грейд")
    skills: List[str] = Field(default_factory=list, max_length=20)
    budget: Decimal = Field(Decimal("0"), ge=0, le=1_000_000)
    currency: CurrencyEnum = CurrencyEnum.RUB
    is_urgent: bool = False
    required_portfolio: bool = False


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    required_grade: Optional[str] = None
    skills: Optional[List[str]] = None
    budget: Optional[Decimal] = Field(None, ge=0, le=1_000_000)
    currency: Optional[CurrencyEnum] = None
    is_urgent: Optional[bool] = None
    required_portfolio: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    title: str
    description: str
    required_grade: str
    skills: List[str]
    budget: Decimal
    currency: str
    is_urgent: bool
    required_portfolio: bool
    created_at: str
    updated_at: str


class TemplateListResponse(BaseModel):
    templates: List[TemplateResponse]
    total: int


class CreateQuestFromTemplateRequest(BaseModel):
    """Optional overrides when creating a quest from a template."""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=20, max_length=5000)
    budget: Optional[Decimal] = Field(None, ge=100, le=1_000_000)
    is_urgent: Optional[bool] = None
    deadline: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: Request,
    body: CreateTemplateRequest,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Create a quest template."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="create_template", limit=20, window_seconds=60)
    if current_user.role not in {"client", "admin"}:
        raise HTTPException(status_code=403, detail="Только заказчики и администраторы могут создавать шаблоны")

    result = await template_service.create_template(
        conn,
        owner_id=current_user.id,
        name=body.name,
        title=body.title,
        description=body.description,
        required_grade=body.required_grade,
        skills=body.skills,
        budget=body.budget,
        currency=body.currency,
        is_urgent=body.is_urgent,
        required_portfolio=body.required_portfolio,
    )
    return TemplateResponse(**result)


@router.get("/", response_model=TemplateListResponse)
async def list_templates(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """List current user's templates."""
    result = await template_service.list_templates(
        conn, current_user.id, limit=limit, offset=offset,
    )
    return TemplateListResponse(**result)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get a specific template."""
    result = await template_service.get_template(conn, template_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return TemplateResponse(**result)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: Request,
    body: UpdateTemplateRequest,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Update a template."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="update_template", limit=30, window_seconds=60)
    updates = body.model_dump(exclude_none=True)
    async with conn.transaction():
        result = await template_service.update_template(conn, template_id, current_user.id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return TemplateResponse(**result)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    request: Request,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Delete a template."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="delete_template", limit=15, window_seconds=60)
    async with conn.transaction():
        deleted = await template_service.delete_template(conn, template_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Шаблон не найден")


@router.post("/{template_id}/create-quest", status_code=status.HTTP_201_CREATED)
async def create_quest_from_template(
    template_id: str,
    request: Request,
    body: CreateQuestFromTemplateRequest | None = None,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Create a quest from a template, optionally overriding fields."""
    ip = get_client_ip(request)
    await check_rate_limit(ip, action="create_quest_from_template", limit=20, window_seconds=60)
    if current_user.role not in {"client", "admin"}:
        raise HTTPException(status_code=403, detail="Только заказчики и администраторы могут создавать квесты")

    async with conn.transaction():
        tpl = await template_service.get_template(conn, template_id, current_user.id)
        if not tpl:
            raise HTTPException(status_code=404, detail="Шаблон не найден")

        # Merge template defaults with optional overrides
        title = (body.title if body and body.title else tpl["title"]) or "Новый квест"
        description = (body.description if body and body.description else tpl["description"]) or "Описание квеста из шаблона"
        budget = body.budget if (body and body.budget is not None) else tpl["budget"]
        if budget is None:
            budget = Decimal("100")
        is_urgent = body.is_urgent if body and body.is_urgent is not None else tpl["is_urgent"]

        # Ensure description meets QuestCreate minimum (20 chars)
        if len(description) < 20:
            description = description + " " * (20 - len(description))

        deadline = None
        if body and body.deadline:
            from datetime import datetime, timezone
            try:
                deadline = datetime.fromisoformat(body.deadline)
            except ValueError:
                raise HTTPException(status_code=400, detail="Некорректный формат дедлайна")

        quest_data = QuestCreate(
            title=title,
            description=description,
            required_grade=GradeEnum(tpl["required_grade"]),
            skills=tpl["skills"],
            budget=budget,
            currency=tpl["currency"],
            is_urgent=is_urgent,
            deadline=deadline,
            required_portfolio=tpl["required_portfolio"],
        )

        quest = await quest_service.create_quest(conn, quest_data, current_user)
    return quest.model_dump(mode="json")
