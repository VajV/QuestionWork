"""
Pydantic модели пользователя
Используются для валидации данных и документации API
"""

from pydantic import BaseModel, Field
from typing import Optional, List
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
    intelligence: int = Field(default=10, description="Интеллект", ge=1, le=100, alias="int")
    dexterity: int = Field(default=10, description="Ловкость", ge=1, le=100, alias="dex")
    charisma: int = Field(default=10, description="Харизма", ge=1, le=100, alias="cha")
    
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
    email: str
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
