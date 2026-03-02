"""
Endpoints для работы с квестами
CRUD: Create, Read, Update, Delete + отклики
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.rewards import (
    calculate_quest_rewards,
    calculate_xp_reward,
    calculate_xp_to_next,
    check_level_up,
)
from app.core.security import decode_access_token
from app.db.session import get_db_connection
from app.models.quest import (
    Quest,
    QuestApplication,
    QuestApplicationCreate,
    QuestCreate,
    QuestListResponse,
    QuestStatusEnum,
)
from app.models.user import GradeEnum, UserProfile, row_to_user_profile
from app.core.otel_utils import db_span

# Настройка логирования
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quests", tags=["Quests"])

# ============================================
# Вспомогательные функции
# ============================================


async def get_current_user(
    authorization: Optional[str] = Header(None),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> Optional[UserProfile]:
    """Получить текущего пользователя из токена"""
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("No authorization header or invalid format")
        return None

    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)

    if not payload:
        logger.warning("Invalid token")
        return None

    user_id = payload.get("sub")

    with db_span("db.fetchrow", query="SELECT * FROM users WHERE id = $1", params=[user_id]):
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    if row:
        user = row_to_user_profile(row)
        logger.info(f"User authenticated: {user.username} ({user.id})")
        return user
    else:
        logger.warning(f"User not found: {user_id}")
        return None


async def require_auth(
    current_user: Optional[UserProfile] = Depends(get_current_user),
) -> UserProfile:
    """Dependency, требующая авторизацию. Выбрасывает 401 если пользователь не авторизован."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization required"
        )
    return current_user


def get_user_grade_level(grade: GradeEnum) -> int:
    """Получить числовой уровень грейда"""
    from app.core.rewards import get_grade_level

    return get_grade_level(grade)


# ============================================
# Endpoints
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
    logger.info(f"Getting quests: page={page}, status={status_filter}")

    query = "SELECT * FROM quests WHERE 1=1"
    args = []
    arg_idx = 1

    if status_filter:
        query += f" AND status = ${arg_idx}"
        args.append(status_filter.value)
        arg_idx += 1
    if grade_filter:
        query += f" AND required_grade = ${arg_idx}"
        args.append(grade_filter.value)
        arg_idx += 1
    if skill_filter:
        query += f" AND skills::jsonb @> ${arg_idx}::jsonb"
        args.append(json.dumps([skill_filter]))
        arg_idx += 1
    if min_budget is not None:
        query += f" AND budget >= ${arg_idx}"
        args.append(min_budget)
        arg_idx += 1
    if max_budget is not None:
        query += f" AND budget <= ${arg_idx}"
        args.append(max_budget)
        arg_idx += 1

    # Получаем общее количество
    count_query = f"SELECT COUNT(*) FROM ({query}) as count_query"
    with db_span("db.fetchval", query=count_query, params=args):
        total = await conn.fetchval(count_query, *args)

    # Добавляем сортировку и пагинацию
    query += f" ORDER BY created_at DESC LIMIT ${arg_idx} OFFSET ${arg_idx + 1}"
    args.extend([page_size, (page - 1) * page_size])

    with db_span("db.fetch", query=query, params=args):
        rows = await conn.fetch(query, *args)

    # Batch-fetch all applications for these quests in a single query (fix N+1)
    quest_ids = [row["id"] for row in rows]
    apps_map: dict[str, list[str]] = {qid: [] for qid in quest_ids}
    if quest_ids:
        apps_query = "SELECT quest_id, freelancer_id FROM applications WHERE quest_id = ANY($1)"
        with db_span("db.fetch", query=apps_query, params=[quest_ids]):
            app_rows = await conn.fetch(apps_query, quest_ids)
        for app_row in app_rows:
            apps_map[app_row["quest_id"]].append(app_row["freelancer_id"])

    quests = []
    for row in rows:
        applications = apps_map.get(row["id"], [])

        quests.append(
            Quest(
                id=row["id"],
                client_id=row["client_id"],
                client_username=row["client_username"],
                title=row["title"],
                description=row["description"],
                required_grade=GradeEnum(row["required_grade"]),
                skills=json.loads(row["skills"]) if row["skills"] else [],
                budget=float(row["budget"]),
                currency=row["currency"],
                xp_reward=row["xp_reward"],
                status=QuestStatusEnum(row["status"]),
                applications=applications,
                assigned_to=row["assigned_to"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                completed_at=row["completed_at"],
            )
        )

    logger.info(f"Found {total} quests, returning {len(quests)}")

    safe_total = int(total or 0)

    return QuestListResponse(
        quests=quests,
        total=safe_total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < safe_total,
    )


@router.get("/{quest_id}", response_model=Quest)
async def get_quest(
    quest_id: str, conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Получить детали квеста по ID"""
    logger.info(f"Getting quest: {quest_id}")

    with db_span("db.fetchrow", query="SELECT * FROM quests WHERE id = $1", params=[quest_id]):
        row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not row:
        logger.warning(f"Quest not found: {quest_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    apps_query = "SELECT freelancer_id FROM applications WHERE quest_id = $1"
    with db_span("db.fetch", query=apps_query, params=[quest_id]):
        app_rows = await conn.fetch(apps_query, quest_id)
    applications = [app_row["freelancer_id"] for app_row in app_rows]

    return Quest(
        id=row["id"],
        client_id=row["client_id"],
        client_username=row["client_username"],
        title=row["title"],
        description=row["description"],
        required_grade=GradeEnum(row["required_grade"]),
        skills=json.loads(row["skills"]) if row["skills"] else [],
        budget=float(row["budget"]),
        currency=row["currency"],
        xp_reward=row["xp_reward"],
        status=QuestStatusEnum(row["status"]),
        applications=applications,
        assigned_to=row["assigned_to"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
    )


@router.post("/", response_model=Quest, status_code=status.HTTP_201_CREATED)
async def create_quest(
    quest_data: QuestCreate,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Создать новый квест"""
    logger.info(f"Creating quest for user: {current_user.username}")

    xp_reward = quest_data.xp_reward
    if xp_reward is None:
        xp_reward = calculate_xp_reward(
            budget=quest_data.budget,
            quest_grade=quest_data.required_grade,
            user_grade=GradeEnum.novice,
        )

    quest_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    with db_span("db.execute", query="INSERT INTO quests (...) VALUES (...)", params=[quest_id, current_user.id, current_user.username]):
        await conn.execute(
        """
        INSERT INTO quests (
            id, client_id, client_username, title, description, required_grade,
            skills, budget, currency, xp_reward, status, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """,
        quest_id,
        current_user.id,
        current_user.username,
        quest_data.title,
        quest_data.description,
        quest_data.required_grade.value,
        json.dumps(quest_data.skills),
        quest_data.budget,
        quest_data.currency,
        xp_reward,
        QuestStatusEnum.open.value,
        now,
        now,
    )

    quest = Quest(
        id=quest_id,
        client_id=current_user.id,
        client_username=current_user.username,
        title=quest_data.title,
        description=quest_data.description,
        required_grade=quest_data.required_grade,
        skills=quest_data.skills,
        budget=quest_data.budget,
        currency=quest_data.currency,
        xp_reward=xp_reward,
        status=QuestStatusEnum.open,
        applications=[],
        assigned_to=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )

    logger.info(f"Quest created: {quest.id}")

    return quest


@router.post("/{quest_id}/apply")
async def apply_to_quest(
    quest_id: str,
    application_data: QuestApplicationCreate,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Откликнуться на квест"""
    logger.info(f"Apply request: quest_id={quest_id}, user={current_user.username}")

    logger.info(f"User authenticated: {current_user.username} ({current_user.id})")

    with db_span("db.fetchrow", query="SELECT * FROM quests WHERE id = $1", params=[quest_id]):
        quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        logger.error(f"Quest not found: {quest_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    logger.info(f"Quest found: {quest['title']}, status={quest['status']}")

    if quest["status"] != QuestStatusEnum.open.value:
        logger.error(f"Quest status is not open: {quest['status']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot apply to quest with status: {quest['status']}",
        )

    if quest["client_id"] == current_user.id:
        logger.error("User trying to apply to own quest")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot apply to your own quest",
        )

    with db_span("db.fetchrow", query="SELECT id FROM applications WHERE quest_id = $1 AND freelancer_id = $2", params=[quest_id, current_user.id]):
        existing_app = await conn.fetchrow(
            "SELECT id FROM applications WHERE quest_id = $1 AND freelancer_id = $2",
            quest_id,
            current_user.id,
        )

    if existing_app:
        logger.error("User already applied")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already applied to this quest",
        )

    quest_required_grade = GradeEnum(quest["required_grade"])
    quest_grade_level = get_user_grade_level(quest_required_grade)
    user_grade_level = get_user_grade_level(current_user.grade)

    logger.info(
        f"Grade check: quest requires {quest_required_grade} (level {quest_grade_level}), user has {current_user.grade} (level {user_grade_level})"
    )

    if user_grade_level < quest_grade_level:
        logger.error(
            f"User grade too low: {current_user.grade} < {quest_required_grade}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Your grade ({current_user.grade}) is lower than required ({quest_required_grade})",
        )

    application_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    with db_span("db.execute", query="INSERT INTO applications (...) VALUES (...)", params=[application_id, quest_id, current_user.id]):
        await conn.execute(
        """
        INSERT INTO applications (
            id, quest_id, freelancer_id, freelancer_username, freelancer_grade,
            cover_letter, proposed_price, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        application_id,
        quest_id,
        current_user.id,
        current_user.username,
        str(current_user.grade),
        application_data.cover_letter,
        application_data.proposed_price,
        now,
    )

    with db_span("db.execute", query="UPDATE quests SET updated_at = $1 WHERE id = $2", params=[now, quest_id]):
        await conn.execute("UPDATE quests SET updated_at = $1 WHERE id = $2", now, quest_id)

    application = QuestApplication(
        id=application_id,
        quest_id=quest_id,
        freelancer_id=current_user.id,
        freelancer_username=current_user.username,
        freelancer_grade=current_user.grade,
        cover_letter=application_data.cover_letter,
        proposed_price=application_data.proposed_price,
        created_at=now,
    )

    logger.info(f"Application successful: {application.id}")

    return {"message": "Application submitted successfully", "application": application}


@router.post("/{quest_id}/assign")
async def assign_quest(
    quest_id: str,
    freelancer_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Назначить исполнителя на квест"""
    logger.info(f"Assign request: quest_id={quest_id}, freelancer={freelancer_id}")

    with db_span("db.fetchrow", query="SELECT * FROM quests WHERE id = $1", params=[quest_id]):
        quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    if quest["client_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client can assign freelancer",
        )

    if quest["status"] != QuestStatusEnum.open.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign freelancer to quest with status: {quest['status']}",
        )

    with db_span("db.fetchrow", query="SELECT id FROM applications WHERE quest_id = $1 AND freelancer_id = $2", params=[quest_id, freelancer_id]):
        app = await conn.fetchrow(
            "SELECT id FROM applications WHERE quest_id = $1 AND freelancer_id = $2",
            quest_id,
            freelancer_id,
        )

    if not app:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user has not applied to the quest",
        )

    now = datetime.now(timezone.utc)
    with db_span("db.execute", query="UPDATE quests SET assigned_to = $1, status = $2, updated_at = $3 WHERE id = $4", params=[freelancer_id, QuestStatusEnum.in_progress.value, now, quest_id]):
        await conn.execute(
            "UPDATE quests SET assigned_to = $1, status = $2, updated_at = $3 WHERE id = $4",
            freelancer_id,
            QuestStatusEnum.in_progress.value,
            now,
            quest_id,
        )

    logger.info(f"Freelancer assigned: {freelancer_id}")

    with db_span("db.fetchrow", query="SELECT * FROM quests WHERE id = $1", params=[quest_id]):
        updated_quest_row = await conn.fetchrow(
            "SELECT * FROM quests WHERE id = $1", quest_id
        )
    with db_span("db.fetch", query="SELECT freelancer_id FROM applications WHERE quest_id = $1", params=[quest_id]):
        app_rows = await conn.fetch(
            "SELECT freelancer_id FROM applications WHERE quest_id = $1",
            quest_id,
        )
    applications = [app_row["freelancer_id"] for app_row in app_rows]

    if not updated_quest_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    quest_payload = Quest(
        id=updated_quest_row["id"],
        client_id=updated_quest_row["client_id"],
        client_username=updated_quest_row["client_username"],
        title=updated_quest_row["title"],
        description=updated_quest_row["description"],
        required_grade=GradeEnum(updated_quest_row["required_grade"]),
        skills=json.loads(updated_quest_row["skills"])
        if updated_quest_row["skills"]
        else [],
        budget=float(updated_quest_row["budget"]),
        currency=updated_quest_row["currency"],
        xp_reward=updated_quest_row["xp_reward"],
        status=QuestStatusEnum(updated_quest_row["status"]),
        applications=applications,
        assigned_to=updated_quest_row["assigned_to"],
        created_at=updated_quest_row["created_at"],
        updated_at=updated_quest_row["updated_at"],
        completed_at=updated_quest_row["completed_at"],
    )

    return {"message": "Freelancer assigned successfully", "quest": quest_payload}


@router.post("/{quest_id}/complete")
async def complete_quest(
    quest_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Завершить квест (исполнитель)"""
    logger.info(f"Complete request: quest_id={quest_id}")

    quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    if quest["status"] != QuestStatusEnum.in_progress.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only complete quest that is in progress",
        )

    if quest["assigned_to"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only assigned freelancer can complete quest",
        )

    now = datetime.now(timezone.utc)
    with db_span("db.execute", query="UPDATE quests SET status = $1, completed_at = $2, updated_at = $3 WHERE id = $4", params=[QuestStatusEnum.completed.value, now, now, quest_id]):
        await conn.execute(
            "UPDATE quests SET status = $1, completed_at = $2, updated_at = $3 WHERE id = $4",
            QuestStatusEnum.completed.value,
            now,
            now,
            quest_id,
        )

    logger.info(f"Quest completed by freelancer: {current_user.id}")

    with db_span("db.fetchrow", query="SELECT * FROM quests WHERE id = $1", params=[quest_id]):
        updated_quest_row = await conn.fetchrow(
            "SELECT * FROM quests WHERE id = $1", quest_id
        )
    with db_span("db.fetch", query="SELECT freelancer_id FROM applications WHERE quest_id = $1", params=[quest_id]):
        app_rows = await conn.fetch(
            "SELECT freelancer_id FROM applications WHERE quest_id = $1",
            quest_id,
        )
    applications = [app_row["freelancer_id"] for app_row in app_rows]

    if not updated_quest_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    quest_payload = Quest(
        id=updated_quest_row["id"],
        client_id=updated_quest_row["client_id"],
        client_username=updated_quest_row["client_username"],
        title=updated_quest_row["title"],
        description=updated_quest_row["description"],
        required_grade=GradeEnum(updated_quest_row["required_grade"]),
        skills=json.loads(updated_quest_row["skills"])
        if updated_quest_row["skills"]
        else [],
        budget=float(updated_quest_row["budget"]),
        currency=updated_quest_row["currency"],
        xp_reward=updated_quest_row["xp_reward"],
        status=QuestStatusEnum(updated_quest_row["status"]),
        applications=applications,
        assigned_to=updated_quest_row["assigned_to"],
        created_at=updated_quest_row["created_at"],
        updated_at=updated_quest_row["updated_at"],
        completed_at=updated_quest_row["completed_at"],
    )

    return {
        "message": "Quest marked as completed. Awaiting client confirmation.",
        "quest": quest_payload,
        "xp_earned": quest["xp_reward"],
    }


@router.post("/{quest_id}/confirm")
async def confirm_quest_completion(
    quest_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """
    Подтвердить завершение квеста (клиент)

    Это основной endpoint для подтверждения выполнения квеста.
    После подтверждения:
    - Статус квеста остается "completed" (или можно поменять на paid)
    - Фрилансер получает XP и деньги
    - Клиент получает подтверждение
    """
    logger.info(f"Confirm request: quest_id={quest_id}")

    with db_span("db.fetchrow", query="SELECT * FROM quests WHERE id = $1", params=[quest_id]):
        quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    if quest["client_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client can confirm completion",
        )

    if quest["status"] != QuestStatusEnum.completed.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quest has not been marked as completed by freelancer",
        )

    freelancer_row = await conn.fetchrow(
        "SELECT * FROM users WHERE id = $1", quest["assigned_to"]
    )
    if not freelancer_row:
        logger.error(f"Freelancer not found: {quest['assigned_to']}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Freelancer not found"
        )

    # Расчёт наград
    quest_grade = GradeEnum(quest["required_grade"])
    freelancer_grade = GradeEnum(freelancer_row["grade"])

    xp_reward, money_reward = calculate_quest_rewards(
        budget=float(quest["budget"]),
        quest_grade=quest_grade,
        user_grade=freelancer_grade,
    )

    logger.info(
        f"Quest confirmed. Freelancer: {freelancer_row['username']}, XP: {xp_reward}, Money: {money_reward}"
    )

    # Начисляем XP фрилансеру
    new_xp = freelancer_row["xp"] + xp_reward
    now = datetime.now(timezone.utc)

    # Проверяем повышение грейда/уровня
    level_up, new_grade, new_level = check_level_up(new_xp, freelancer_grade)
    if level_up:
        logger.info(f"Level up! {freelancer_row['username']} is now {new_grade}")

    # Calculate xp_to_next for the (possibly new) grade
    new_xp_to_next = calculate_xp_to_next(new_xp, new_grade)

    # Сохраняем обновлённого фрилансера в БД
    await conn.execute(
        """
        UPDATE users
        SET xp = $1, level = $2, grade = $3, xp_to_next = $4, updated_at = $5
        WHERE id = $6
        """,
        new_xp,
        new_level,
        new_grade.value,
        new_xp_to_next,
        now,
        quest["assigned_to"],
    )

    await conn.execute(
        """
        INSERT INTO transactions (id, user_id, quest_id, amount, currency, type, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        str(uuid.uuid4()),
        quest["assigned_to"],
        quest_id,
        float(quest["budget"]),
        quest["currency"],
        "income",
        now,
    )

    return {
        "message": "Quest confirmed! Reward has been paid.",
        "xp_reward": xp_reward,
        "money_reward": money_reward,
        "freelancer_username": freelancer_row["username"],
    }


@router.post("/{quest_id}/cancel")
async def cancel_quest(
    quest_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Отменить квест"""
    logger.info(f"Cancel request: quest_id={quest_id}")

    quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    if quest["client_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only client can cancel quest"
        )

    if quest["status"] in [
        QuestStatusEnum.completed.value,
        QuestStatusEnum.cancelled.value,
    ]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel quest with status: {quest['status']}",
        )

    now = datetime.now(timezone.utc)
    with db_span("db.execute", query="UPDATE quests SET status = $1, updated_at = $2 WHERE id = $3", params=[QuestStatusEnum.cancelled.value, now, quest_id]):
        await conn.execute(
            "UPDATE quests SET status = $1, updated_at = $2 WHERE id = $3",
            QuestStatusEnum.cancelled.value,
            now,
            quest_id,
        )

    logger.info(f"Quest cancelled: {quest_id}")

    return {"message": "Quest cancelled successfully"}


@router.get("/{quest_id}/applications")
async def get_quest_applications(
    quest_id: str,
    current_user: UserProfile = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Получить список откликов на квест"""
    logger.info(f"Get applications: quest_id={quest_id}")

    with db_span("db.fetchrow", query="SELECT * FROM quests WHERE id = $1", params=[quest_id]):
        quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    if quest["client_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client can view applications",
        )

    with db_span("db.fetch", query="SELECT * FROM applications WHERE quest_id = $1 ORDER BY created_at DESC", params=[quest_id]):
        rows = await conn.fetch(
            "SELECT * FROM applications WHERE quest_id = $1 ORDER BY created_at DESC",
            quest_id,
        )

    applications = [
        QuestApplication(
            id=row["id"],
            quest_id=row["quest_id"],
            freelancer_id=row["freelancer_id"],
            freelancer_username=row["freelancer_username"],
            freelancer_grade=GradeEnum(row["freelancer_grade"]),
            cover_letter=row["cover_letter"],
            proposed_price=float(row["proposed_price"])
            if row["proposed_price"]
            else None,
            created_at=row["created_at"],
        )
        for row in rows
    ]

    logger.info(f"Found {len(applications)} applications")

    return {"applications": applications, "total": len(applications)}
