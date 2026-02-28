# QuestionWork Backend Setup Script
# Автоматическая настройка FastAPI проекта

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Backend Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$BACKEND_ROOT = Split-Path -Parent $PSScriptRoot
$APP_DIR = Join-Path $BACKEND_ROOT "app"

Write-Host "`n[1/6] Создание структуры папок..." -ForegroundColor Yellow

# Создаём папки
$folders = @(
    (Join-Path $APP_DIR "core"),
    (Join-Path $APP_DIR "models"),
    (Join-Path $APP_DIR "api"),
    (Join-Path $APP_DIR "api\v1"),
    (Join-Path $APP_DIR "api\v1\endpoints"),
    (Join-Path $APP_DIR "db"),
    (Join-Path $APP_DIR "services"),
    (Join-Path $APP_DIR "schemas")
)

foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder -Force | Out-Null
        Write-Host "  + $folder" -ForegroundColor Green
    }
}

Write-Host "`n[2/6] Создание requirements.txt..." -ForegroundColor Yellow

$requirements = @'
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-dotenv==1.0.0
pydantic==2.5.3
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
asyncpg==0.29.0
redis==5.0.1
httpx==0.26.0
'@

$requirementsPath = Join-Path $BACKEND_ROOT "requirements.txt"
$requirements | Out-File -FilePath $requirementsPath -Encoding UTF8 -Force
Write-Host "  + requirements.txt" -ForegroundColor Green

Write-Host "`n[3/6] Создание .env.example..." -ForegroundColor Yellow

$envExample = @'
# QuestionWork Backend Configuration

# Application
APP_NAME=QuestionWork
APP_ENV=development
DEBUG=True
SECRET_KEY=your-secret-key-change-in-production

# Server
HOST=127.0.0.1
PORT=8000

# Database (PostgreSQL)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/questionwork
REDIS_URL=redis://localhost:6379

# JWT Settings
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# CORS (Frontend URL)
FRONTEND_URL=http://localhost:3000

# OpenRouter API (для AI проверки)
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_MODEL=qwen/qwen-2.5-coder-32b-instruct
'@

$envExamplePath = Join-Path $BACKEND_ROOT ".env.example"
$envExample | Out-File -FilePath $envExamplePath -Encoding UTF8 -Force
Write-Host "  + .env.example" -ForegroundColor Green

# Создаём .env (копия .env.example для быстрого старта)
$envPath = Join-Path $BACKEND_ROOT ".env"
$envExample | Out-File -FilePath $envPath -Encoding UTF8 -Force
Write-Host "  + .env (готов к использованию)" -ForegroundColor Green

Write-Host "`n[4/6] Создание файлов приложения..." -ForegroundColor Yellow

# ============================================
# main.py
# ============================================
$mainPy = @'
"""
QuestionWork Backend - FastAPI Application
IT-фриланс биржа с RPG-геймификацией
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from app.api.v1.api import api_router

# Создаём FastAPI приложение
app = FastAPI(
    title=os.getenv("APP_NAME", "QuestionWork"),
    description="Backend для IT-фриланс биржи с RPG-геймификацией",
    version="0.1.0",
    debug=os.getenv("DEBUG", "False") == "True"
)

# Настраиваем CORS (разрешаем запросы с фронтенда)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем все методы (GET, POST, PUT, DELETE)
    allow_headers=["*"],  # Разрешаем все заголовки
)

# Подключаем роутеры
app.include_router(api_router, prefix="/api/v1")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Проверка работоспособности API"""
    return {"status": "ok", "message": "QuestionWork API is running"}

# Root endpoint
@app.get("/")
async def root():
    """Приветственный endpoint"""
    return {
        "message": "Welcome to QuestionWork API",
        "docs": "/docs",
        "version": "0.1.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "False") == "True"
    )
'@

$mainPath = Join-Path $APP_DIR "main.py"
$mainPy | Out-File -FilePath $mainPath -Encoding UTF8 -Force
Write-Host "  + app/main.py" -ForegroundColor Green

# ============================================
# core/config.py
# ============================================
$configPy = @'
"""
Конфигурация приложения
Загружает настройки из переменных окружения
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Application
    APP_NAME: str = "QuestionWork"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    
    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/questionwork"
    REDIS_URL: str = "redis://localhost:6379"
    
    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    
    # CORS
    FRONTEND_URL: str = "http://localhost:3000"
    
    # OpenRouter API
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "qwen/qwen-2.5-coder-32b-instruct"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Глобальный экземпляр настроек
settings = Settings()
'@

$configPath = Join-Path $APP_DIR "core\config.py"
$configPy | Out-File -FilePath $configPath -Encoding UTF8 -Force
Write-Host "  + app/core/config.py" -ForegroundColor Green

# ============================================
# core/security.py
# ============================================
$securityPy = @'
"""
Модуль безопасности
JWT токены, хеширование паролей
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

# Контекст для хеширования паролей (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверка пароля
    
    Args:
        plain_password: Пароль в открытом виде
        hashed_password: Хешированный пароль из БД
    
    Returns:
        True если пароль верный
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Хеширование пароля
    
    Args:
        password: Пароль в открытом виде
    
    Returns:
        Хешированный пароль
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создание JWT access токена
    
    Args:
        data: Данные для кодирования (обычно {"sub": user_id})
        expires_delta: Время жизни токена
    
    Returns:
        JWT токен в формате строки
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Декодирование JWT токена
    
    Args:
        token: JWT токен
    
    Returns:
        decoded данные или None если токен невалидный
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except Exception:
        return None
'@

$securityPath = Join-Path $APP_DIR "core\security.py"
$securityPy | Out-File -FilePath $securityPath -Encoding UTF8 -Force
Write-Host "  + app/core/security.py" -ForegroundColor Green

# ============================================
# models/user.py
# ============================================
$userModelPy = @'
"""
Pydantic модели пользователя
Используются для валидации данных и документации API
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class GradeEnum(str, Enum):
    """Грейды пользователей (RPG система)"""
    novice = "novice"
    junior = "junior"
    middle = "middle"
    senior = "senior"


class UserStats(BaseModel):
    """Характеристики пользователя (RPG статы)"""
    int: int = Field(default=10, description="Интеллект", ge=1, le=100)
    dex: int = Field(default=10, description="Ловкость", ge=1, le=100)
    cha: int = Field(default=10, description="Харизма", ge=1, le=100)
    
    class Config:
        populate_by_name = True


class UserBadge(BaseModel):
    """Бейдж достижения"""
    id: str
    name: str
    description: str
    icon: str
    earned_at: datetime


class UserProfile(BaseModel):
    """
    Профиль пользователя для API ответов
    
    Используется в endpoint GET /users/{id}
    """
    id: str = Field(..., description="Уникальный ID пользователя")
    username: str = Field(..., description="Имя пользователя", min_length=3, max_length=50)
    email: Optional[str] = Field(None, description="Email")
    
    # RPG система
    level: int = Field(default=1, description="Уровень", ge=1, le=100)
    grade: GradeEnum = Field(default=GradeEnum.novice, description="Грейд")
    xp: int = Field(default=0, description="Текущий опыт", ge=0)
    xp_to_next: int = Field(default=100, description="Опыт до следующего уровня")
    
    # Статы
    stats: UserStats = Field(default_factory=UserStats, description="Характеристики")
    
    # Достижения
    badges: List[UserBadge] = Field(default_factory=list, description="Бейджи")
    
    # Дополнительно
    bio: Optional[str] = Field(None, description="О себе", max_length=500)
    skills: List[str] = Field(default_factory=list, description="Навыки")
    
    # Метаданные
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class UserCreate(BaseModel):
    """Модель для регистрации пользователя"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """Модель для входа"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Ответ с токеном"""
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
'@

$userModelPath = Join-Path $APP_DIR "models\user.py"
$userModelPy | Out-File -FilePath $userModelPath -Encoding UTF8 -Force
Write-Host "  + app/models/user.py" -ForegroundColor Green

# ============================================
# __init__.py для models
# ============================================
$modelsInit = @'
from app.models.user import UserStats, UserBadge, UserProfile, UserCreate, UserLogin, TokenResponse, GradeEnum

__all__ = [
    "UserStats",
    "UserBadge", 
    "UserProfile",
    "UserCreate",
    "UserLogin",
    "TokenResponse",
    "GradeEnum"
]
'@

$modelsInitPath = Join-Path $APP_DIR "models\__init__.py"
$modelsInit | Out-File -FilePath $modelsInitPath -Encoding UTF8 -Force
Write-Host "  + app/models/__init__.py" -ForegroundColor Green

# ============================================
# api/v1/endpoints/auth.py
# ============================================
$authPy = @'
"""
Endpoints для аутентификации
Регистрация, логин, logout
"""

from fastapi import APIRouter, HTTPException, status
from datetime import datetime

from app.models.user import UserCreate, UserLogin, TokenResponse, UserProfile, UserStats, GradeEnum
from app.core.security import get_password_hash, create_access_token

router = APIRouter(prefix="/auth", tags=["Аутентификация"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """
    Регистрация нового пользователя
    
    - **username**: Имя пользователя (3-50 символов)
    - **email**: Email адрес
    - **password**: Пароль (минимум 8 символов)
    
    Возвращает токен доступа и профиль пользователя
    """
    # TODO: Реализовать сохранение в БД
    # Пока возвращаем mock-данные
    
    # Проверяем "существование" пользователя (заглушка)
    existing_users = ["admin", "test"]  # Пример существующих пользователей
    if user_data.username in existing_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким именем уже существует"
        )
    
    # Создаём новый профиль
    user_profile = UserProfile(
        id=f"user_{datetime.utcnow().timestamp()}",
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
    
    # Создаём access токен
    access_token = create_access_token(data={"sub": user_profile.id})
    
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
    # TODO: Реализовать проверку пароля из БД
    # Пока возвращаем mock-данные для демонстрации
    
    # Mock-проверка (в реальности нужно получать из БД)
    mock_users = {
        "novice_dev": {
            "password": "password123",
            "profile": UserProfile(
                id="user_123456",
                username="novice_dev",
                email="novice@example.com",
                level=1,
                grade=GradeEnum.novice,
                xp=0,
                xp_to_next=100,
                stats=UserStats(int=10, dex=10, cha=10),
                badges=[]
            )
        }
    }
    
    if credentials.username not in mock_users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_data = mock_users[credentials.username]
    
    # В реальности здесь будет verify_password()
    if credentials.password != user_data["password"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Создаём access токен
    access_token = create_access_token(data={"sub": user_data["profile"].id})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_data["profile"]
    )


@router.post("/logout")
async def logout():
    """
    Выход из системы
    
    В будущем здесь будет добавление токена в blacklist
    """
    # TODO: Реализовать blacklist токенов в Redis
    return {"message": "Успешный выход"}
'@

$authPath = Join-Path $APP_DIR "api\v1\endpoints\auth.py"
$authPy | Out-File -FilePath $authPath -Encoding UTF8 -Force
Write-Host "  + app/api/v1/endpoints/auth.py" -ForegroundColor Green

# ============================================
# api/v1/endpoints/users.py
# ============================================
$usersPy = @'
"""
Endpoints для работы с пользователями
Получение профиля, обновление, список
"""

from fastapi import APIRouter, HTTPException, status
from typing import List
from datetime import datetime

from app.models.user import UserProfile, UserStats, GradeEnum, UserBadge

router = APIRouter(prefix="/users", tags=["Пользователи"])


# Mock-база данных пользователей (в реальности будет PostgreSQL)
MOCK_USERS = {
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
    if user_id not in MOCK_USERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )
    
    return MOCK_USERS[user_id]


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с ID {user_id} не найден"
        )
    
    return MOCK_USERS[user_id].stats
'@

$usersPath = Join-Path $APP_DIR "api\v1\endpoints\users.py"
$usersPy | Out-File -FilePath $usersPath -Encoding UTF8 -Force
Write-Host "  + app/api/v1/endpoints/users.py" -ForegroundColor Green

# ============================================
# api/v1/api.py
# ============================================
$apiPy = @'
"""
Основной роутер API v1
Подключает все endpoints
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users

# Создаём главный роутер для версии API v1
api_router = APIRouter()

# Подключаем endpoints
api_router.include_router(auth.router)
api_router.include_router(users.router)
'@

$apiPath = Join-Path $APP_DIR "api\v1\api.py"
$apiPy | Out-File -FilePath $apiPath -Encoding UTF8 -Force
Write-Host "  + app/api/v1/api.py" -ForegroundColor Green

# ============================================
# api/__init__.py
# ============================================
$apiInit = @'
# API package
'@

$apiInitPath = Join-Path $APP_DIR "api\__init__.py"
$apiInit | Out-File -FilePath $apiInitPath -Encoding UTF8 -Force
Write-Host "  + app/api/__init__.py" -ForegroundColor Green

# ============================================
# core/__init__.py
# ============================================
$coreInit = @'
from app.core.config import settings
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token

__all__ = [
    "settings",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "decode_access_token"
]
'@

$coreInitPath = Join-Path $APP_DIR "core\__init__.py"
$coreInit | Out-File -FilePath $coreInitPath -Encoding UTF8 -Force
Write-Host "  + app/core/__init__.py" -ForegroundColor Green

# ============================================
# app/__init__.py
# ============================================
$appInit = @'
# QuestionWork Backend Application
'@

$appInitPath = Join-Path $APP_DIR "__init__.py"
$appInit | Out-File -FilePath $appInitPath -Encoding UTF8 -Force
Write-Host "  + app/__init__.py" -ForegroundColor Green

Write-Host "`n[5/6] Создание run.ps1 скрипта..." -ForegroundColor Yellow

$runScript = @'
# QuestionWork Backend Run Script
# Запуск FastAPI сервера

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Backend Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$BACKEND_ROOT = Split-Path -Parent $PSScriptRoot

Set-Location $BACKEND_ROOT

# Проверяем наличие venv
if (-not (Test-Path ".venv")) {
    Write-Host "`nОшибка: Виртуальное окружение не найдено!" -ForegroundColor Red
    Write-Host "Запустите сначала: .\scripts\setup.ps1" -ForegroundColor Yellow
    exit 1
}

# Активируем виртуальное окружение
Write-Host "`nАктивация виртуального окружения..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

Write-Host "Запуск FastAPI сервера..." -ForegroundColor Yellow
Write-Host "Swagger UI: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "ReDoc: http://localhost:8000/redoc" -ForegroundColor Green
Write-Host "`nНажми Ctrl+C для остановки`n" -ForegroundColor Gray

# Запускаем uvicorn
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
'@

$runScriptPath = Join-Path $BACKEND_ROOT "scripts\run.ps1"
$runScript | Out-File -FilePath $runScriptPath -Encoding UTF8 -Force
Write-Host "  + scripts/run.ps1" -ForegroundColor Green

Write-Host "`n[6/6] Создание виртуального окружения Python..." -ForegroundColor Yellow

Set-Location $BACKEND_ROOT

# Создаём venv
if (Test-Path ".venv") {
    Write-Host "  Виртуальное окружение уже существует" -ForegroundColor Green
} else {
    Write-Host "  Создание .venv..." -ForegroundColor Yellow
    python -m venv .venv
}

# Активируем и устанавливаем зависимости
Write-Host "  Активация и установка зависимостей..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"
pip install -r requirements.txt

Write-Host "`n✅ Настройка завершена!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n📋 Для запуска проекта:" -ForegroundColor Green
Write-Host "   1. Убедись что PostgreSQL и Redis запущены" -ForegroundColor White
Write-Host "   2. Перейди в C:\QuestionWork\backend" -ForegroundColor White
Write-Host "   3. Запусти: .\scripts\run.ps1" -ForegroundColor White
Write-Host "   4. Открой http://localhost:8000/docs" -ForegroundColor White

Write-Host "`n📝 Mock-пользователи для тестирования:" -ForegroundColor Cyan
Write-Host "   ID: user_123456 (novice_dev) - Lv.1 Novice" -ForegroundColor White
Write-Host "   ID: user_789012 (junior_coder) - Lv.5 Junior" -ForegroundColor White
Write-Host "   ID: user_345678 (middle_master) - Lv.15 Middle" -ForegroundColor White

Write-Host "`n========================================" -ForegroundColor Cyan
