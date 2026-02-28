"""
Endpoints для работы с пользователями
Получение профиля, обновление, список

TODO: Заменить mock-хранилище на PostgreSQL
"""

from fastapi import APIRouter, HTTPException, status
from typing import List, Dict
from datetime import datetime

from app.models.user import UserProfile, UserStats, GradeEnum, UserBadge

router = APIRouter(prefix="/users", tags=["Пользователи"])


# Mock-база данных пользователей
# В auth.py добавляются новые пользователи при регистрации
MOCK_USERS: Dict[str, UserProfile] = {
    "user_123456": UserProfile(
        id="user_123456",
        username="novice_dev",
        email="novice@example.com",
        level=1,
        grade=GradeEnum.novice,
        xp=0,
        xp_to_next=100,
        stats=UserStats(int=10, dex=10, cha=10),
        badges=[],
        created_at=datetime(2026, 2, 28),
        updated_at=datetime(2026, 2, 28)
    ),
    "user_789012": UserProfile(
        id="user_789012",
        username="junior_coder",
        email="junior@example.com",
        level=5,
        grade=GradeEnum.junior,
        xp=450,
        xp_to_next=500,
        stats=UserStats(int=15, dex=12, cha=14),
        badges=[
            UserBadge(
                id="badge_001",
                name="Первый квест",
                description="Выполнить первый квест",
                icon="🎯",
                earned_at=datetime(2026, 2, 25)
            )
        ],
        created_at=datetime(2026, 1, 15),
        updated_at=datetime(2026, 2, 28)
    ),
    "user_345678": UserProfile(
        id="user_345678",
        username="middle_master",
        email="middle@example.com",
        level=15,
        grade=GradeEnum.middle,
        xp=1200,
        xp_to_next=1500,
        stats=UserStats(int=25, dex=20, cha=22),
        badges=[],
        created_at=datetime(2025, 10, 1),
        updated_at=datetime(2026, 2, 28)
    )
}


def get_user_from_auth_db(user_id: str) -> UserProfile | None:
    """
    Попытка получить пользователя из auth.py USERS_DB
    Это нужно для связи между регистрацией и профилем
    """
    try:
        from app.api.v1.endpoints import auth
        # Ищем пользователя по ID в auth базе
        for username, user_info in auth.USERS_DB.items():
            if user_info["profile"].id == user_id:
                return user_info["profile"]
    except (ImportError, AttributeError):
        pass
    return None


@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(user_id: str):
    """
    Получить профиль пользователя по ID
    
    - **user_id**: Уникальный идентификатор пользователя
    
    Возвращает полный профиль с RPG характеристиками:
    - Уровень и грейд
    - Опыт (XP)
    - Статы (INT, DEX, CHA)
    - Бейджи достижений
    """
    # Сначала ищем в MOCK_USERS
    if user_id in MOCK_USERS:
        return MOCK_USERS[user_id]
    
    # Пытаемся найти в auth базе (для ново зарегистрированных)
    user = get_user_from_auth_db(user_id)
    if user:
        return user
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Пользователь с ID {user_id} не найден"
    )


@router.get("/", response_model=List[UserProfile])
async def get_all_users(
    skip: int = 0,
    limit: int = 10,
    grade: str = None
):
    """
    Получить список всех пользователей
    
    - **skip**: Пропустить N пользователей (пагинация)
    - **limit**: Максимальное количество результатов
    - **grade**: Фильтр по грейду (novice, junior, middle, senior)
    """
    users = list(MOCK_USERS.values())
    
    # Фильтр по грейду
    if grade:
        users = [u for u in users if u.grade == grade]
    
    # Пагинация
    return users[skip:skip + limit]


@router.get("/{user_id}/stats")
async def get_user_stats(user_id: str):
    """
    Получить только характеристики пользователя
    
    Удобно для быстрого получения стат без лишних данных
    """
    if user_id not in MOCK_USERS:
        # Пытаемся найти в auth базе
        user = get_user_from_auth_db(user_id)
        if user:
            return user.stats
            
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )
    
    return MOCK_USERS[user_id].stats
