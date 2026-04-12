"""
Pydantic модели для квестов (заказов)
Используются для валидации данных и документации API
"""

from decimal import Decimal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Annotated, Literal, Optional, List
from datetime import datetime, timezone
from enum import Enum
from app.models.user import GradeEnum


class QuestTypeEnum(str, Enum):
    """Тип квеста: обычный (от клиента), тренировочный (PvE) или рейд (кооп)"""
    standard = "standard"  # Обычный квест от клиента
    training = "training"  # PvE тренировочный квест (системный)
    raid = "raid"          # Кооперативный рейд-квест (несколько участников)


class QuestStatusEnum(str, Enum):
    """Статусы квеста"""
    draft = "draft"  # Черновик, виден только владельцу/админу
    open = "open"  # Открыт, принимает отклики
    assigned = "assigned"  # Исполнитель выбран, ожидается старт работы
    in_progress = "in_progress"  # В работе
    completed = "completed"  # Завершён (фрилансер отметил, ждёт подтверждения)
    revision_requested = "revision_requested"  # Клиент запросил доработки
    confirmed = "confirmed"  # Подтверждён клиентом, оплата произведена
    cancelled = "cancelled"  # Отменён


class CurrencyEnum(str, Enum):
    """P1-15: Supported currencies. Prevents arbitrary strings in quest/wallet endpoints."""
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


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
    budget: Decimal = Field(..., description="Бюджет квеста", ge=0)
    currency: str = Field(default="RUB", description="Валюта (RUB, USD, EUR)")
    xp_reward: int = Field(..., description="Награда в XP", ge=0)
    
    # Статус и исполнители
    status: QuestStatusEnum = Field(default=QuestStatusEnum.open, description="Статус квеста")
    applications: List[str] = Field(default_factory=list, description="ID откликнувшихся фрилансеров")
    assigned_to: Optional[str] = Field(None, description="ID исполнителя (если выбран)")
    
    # Тип квеста
    quest_type: str = Field(default="standard", description="Тип квеста: standard, training (PvE) или raid (coop)")

    # Raid-специфичные поля
    raid_max_members: Optional[int] = Field(None, description="Макс. участников рейда (2-8)")
    raid_current_members: int = Field(default=0, description="Текущее количество участников рейда")

    # Chain metadata (set when quest belongs to a legendary chain)
    chain_id: Optional[str] = Field(None, description="ID цепочки квестов (если принадлежит chain)")
    chain_step_order: Optional[int] = Field(None, description="Порядковый номер в цепочке")

    # Метаданные квеста
    is_urgent: bool = Field(default=False, description="Срочный квест (ускоренный дедлайн)")
    deadline: Optional[datetime] = Field(None, description="Дедлайн выполнения")
    required_portfolio: bool = Field(default=False, description="Требуется портфолио")
    delivery_note: Optional[str] = Field(None, description="Комментарий исполнителя при сдаче результата")
    delivery_url: Optional[str] = Field(None, description="Ссылка на результат работы")
    delivery_submitted_at: Optional[datetime] = Field(None, description="Дата отправки результата")
    revision_reason: Optional[str] = Field(None, description="Причина запроса доработок")
    revision_requested_at: Optional[datetime] = Field(None, description="Дата запроса доработок")

    # Снимок комиссии на момент создания квеста
    platform_fee_percent: Optional[Decimal] = Field(None, description="Комиссия платформы %, зафиксированная при создании")

    # Таймстемпы
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(None, description="Дата завершения")
    model_config = ConfigDict(use_enum_values=True)


class QuestCreate(BaseModel):
    """
    Модель для создания квеста
    
    Содержит только поля, которые клиент может указать при создании
    """
    title: str = Field(..., description="Заголовок квеста", min_length=5, max_length=200)
    description: str = Field(..., description="Подробное описание задачи", min_length=20, max_length=5000)
    required_grade: GradeEnum = Field(default=GradeEnum.novice, description="Минимальный требуемый грейд")
    skills: List[str] = Field(default_factory=list, description="Требуемые навыки (max 20)")
    budget: Decimal = Field(..., description="Бюджет квеста", ge=100, le=1_000_000)
    currency: Literal["USD", "EUR", "RUB"] = Field(default="RUB", description="Валюта (USD, EUR, RUB)")
    xp_reward: Optional[int] = Field(None, description="Награда в XP (авто-расчёт если не указан)", ge=10, le=500)
    status: Literal["draft", "open"] = Field(default="open", description="Черновик или публикация сразу")
    is_urgent: bool = Field(default=False, description="Срочный квест")
    deadline: Optional[datetime] = Field(None, description="Дедлайн выполнения")
    required_portfolio: bool = Field(default=False, description="Требуется портфолио")

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
    budget: Optional[Decimal] = Field(None, description="Бюджет квеста", ge=100, le=1_000_000)
    xp_reward: Optional[int] = Field(None, description="Награда в XP", ge=10, le=500)


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
    proposed_price: Optional[Decimal] = Field(None, description="Предлагаемая цена")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = ConfigDict(use_enum_values=True)


class QuestApplicationCreate(BaseModel):
    """
    Модель для создания отклика
    """
    cover_letter: Optional[str] = Field(None, description="Сопроводительное письмо (10-1000 символов)", min_length=10, max_length=1000)
    proposed_price: Optional[Decimal] = Field(None, description="Предлагаемая цена", ge=0)


class QuestInviteCreate(BaseModel):
    """Payload for inviting a freelancer to apply to an open quest."""

    freelancer_id: str = Field(..., description="ID фрилансера", min_length=1)


class QuestInviteResponse(BaseModel):
    """Result of sending or reusing a quest invite notification."""

    quest_id: str
    freelancer_id: str
    already_sent: bool = False
    message: str


class QuestCompletionCreate(BaseModel):
    """Данные для сдачи результата по квесту."""
    delivery_note: Optional[str] = Field(
        None,
        description="Краткое описание выполненной работы",
        min_length=10,
        max_length=5000,
    )
    delivery_url: Optional[AnyHttpUrl] = Field(
        None,
        description="Ссылка на репозиторий, архив, макет или иной результат",
    )

    @field_validator("delivery_url")
    @classmethod
    def validate_delivery_url_https(cls, v: Optional[AnyHttpUrl]) -> Optional[AnyHttpUrl]:
        if v is not None and str(v).startswith("http://"):
            raise ValueError("delivery_url must use HTTPS")
        return v

    @model_validator(mode="after")
    def validate_payload(self):
        if not self.delivery_note and not self.delivery_url:
            raise ValueError("Provide delivery_note or delivery_url")
        return self


class QuestRevisionRequest(BaseModel):
    """Данные для запроса доработок по завершённому квесту."""

    revision_reason: str = Field(
        ...,
        description="Что нужно исправить перед подтверждением",
        min_length=10,
        max_length=5000,
    )


class QuestStatusHistoryEntry(BaseModel):
    id: str = Field(..., description="ID записи истории")
    quest_id: str = Field(..., description="ID квеста")
    from_status: Optional[QuestStatusEnum] = Field(None, description="Предыдущий статус")
    to_status: QuestStatusEnum = Field(..., description="Новый статус")
    changed_by: Optional[str] = Field(None, description="ID пользователя, изменившего статус")
    changed_by_username: Optional[str] = Field(None, description="Имя пользователя")
    note: Optional[str] = Field(None, description="Дополнительный комментарий")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_config = ConfigDict(use_enum_values=True)


class TrainingQuestCreate(BaseModel):
    """Payload for creating a PvE training quest.

    Training quests are system-generated, skip the application phase,
    have capped XP rewards, and carry no real money.
    """
    title: str = Field(..., description="Название тренировочного квеста", min_length=5, max_length=200)
    description: str = Field(..., description="Описание задания", min_length=20, max_length=5000)
    required_grade: GradeEnum = Field(default=GradeEnum.novice, description="Минимальный грейд для доступа")
    skills: List[str] = Field(default_factory=list, description="Тренируемые навыки (max 10)")
    xp_reward: int = Field(default=25, description="Фиксированная XP-награда (ограничена TRAINING_MAX_XP)", ge=5, le=150)

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: list) -> list:
        if len(v) > 10:
            raise ValueError("training quest skills list must contain at most 10 items")
        for item in v:
            if len(item) > 50:
                raise ValueError(f"each skill must be at most 50 characters, got: {item[:20]!r}...")
        return v


# ---------------------------------------------------------------------------
# Co-op Raid Quest models
# ---------------------------------------------------------------------------

RAID_ROLE_SLOTS = ["leader", "developer", "designer", "tester", "analyst", "devops", "support", "any"]


class RaidParticipant(BaseModel):
    """A single participant entry in a raid quest."""
    id: str
    quest_id: str
    user_id: str
    username: str
    role_slot: str = Field(description="Role in the raid party")
    joined_at: datetime
    model_config = ConfigDict(use_enum_values=True)


class RaidQuestCreate(BaseModel):
    """Payload for creating a co-op raid quest."""
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=20, max_length=5000)
    required_grade: GradeEnum = Field(default=GradeEnum.novice)
    skills: List[str] = Field(default_factory=list, description="Требуемые навыки (max 20)")
    budget: Decimal = Field(..., ge=100, le=1_000_000, description="Общий бюджет рейда")
    currency: Literal["USD", "EUR", "RUB"] = Field(default="RUB")
    xp_reward: Optional[int] = Field(None, ge=10, le=500, description="XP за квест (авто-расчёт если не указан)")
    raid_max_members: int = Field(..., ge=2, le=8, description="Количество участников рейда")
    role_slots: List[str] = Field(default_factory=list, description="Ролевые слоты (leader, developer, designer, etc.)")

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: list) -> list:
        if len(v) > 20:
            raise ValueError("skills list must contain at most 20 items")
        for item in v:
            if len(item) > 50:
                raise ValueError(f"each skill must be at most 50 characters, got: {item[:20]!r}...")
        return v

    @field_validator("role_slots")
    @classmethod
    def validate_role_slots(cls, v: list) -> list:
        for slot in v:
            if slot not in RAID_ROLE_SLOTS:
                raise ValueError(f"Invalid role slot: {slot!r}. Allowed: {RAID_ROLE_SLOTS}")
        return v


class RaidJoinRequest(BaseModel):
    """Payload for joining a raid quest."""
    role_slot: str = Field(..., description="Desired role in the raid party")

    @field_validator("role_slot")
    @classmethod
    def validate_role_slot(cls, v: str) -> str:
        if v not in RAID_ROLE_SLOTS:
            raise ValueError(f"Invalid role slot: {v!r}. Allowed: {RAID_ROLE_SLOTS}")
        return v


class RaidPartyResponse(BaseModel):
    """Response showing the current raid party state."""
    quest_id: str
    max_members: int
    current_members: int
    open_slots: int
    participants: List[RaidParticipant]
    role_slots: List[str]


class QuestListResponse(BaseModel):
    """
    Ответ со списком квестов (пагинация)
    """
    quests: List[Quest]
    total: int
    page: int
    page_size: int
    has_more: bool


# ---------------------------------------------------------------------------
# Legendary Quest Chain models
# ---------------------------------------------------------------------------

class ChainStatusEnum(str, Enum):
    """Progress status of a user on a quest chain."""
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"


class QuestChain(BaseModel):
    """A multi-step legendary quest chain."""
    id: str
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    total_steps: int = Field(..., ge=2, le=20)
    final_xp_bonus: int = Field(default=0, ge=0, description="Bonus XP awarded on full chain completion")
    final_badge_id: Optional[str] = Field(None, description="Badge awarded on chain completion")
    created_at: datetime
    model_config = ConfigDict(use_enum_values=True)


class ChainStep(BaseModel):
    """One step inside a quest chain, linked to a quest."""
    id: str
    chain_id: str
    quest_id: str
    step_order: int = Field(..., ge=1)
    model_config = ConfigDict(use_enum_values=True)


class UserChainProgress(BaseModel):
    """Tracks a user's progress through a quest chain."""
    id: str
    chain_id: str
    user_id: str
    current_step: int = Field(default=0, ge=0, description="Number of completed steps")
    status: ChainStatusEnum = Field(default=ChainStatusEnum.not_started)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(use_enum_values=True)


class QuestChainCreate(BaseModel):
    """Payload for creating a new quest chain (admin only)."""
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    quest_ids: List[str] = Field(..., min_length=2, max_length=20, description="Ordered quest IDs forming the chain")
    final_xp_bonus: int = Field(default=0, ge=0, le=5000)
    final_badge_id: Optional[str] = None


class ChainDetailResponse(BaseModel):
    """Full chain info with steps and (optionally) user progress."""
    chain: QuestChain
    steps: List[ChainStep]
    quests: List[Quest] = Field(default_factory=list, description="Quests in step order")
    user_progress: Optional[UserChainProgress] = None


class ChainListResponse(BaseModel):
    """Paginated chain list."""
    chains: List[QuestChain]
    total: int
