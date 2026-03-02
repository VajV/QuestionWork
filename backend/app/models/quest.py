"""
Pydantic модели для квестов (заказов)
Используются для валидации данных и документации API
"""

from pydantic import BaseModel, Field, field_validator
from typing import Annotated, Literal, Optional, List
from datetime import datetime, timezone
from enum import Enum
from app.models.user import GradeEnum


class QuestStatusEnum(str, Enum):
    """Статусы квеста"""
    open = "open"  # Открыт, принимает отклики
    in_progress = "in_progress"  # В работе
    completed = "completed"  # Завершён
    cancelled = "cancelled"  # Отменён


class Quest(BaseModel):
    """
    Модель квеста (заказа)
    
    Это основной объект биржи — заказ от клиента,
    который может выполнить фрилансер
    """
    id: str = Field(..., description="Уникальный ID квеста")
    
    # Информация о клиенте
    client_id: str = Field(..., description="ID клиента, создавшего квест")
    client_username: Optional[str] = Field(None, description="Имя клиента (для отображения)")
    
    # Описание квеста
    title: str = Field(..., description="Заголовок квеста", min_length=5, max_length=200)
    description: str = Field(..., description="Подробное описание задачи", min_length=20, max_length=5000)
    
    # Требования
    required_grade: GradeEnum = Field(default=GradeEnum.novice, description="Минимальный требуемый грейд")
    skills: List[str] = Field(default_factory=list, description="Требуемые навыки (Python, Figma, etc)")
    
    # Бюджет и награда
    budget: float = Field(..., description="Бюджет квеста", ge=0)
    currency: str = Field(default="RUB", description="Валюта (RUB, USD, EUR)")
    xp_reward: int = Field(..., description="Награда в XP", ge=0)
    
    # Статус и исполнители
    status: QuestStatusEnum = Field(default=QuestStatusEnum.open, description="Статус квеста")
    applications: List[str] = Field(default_factory=list, description="ID откликнувшихся фрилансеров")
    assigned_to: Optional[str] = Field(None, description="ID исполнителя (если выбран)")
    
    # Метаданные
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(None, description="Дата завершения")
    
    class Config:
        use_enum_values = True


class QuestCreate(BaseModel):
    """
    Модель для создания квеста
    
    Содержит только поля, которые клиент может указать при создании
    """
    title: str = Field(..., description="Заголовок квеста", min_length=5, max_length=200)
    description: str = Field(..., description="Подробное описание задачи", min_length=20, max_length=5000)
    required_grade: GradeEnum = Field(default=GradeEnum.novice, description="Минимальный требуемый грейд")
    skills: List[str] = Field(default_factory=list, description="Требуемые навыки (max 20)")
    budget: float = Field(..., description="Бюджет квеста", ge=100, le=1_000_000)
    currency: Literal["USD", "EUR", "RUB"] = Field(default="RUB", description="Валюта (USD, EUR, RUB)")
    xp_reward: Optional[int] = Field(None, description="Награда в XP (авто-расчёт если не указан)")

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: list) -> list:
        if len(v) > 20:
            raise ValueError("skills list must contain at most 20 items")
        for item in v:
            if len(item) > 50:
                raise ValueError(f"each skill must be at most 50 characters, got: {item[:20]!r}...")
        return v


class QuestUpdate(BaseModel):
    """
    Модель для обновления квеста
    
    Разрешает обновлять только определённые поля
    """
    title: Optional[str] = Field(None, description="Заголовок квеста", min_length=5, max_length=200)
    description: Optional[str] = Field(None, description="Подробное описание задачи", min_length=20, max_length=5000)
    required_grade: Optional[GradeEnum] = Field(None, description="Минимальный требуемый грейд")
    skills: Optional[List[str]] = Field(None, description="Требуемые навыки")
    budget: Optional[float] = Field(None, description="Бюджет квеста", ge=0, le=1_000_000)
    xp_reward: Optional[int] = Field(None, description="Награда в XP")


class QuestApplication(BaseModel):
    """
    Отклик на квест от фрилансера
    """
    id: str = Field(..., description="Уникальный ID отклика")
    quest_id: str = Field(..., description="ID квеста")
    freelancer_id: str = Field(..., description="ID фрилансера")
    freelancer_username: str = Field(..., description="Имя фрилансера")
    freelancer_grade: GradeEnum = Field(..., description="Грейд фрилансера")
    cover_letter: Optional[str] = Field(None, description="Сопроводительное письмо", max_length=1000)
    proposed_price: Optional[float] = Field(None, description="Предлагаемая цена")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        use_enum_values = True


class QuestApplicationCreate(BaseModel):
    """
    Модель для создания отклика
    """
    cover_letter: Optional[str] = Field(None, description="Сопроводительное письмо (10-1000 символов)", min_length=10, max_length=1000)
    proposed_price: Optional[float] = Field(None, description="Предлагаемая цена", ge=0)


class QuestListResponse(BaseModel):
    """
    Ответ со списком квестов (пагинация)
    """
    quests: List[Quest]
    total: int
    page: int
    page_size: int
    has_more: bool
