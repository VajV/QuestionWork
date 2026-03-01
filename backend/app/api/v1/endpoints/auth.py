"""
Endpoints для аутентификации
Регистрация, логин, logout
"""

from fastapi import APIRouter, HTTPException, status, Request
from datetime import datetime, timezone
from typing import Dict
from collections import defaultdict
import uuid
import time

from app.models.user import UserCreate, UserLogin, TokenResponse, UserProfile, UserStats, GradeEnum, UserRoleEnum
from app.core.security import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Аутентификация"])

_login_attempts: Dict[str, list] = defaultdict(list)
_RATE_LIMIT_WINDOW = 300
_RATE_LIMIT_MAX = 10


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _RATE_LIMIT_WINDOW]
    if len(_login_attempts[ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Слишком много попыток")
    _login_attempts[ip].append(now)

USERS_DB: Dict[str, dict] = {
    "novice_dev": {
        "password_hash": get_password_hash("password123"),
        "profile": UserProfile(
            id="user_123456",
            username="novice_dev",
            email="novice@example.com",
            role=UserRoleEnum.freelancer,
            level=1, grade=GradeEnum.novice, xp=0, xp_to_next=100,
            stats=UserStats(int=10, dex=10, cha=10),
            badges=[],
            created_at=datetime(2026, 2, 28),
            updated_at=datetime(2026, 2, 28)
        )
    },
    "client_user": {
        "password_hash": get_password_hash("client123"),
        "profile": UserProfile(
            id="user_client_001",
            username="client_user",
            email="client@example.com",
            role=UserRoleEnum.client,
            level=1, grade=GradeEnum.novice, xp=0, xp_to_next=100,
            stats=UserStats(int=10, dex=10, cha=10),
            badges=[],
            created_at=datetime(2026, 2, 28),
            updated_at=datetime(2026, 2, 28)
        )
    }
}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    if user_data.username in USERS_DB:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь уже существует")
    
    for user_info in USERS_DB.values():
        if user_info["profile"].email == user_data.email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email уже зарегистрирован")
    
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    user_profile = UserProfile(
        id=user_id, username=user_data.username, email=user_data.email,
        role=user_data.role, level=1, grade=GradeEnum.novice, xp=0, xp_to_next=100,
        stats=UserStats(int=10, dex=10, cha=10), badges=[],
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)
    )
    
    password_hash = get_password_hash(user_data.password)
    USERS_DB[user_data.username] = {"password_hash": password_hash, "profile": user_profile}
    access_token = create_access_token(data={"sub": user_id})
    
    return TokenResponse(access_token=access_token, token_type="bearer", user=user_profile)


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, request: Request):
    _check_rate_limit(request.client.host if request.client else "unknown")
    
    if credentials.username not in USERS_DB:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверное имя пользователя или пароль")
    
    user_info = USERS_DB[credentials.username]
    if not verify_password(credentials.password, user_info["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверное имя пользователя или пароль")
    
    access_token = create_access_token(data={"sub": user_info["profile"].id})
    return TokenResponse(access_token=access_token, token_type="bearer", user=user_info["profile"])


@router.post("/logout")
async def logout():
    return {"message": "Успешный выход"}
