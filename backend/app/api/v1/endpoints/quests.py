"""
Endpoints для работы с квестами
CRUD: Create, Read, Update, Delete + отклики
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.rewards import (
    calculate_quest_rewards,
    calculate_xp_reward,
    check_level_up,
)
from app.core.security import decode_access_token
from app.models.quest import (
    Quest,
    QuestApplication,
    QuestApplicationCreate,
    QuestCreate,
    QuestListResponse,
    QuestStatusEnum,
    QuestUpdate,
)
from app.models.user import GradeEnum, UserProfile

# Настройка логирования
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quests", tags=["Quests"])

# ============================================
# Mock-хранилище квестов
# ============================================

QUESTS_DB: Dict[str, Quest] = {}
APPLICATIONS_DB: Dict[str, QuestApplication] = {}

# Демо-квесты
DEMO_QUESTS = [
    Quest(
        id=str(uuid.uuid4()),
        client_id="user_123456",
        client_username="novice_dev",
        title="Создать лендинг для кофейни",
        description="Нужен одностраничный сайт для небольшой кофейни. Дизайн есть в Figma, нужно сверстать и натянуть на простую CMS.",
        required_grade=GradeEnum.novice,
        skills=["HTML", "CSS", "JavaScript"],
        budget=5000,
        currency="RUB",
        xp_reward=100,
        status=QuestStatusEnum.open,
        applications=[],
        assigned_to=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ),
    Quest(
        id=str(uuid.uuid4()),
        client_id="user_789012",
        client_username="junior_coder",
        title="Парсер данных с сайта",
        description="Требуется написать парсер для сбора данных о товарах с маркетплейса. Python, BeautifulSoup/Selenium. Данные сохранять в CSV.",
        required_grade=GradeEnum.junior,
        skills=["Python", "Web Scraping", "BeautifulSoup"],
        budget=15000,
        currency="RUB",
        xp_reward=200,
        status=QuestStatusEnum.open,
        applications=[],
        assigned_to=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ),
    Quest(
        id=str(uuid.uuid4()),
        client_id="user_345678",
        client_username="middle_master",
        title="Telegram бот для записи клиентов",
        description="Нужен бот для автоматизации записи клиентов в салон красоты. Интеграция с Google Calendar, уведомления, админка.",
        required_grade=GradeEnum.middle,
        skills=["Python", "aiogram", "Google API"],
        budget=50000,
        currency="RUB",
        xp_reward=400,
        status=QuestStatusEnum.in_progress,
        applications=["user_123456"],
        assigned_to="user_123456",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ),
]

for quest in DEMO_QUESTS:
    QUESTS_DB[quest.id] = quest


# ============================================
# Вспомогательные функции
# ============================================


async def get_current_user(
    authorization: Optional[str] = Header(None),
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

    from app.api.v1.endpoints.users import MOCK_USERS

    user_id = payload.get("sub")

    # Try MOCK_USERS first (demo users)
    user = MOCK_USERS.get(user_id)

    # If not found, try USERS_DB (registered users)
    if not user:
        try:
            from app.api.v1.endpoints.users import get_user_from_auth_db

            user = get_user_from_auth_db(user_id)
            if user:
                logger.info(f"Found user in USERS_DB: {user.username}")
        except ImportError as e:
            logger.warning(f"Could not import get_user_from_auth_db: {e}")

    if user:
        logger.info(f"User authenticated: {user.username} ({user.id})")
    else:
        logger.warning(f"User not found: {user_id}")

    return user


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
):
    """Получить список всех квестов с фильтрацией"""
    logger.info(f"Getting quests: page={page}, status={status_filter}")

    quests = list(QUESTS_DB.values())

    if status_filter:
        quests = [q for q in quests if q.status == status_filter]
    if grade_filter:
        quests = [q for q in quests if q.required_grade == grade_filter]
    if skill_filter:
        quests = [
            q for q in quests if skill_filter.lower() in [s.lower() for s in q.skills]
        ]
    if min_budget is not None:
        quests = [q for q in quests if q.budget >= min_budget]
    if max_budget is not None:
        quests = [q for q in quests if q.budget <= max_budget]

    quests.sort(key=lambda q: q.created_at, reverse=True)

    total = len(quests)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_quests = quests[start:end]

    logger.info(f"Found {total} quests, returning {len(paginated_quests)}")

    return QuestListResponse(
        quests=paginated_quests,
        total=total,
        page=page,
        page_size=page_size,
        has_more=end < total,
    )


@router.get("/{quest_id}", response_model=Quest)
async def get_quest(quest_id: str):
    """Получить детали квеста по ID"""
    logger.info(f"Getting quest: {quest_id}")

    if quest_id not in QUESTS_DB:
        logger.warning(f"Quest not found: {quest_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    return QUESTS_DB[quest_id]


@router.post("/", response_model=Quest, status_code=status.HTTP_201_CREATED)
async def create_quest(
    quest_data: QuestCreate, current_user: UserProfile = Depends(require_auth)
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

    quest = Quest(
        id=str(uuid.uuid4()),
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
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    QUESTS_DB[quest.id] = quest
    logger.info(f"Quest created: {quest.id}")

    return quest


@router.post("/{quest_id}/apply")
async def apply_to_quest(
    quest_id: str,
    application_data: QuestApplicationCreate,
    current_user: UserProfile = Depends(require_auth),
):
    """Откликнуться на квест"""
    logger.info(f"Apply request: quest_id={quest_id}, user={current_user.username}")

    logger.info(f"User authenticated: {current_user.username} ({current_user.id})")

    if quest_id not in QUESTS_DB:
        logger.error(f"Quest not found: {quest_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    quest = QUESTS_DB[quest_id]
    logger.info(f"Quest found: {quest.title}, status={quest.status}")

    if quest.status != QuestStatusEnum.open:
        logger.error(f"Quest status is not open: {quest.status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot apply to quest with status: {quest.status}",
        )

    if quest.client_id == current_user.id:
        logger.error("User trying to apply to own quest")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot apply to your own quest",
        )

    if current_user.id in quest.applications:
        logger.error("User already applied")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already applied to this quest",
        )

    quest_grade_level = get_user_grade_level(quest.required_grade)
    user_grade_level = get_user_grade_level(current_user.grade)

    logger.info(
        f"Grade check: quest requires {quest.required_grade} (level {quest_grade_level}), user has {current_user.grade} (level {user_grade_level})"
    )

    if user_grade_level < quest_grade_level:
        logger.error(
            f"User grade too low: {current_user.grade} < {quest.required_grade}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Your grade ({current_user.grade}) is lower than required ({quest.required_grade})",
        )

    quest.applications.append(current_user.id)
    quest.updated_at = datetime.now(timezone.utc)

    application = QuestApplication(
        id=str(uuid.uuid4()),
        quest_id=quest_id,
        freelancer_id=current_user.id,
        freelancer_username=current_user.username,
        freelancer_grade=current_user.grade,
        cover_letter=application_data.cover_letter,
        proposed_price=application_data.proposed_price,
        created_at=datetime.now(timezone.utc),
    )

    APPLICATIONS_DB[application.id] = application

    logger.info(f"Application successful: {application.id}")

    return {"message": "Application submitted successfully", "application": application}


@router.post("/{quest_id}/assign")
async def assign_quest(
    quest_id: str, freelancer_id: str, current_user: UserProfile = Depends(require_auth)
):
    """Назначить исполнителя на квест"""
    logger.info(f"Assign request: quest_id={quest_id}, freelancer={freelancer_id}")

    if quest_id not in QUESTS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    quest = QUESTS_DB[quest_id]

    if quest.client_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client can assign freelancer",
        )

    if quest.status != QuestStatusEnum.open:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign freelancer to quest with status: {quest.status}",
        )

    if freelancer_id not in quest.applications:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This user has not applied to the quest",
        )

    quest.assigned_to = freelancer_id
    quest.status = QuestStatusEnum.in_progress
    quest.updated_at = datetime.now(timezone.utc)

    logger.info(f"Freelancer assigned: {freelancer_id}")

    return {"message": "Freelancer assigned successfully", "quest": quest}


@router.post("/{quest_id}/complete")
async def complete_quest(
    quest_id: str, current_user: UserProfile = Depends(require_auth)
):
    """Завершить квест (исполнитель)"""
    logger.info(f"Complete request: quest_id={quest_id}")

    if quest_id not in QUESTS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    quest = QUESTS_DB[quest_id]

    if quest.status != QuestStatusEnum.in_progress:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only complete quest that is in progress",
        )

    if quest.assigned_to != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only assigned freelancer can complete quest",
        )

    quest.status = QuestStatusEnum.completed
    quest.completed_at = datetime.now(timezone.utc)
    quest.updated_at = datetime.now(timezone.utc)

    logger.info(f"Quest completed by freelancer: {current_user.id}")

    return {
        "message": "Quest marked as completed. Awaiting client confirmation.",
        "quest": quest,
        "xp_earned": quest.xp_reward,
    }


@router.post("/{quest_id}/confirm")
async def confirm_quest_completion(
    quest_id: str, current_user: UserProfile = Depends(require_auth)
):
    """
    Подтвердить завершение квеста (клиент)

    Это основной endpoint для подтверждения выполнения квеста.
    После подтверждения:
    - Статус квеста меняется на "completed"
    - Фрилансер получает XP и деньги
    - Клиент получает подтверждение
    """
    logger.info(f"Confirm request: quest_id={quest_id}")

    if quest_id not in QUESTS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    quest = QUESTS_DB[quest_id]

    if quest.client_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client can confirm completion",
        )

    if quest.status != QuestStatusEnum.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quest has not been marked as completed by freelancer",
        )

    # Получаем данные фрилансера (сначала MOCK_USERS, потом auth.USERS_DB)
    from app.api.v1.endpoints.users import MOCK_USERS, get_user_from_auth_db

    freelancer = MOCK_USERS.get(quest.assigned_to) or get_user_from_auth_db(
        quest.assigned_to
    )

    if not freelancer:
        logger.error(f"Freelancer not found: {quest.assigned_to}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Freelancer not found"
        )

    # Расчёт наград
    xp_reward, money_reward = calculate_quest_rewards(
        budget=quest.budget,
        quest_grade=quest.required_grade,
        user_grade=freelancer.grade,
    )

    logger.info(
        f"Quest confirmed. Freelancer: {freelancer.username}, XP: {xp_reward}, Money: {money_reward}"
    )

    # Начисляем XP фрилансеру
    freelancer.xp += xp_reward
    freelancer.updated_at = datetime.now(timezone.utc)

    # Проверяем повышение грейда/уровня
    level_up, new_grade, new_level = check_level_up(freelancer.xp, freelancer.grade)
    if level_up:
        freelancer.grade = new_grade
        logger.info(f"Level up! {freelancer.username} is now {new_grade}")
    freelancer.level = new_level

    # Сохраняем обновлённого фрилансера в обоих хранилищах
    from app.api.v1.endpoints.users import MOCK_USERS as _MOCK_USERS

    if quest.assigned_to in _MOCK_USERS:
        _MOCK_USERS[quest.assigned_to] = freelancer

    try:
        from app.api.v1.endpoints import auth as _auth

        for _uname, _uinfo in _auth.USERS_DB.items():
            if _uinfo["profile"].id == quest.assigned_to:
                _uinfo["profile"].xp = freelancer.xp
                _uinfo["profile"].level = freelancer.level
                _uinfo["profile"].grade = freelancer.grade
                _uinfo["profile"].updated_at = freelancer.updated_at
                break
    except (ImportError, AttributeError):
        pass

    return {
        "message": "Quest confirmed! Reward has been paid.",
        "quest": quest,
        "xp_reward": xp_reward,
        "money_reward": money_reward,
        "freelancer_username": freelancer.username,
    }


@router.post("/{quest_id}/cancel")
async def cancel_quest(
    quest_id: str, current_user: UserProfile = Depends(require_auth)
):
    """Отменить квест"""
    logger.info(f"Cancel request: quest_id={quest_id}")

    if quest_id not in QUESTS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    quest = QUESTS_DB[quest_id]

    if quest.client_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only client can cancel quest"
        )

    if quest.status in [QuestStatusEnum.completed, QuestStatusEnum.cancelled]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel quest with status: {quest.status}",
        )

    quest.status = QuestStatusEnum.cancelled
    quest.updated_at = datetime.now(timezone.utc)

    logger.info(f"Quest cancelled: {quest_id}")

    return {"message": "Quest cancelled successfully", "quest": quest}


@router.get("/{quest_id}/applications")
async def get_quest_applications(
    quest_id: str, current_user: UserProfile = Depends(require_auth)
):
    """Получить список откликов на квест"""
    logger.info(f"Get applications: quest_id={quest_id}")

    if quest_id not in QUESTS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )

    quest = QUESTS_DB[quest_id]

    if quest.client_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client can view applications",
        )

    applications = [app for app in APPLICATIONS_DB.values() if app.quest_id == quest_id]

    logger.info(f"Found {len(applications)} applications")

    return {"applications": applications, "total": len(applications)}
