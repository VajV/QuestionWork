"""
Система расчёта наград за квесты
RPG-геймификация: XP, деньги, достижения

P0-05 FIX: All budget-related arithmetic uses Decimal throughout.
Config values parsed as Decimal at module load.
"""

from decimal import Decimal
from typing import Optional, Tuple, Union
from app.core.config import settings
from app.models.user import GradeEnum, ReputationStats, FactionAlignment


# ============================================
# Константы баланса (parsed as Decimal from string config)
# ============================================

# Множитель XP от бюджета
XP_PER_BUDGET_RATIO = Decimal(settings.RPG_XP_PER_BUDGET_RATIO)

# Максимальная награда за один квест
MAX_XP_REWARD = settings.RPG_MAX_XP_REWARD

# Минимальная награда за квест
MIN_XP_REWARD = settings.RPG_MIN_XP_REWARD

# Бонус за сложность (если грейд квеста выше грейда исполнителя)
COMPLEXITY_BONUS_MULTIPLIER = Decimal(settings.RPG_COMPLEXITY_BONUS_MULTIPLIER)

# Порядок грейдов (для сравнения сложности)
GRADE_ORDER = {
    GradeEnum.novice: 1,
    GradeEnum.junior: 2,
    GradeEnum.middle: 3,
    GradeEnum.senior: 4,
}

# ---------------------------------------------------------------------------
# PvE Training quest reward constraints
# ---------------------------------------------------------------------------
TRAINING_MAX_XP = 150          # Hard cap on XP per training quest
TRAINING_MIN_XP = 5            # Floor XP per training quest
TRAINING_DAILY_XP_CAP = 500    # Max total training XP earnable per day
TRAINING_BUDGET = Decimal("0")  # Training quests carry no real money


def get_grade_level(grade: GradeEnum) -> int:
    """
    Получить числовой уровень грейда

    Args:
        grade: Грейд пользователя

    Returns:
        Числовой уровень (1-4)
    """
    return GRADE_ORDER.get(grade, 1)


def calculate_xp_reward(
    budget: Decimal,
    quest_grade: GradeEnum,
    user_grade: GradeEnum,
    custom_xp: int = None
) -> int:
    """
    Расчёт награды в XP за выполнение квеста

    Логика:
    1. Базовый XP = 10% от бюджета
    2. Если квест сложнее грейда пользователя → бонус 50%
    3. Ограничение: от 10 до 500 XP

    Args:
        budget: Бюджет квеста (Decimal)
        quest_grade: Требуемый грейд квеста
        user_grade: Грейд исполнителя
        custom_xp: Кастомная награда (если указана клиентом)

    Returns:
        Количество XP для начисления
    """
    # Если указана кастомная награда — используем её
    if custom_xp is not None:
        if not isinstance(custom_xp, int):
            raise TypeError(f"custom_xp must be int, got {type(custom_xp).__name__}")
        return max(MIN_XP_REWARD, min(custom_xp, MAX_XP_REWARD))

    # Coerce to Decimal if a raw float/int sneaks through
    if not isinstance(budget, Decimal):
        budget = Decimal(str(budget))

    if budget < 0:
        raise ValueError("budget must be non-negative")

    # Базовый расчёт: 10% от бюджета
    base_xp = int(budget * XP_PER_BUDGET_RATIO)

    # Проверка сложности
    quest_level = get_grade_level(quest_grade)
    user_level = get_grade_level(user_grade)

    # Если квест требует более высокий грейд → бонус
    if quest_level > user_level:
        base_xp = int(Decimal(base_xp) * COMPLEXITY_BONUS_MULTIPLIER)

    # Ограничиваем мин/макс
    final_xp = max(MIN_XP_REWARD, min(base_xp, MAX_XP_REWARD))

    return final_xp


def calculate_budget_from_xp(
    desired_xp: int,
    quest_grade: GradeEnum,
    user_grade: GradeEnum
) -> Decimal:
    """
    Обратный расчёт: какой бюджет нужен для желаемого XP

    Args:
        desired_xp: Желаемая награда в XP
        quest_grade: Требуемый грейд квеста
        user_grade: Грейд исполнителя

    Returns:
        Рекомендуемый бюджет (Decimal)
    """
    # Проверка сложности
    quest_level = get_grade_level(quest_grade)
    user_level = get_grade_level(user_grade)

    multiplier = COMPLEXITY_BONUS_MULTIPLIER if quest_level > user_level else Decimal("1")

    # Обратная формула: budget = xp / (ratio * multiplier)
    budget = Decimal(desired_xp) / (XP_PER_BUDGET_RATIO * multiplier)

    return max(Decimal("100"), budget)


def calculate_quest_rewards(
    budget: Decimal,
    quest_grade: GradeEnum,
    user_grade: GradeEnum,
    custom_xp: int = None
) -> int:
    """
    Расчёт награды в XP за квест.

    Money reward is computed by wallet_service.split_payment() at confirmation
    time (with platform fee deduction), so this function only returns XP.

    Args:
        budget: Бюджет квеста (Decimal)
        quest_grade: Требуемый грейд квеста
        user_grade: Грейд исполнителя
        custom_xp: Кастомная награда (если указана)

    Returns:
        Количество XP для начисления
    """
    xp_reward = calculate_xp_reward(budget, quest_grade, user_grade, custom_xp)
    return xp_reward


# Cumulative XP thresholds for grade promotion (single source of truth)
GRADE_XP_THRESHOLDS = {
    GradeEnum.novice: settings.rpg_grade_xp_thresholds[0],
    GradeEnum.junior: settings.rpg_grade_xp_thresholds[1],
    GradeEnum.middle: settings.rpg_grade_xp_thresholds[2],
}

# Ordered promotion path
GRADE_PROMOTION = {
    GradeEnum.novice: GradeEnum.junior,
    GradeEnum.junior: GradeEnum.middle,
    GradeEnum.middle: GradeEnum.senior,
}


def get_grade_xp_requirements() -> dict:
    """
    Требования к опыту для каждого грейда

    Returns:
        Словарь {grade: {level, xp_to_next}}
        xp_to_next = cumulative XP needed to reach next grade (or 0 for max grade)
    """
    return {
        GradeEnum.novice: {"level": 1, "xp_to_next": GRADE_XP_THRESHOLDS[GradeEnum.novice]},
        GradeEnum.junior: {"level": 5, "xp_to_next": GRADE_XP_THRESHOLDS[GradeEnum.junior]},
        GradeEnum.middle: {"level": 15, "xp_to_next": GRADE_XP_THRESHOLDS[GradeEnum.middle]},
        GradeEnum.senior: {"level": 30, "xp_to_next": 0},
    }


def calculate_xp_to_next(current_xp: int, grade: GradeEnum) -> int:
    """Calculate remaining XP until next grade promotion.

    Returns 0 when already at max grade (senior).
    """
    threshold = GRADE_XP_THRESHOLDS.get(grade)
    if threshold is None:
        return 0  # senior — max grade
    return max(0, threshold - current_xp)


# ============================================
# RPG Reputation Stats
# ============================================

_GRADE_LEVEL_BONUS: dict[str, float] = {
    "novice": 0.0,
    "junior": 0.25,
    "middle": 0.50,
    "senior": 1.0,
}


def compute_reputation_stats(
    *,
    avg_rating: Optional[float] = None,
    completion_rate: Optional[float] = None,
    trust_score: Optional[float] = None,
    confirmed_quest_count: int = 0,
    review_count: int = 0,
    level: int = 1,
    grade: Union[GradeEnum, str] = GradeEnum.novice,
    profile_completeness_percent: int = 0,
) -> ReputationStats:
    """Compute 4 derived RPG reputation stats from existing user signals.

    All stats are 0-100 integers. These are presentation stats only —
    financial and moderation logic continues to use the canonical trust_score.

    Formulas:
      reliability = completion_rate*0.70 + trust_score*0.30  (both normalized 0-1)
      craft       = (avg_rating/5)*0.70 + level_bonus*0.30
      influence   = min(quests/50,1)*0.50 + min(reviews/20,1)*0.30 + min(level/20,1)*0.20
      resolve     = trust_score*0.60 + (completeness/100)*0.40
    """
    def _clamp01(v: float) -> float:
        return max(0.0, min(1.0, v))

    def _to_100(v: float) -> int:
        return round(_clamp01(v) * 100)

    grade_key = grade.value if isinstance(grade, GradeEnum) else str(grade)
    level_bonus = _GRADE_LEVEL_BONUS.get(grade_key, 0.0)

    # Reliability: completion rate + trust score (both 0-1)
    cr = _clamp01((completion_rate or 0.0) / 100.0)   # completion_rate is 0-100%
    ts = _clamp01(trust_score or 0.0)
    reliability = _to_100(cr * 0.70 + ts * 0.30)

    # Craft: normalized avg rating + grade progression
    rating_norm = _clamp01((avg_rating or 0.0) / 5.0)
    craft = _to_100(rating_norm * 0.70 + level_bonus * 0.30)

    # Influence: quest depth + review volume + level
    quest_factor = _clamp01(confirmed_quest_count / 50.0)
    review_factor = _clamp01(review_count / 20.0)
    level_factor = _clamp01(level / 20.0)
    influence = _to_100(quest_factor * 0.50 + review_factor * 0.30 + level_factor * 0.20)

    # Resolve: overall trust + profile completeness
    pc = _clamp01(profile_completeness_percent / 100.0)
    resolve = _to_100(ts * 0.60 + pc * 0.40)

    return ReputationStats(
        reliability=reliability,
        craft=craft,
        influence=influence,
        resolve=resolve,
    )


def check_level_up(current_xp: int, current_grade: GradeEnum) -> Tuple[bool, GradeEnum, int, list]:
    """
    Проверка повышения уровня/грейда

    Args:
        current_xp: Текущий опыт пользователя
        current_grade: Текущий грейд

    Returns:
        Кортеж (level_up_occurred, new_grade, new_level, promoted_through)
        promoted_through is a list of GradeEnum values for each grade crossed.
    """
    # Текущий уровень (примерный, на основе XP)
    # Формула: level = isqrt(xp / 10) + 1
    # P1 R-01 FIX: Cap at 100 to match UserProfile(level: int = Field(ge=1, le=100))
    import math
    estimated_level = min(math.isqrt(max(0, current_xp) // 10) + 1, 100)

    # Проверка повышения грейда — loop until no more promotions
    new_grade = current_grade
    level_up = False
    promoted_through: list = []

    while True:
        threshold = GRADE_XP_THRESHOLDS.get(new_grade)
        if threshold is not None and current_xp >= threshold:
            new_grade = GRADE_PROMOTION[new_grade]
            promoted_through.append(new_grade)
            level_up = True
        else:
            break

    return (level_up, new_grade, estimated_level, promoted_through)


# ────────────────────────────────────────────
# Stat growth on level-up
# ────────────────────────────────────────────

# Points awarded per level-up
STAT_POINTS_PER_LEVEL = 3
# Automatic distribution pattern (INT, DEX, CHA each get +1 per level)
_STAT_AUTO_DIST = {"int": 1, "dex": 1, "cha": 1}


def allocate_stat_points(levels_gained: int = 1) -> dict:
    """Return the stat delta to apply when gaining *levels_gained* levels.

    For MVP, points are distributed automatically: +1 INT, +1 DEX, +1 CHA per level.

    Args:
        levels_gained: How many levels were gained (usually 1).

    Returns:
        Dict with keys ``int``, ``dex``, ``cha``, ``unspent`` (always 0 for auto mode).

    Example::

        >>> allocate_stat_points(1)
        {'int': 1, 'dex': 1, 'cha': 1, 'unspent': 0}
        >>> allocate_stat_points(3)
        {'int': 3, 'dex': 3, 'cha': 3, 'unspent': 0}
    """
    if levels_gained < 0:
        raise ValueError("levels_gained must be ≥ 0")
    return {
        "int": _STAT_AUTO_DIST["int"] * levels_gained,
        "dex": _STAT_AUTO_DIST["dex"] * levels_gained,
        "cha": _STAT_AUTO_DIST["cha"] * levels_gained,
        "unspent": 0,
    }


# ============================================
# RPG Faction Alignment
# ============================================

_FACTION_NAMES: dict[str, str] = {
    "vanguard": "Фракция Авангарда",
    "keepers": "Хранители Потока",
    "artisans": "Дом Ремесленников",
    "none": "Вне фракций",
}

# (min_score_inclusive, rank_label)
_ALIGNMENT_RANK_THRESHOLDS = [
    (75, "legend"),
    (50, "champion"),
    (25, "soldier"),
    (0, "recruit"),
]


def _alignment_rank(score: int) -> str:
    for threshold, rank in _ALIGNMENT_RANK_THRESHOLDS:
        if score >= threshold:
            return rank
    return "recruit"


def compute_user_faction_alignment(
    *,
    confirmed_quest_count: int = 0,
    active_quest_count: int = 0,
    review_count: int = 0,
    avg_rating: Optional[float] = None,
    completion_rate: Optional[float] = None,
    trust_score: Optional[float] = None,
) -> FactionAlignment:
    """Derive faction alignment from existing user activity signals.

    Scoring model (no new DB columns required):
      vanguard  — speed & delivery pressure:
                  active_quest_count * 10 + min(confirmed * 2, 20)
      keepers   — oversight & review volume:
                  review_count * 8 + revision-pressure bonus (15 pts when
                  completion_rate < 70%)
      artisans  — quality finishes:
                  confirmed_quest_count * 5 + (avg_rating / 5) * 30

    Returns 'none' faction when the user has no activity at all.
    """
    vanguard_score = active_quest_count * 10 + min(confirmed_quest_count * 2, 20)
    keepers_score = review_count * 8 + (
        15 if (completion_rate is not None and completion_rate < 70) else 0
    )
    artisans_score = confirmed_quest_count * 5 + int(
        (avg_rating or 0.0) / 5.0 * 30
    )

    scores: dict[str, int] = {
        "vanguard": vanguard_score,
        "keepers": keepers_score,
        "artisans": artisans_score,
    }

    max_score = max(scores.values())
    if max_score == 0:
        return FactionAlignment(
            faction_id="none",
            faction_name=_FACTION_NAMES["none"],
            contribution_score=0,
            rank="recruit",
            alignment_note=(
                "Пользователь ещё не проявил активность "
                "в рамках ни одной фракции."
            ),
        )

    dominant_id = max(scores, key=lambda k: scores[k])
    contribution = min(100, max_score)

    notes: dict[str, str] = {
        "vanguard": (
            "Высокая активность в рейдах — "
            "пользователь держит фронт открытых задач."
        ),
        "keepers": (
            "Высокий вклад в рецензирование и обратную связь — "
            "хранитель качества потока."
        ),
        "artisans": (
            "Сильный трек подтверждённых квестов и высокий рейтинг — "
            "мастер завершения."
        ),
    }

    return FactionAlignment(
        faction_id=dominant_id,
        faction_name=_FACTION_NAMES[dominant_id],
        contribution_score=contribution,
        rank=_alignment_rank(contribution),
        alignment_note=notes[dominant_id],
    )


# ---------------------------------------------------------------------------
# PvE Training quest XP calculation
# ---------------------------------------------------------------------------

def calculate_training_xp_reward(
    base_xp: int,
    quest_grade: GradeEnum,
    user_grade: GradeEnum,
) -> int:
    """Calculate capped XP reward for a PvE training quest.

    Applies complexity bonus when the quest grade exceeds the user grade,
    then clamps the result to [TRAINING_MIN_XP, TRAINING_MAX_XP].
    """
    xp = max(TRAINING_MIN_XP, min(base_xp, TRAINING_MAX_XP))
    quest_level = get_grade_level(quest_grade)
    user_level = get_grade_level(user_grade)
    if quest_level > user_level:
        xp = int(Decimal(xp) * COMPLEXITY_BONUS_MULTIPLIER)
    return max(TRAINING_MIN_XP, min(xp, TRAINING_MAX_XP))
