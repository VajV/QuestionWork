"""
Endpoints для аутентификации
Регистрация, логин, logout

TODO: Заменить mock-хранилище на реальную БД (PostgreSQL)
"""

from fastapi import APIRouter, HTTPException, status
from datetime import datetime
from typing import Dict

from app.models.user import UserCreate, UserLogin, TokenResponse, UserProfile, UserStats, GradeEnum
from app.core.security import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Аутентификация"])

# ============================================
# Mock-хранилище пользователей (временно!)
# В реальности будет PostgreSQL
# ============================================

# Хранилище пользователей: username -> {password_hash, profile}
USERS_DB: Dict[str, dict] = {
    # Демо-пользователь для тестирования
    "novice_dev": {
        "password_hash": get_password_hash("password123"),
        "profile": UserProfile(
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
        )
    }
}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """
    Регистрация нового пользователя
    
    - **username**: Имя пользователя (3-50 символов)
    - **email**: Email адрес
    - **password**: Пароль (минимум 8 символов)
    
    Возвращает токен доступа и профиль пользователя
    """
    # Проверяем существование пользователя
    if user_data.username in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким именем уже существует"
        )
    
    # Проверяем email (опционально)
    for user_info in USERS_DB.values():
        if user_info["profile"].email == user_data.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email уже зарегистрирован"
            )
    
    # Создаём новый профиль
    user_id = f"user_{datetime.utcnow().timestamp()}"
    user_profile = UserProfile(
        id=user_id,
        username=user_data.username,
        email=user_data.email,
        level=1,
        grade=GradeEnum.novice,
        xp=0,
        xp_to_next=100,
        stats=UserStats(int=10, dex=10, cha=10),
        badges=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Хешируем пароль и сохраняем пользователя
    password_hash = get_password_hash(user_data.password)
    USERS_DB[user_data.username] = {
        "password_hash": password_hash,
        "profile": user_profile
    }
    
    # Создаём access токен
    access_token = create_access_token(data={"sub": user_id})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_profile
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """
    Вход в систему
    
    - **username**: Имя пользователя
    - **password**: Пароль
    
    Возвращает токен доступа и профиль пользователя
    """
    # Ищем пользователя
    if credentials.username not in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_info = USERS_DB[credentials.username]
    
    # Проверяем пароль
    if not verify_password(credentials.password, user_info["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Создаём access токен
    access_token = create_access_token(data={"sub": user_info["profile"].id})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_info["profile"]
    )


@router.post("/logout")
async def logout():
    """
    Выход из системы
    
    В будущем здесь будет добавление токена в blacklist (Redis)
    """
    # TODO: Реализовать blacklist токенов в Redis
    return {"message": "Успешный выход"}
