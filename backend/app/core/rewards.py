"""
Система расчёта наград за квесты
RPG-геймификация: XP, деньги, достижения
"""

from typing import Tuple
from app.models.user import GradeEnum


# ============================================
# Константы баланса
# ============================================

# Множитель XP от бюджета
XP_PER_BUDGET_RATIO = 0.1  # 10% от бюджета = XP

# Максимальная награда за один квест
MAX_XP_REWARD = 500

# Минимальная награда за квест
MIN_XP_REWARD = 10

# Бонус за сложность (если грейд квеста выше грейда исполнителя)
COMPLEXITY_BONUS_MULTIPLIER = 1.5  # +50% XP

# Порядок грейдов (для сравнения сложности)
GRADE_ORDER = {
    GradeEnum.novice: 1,
    GradeEnum.junior: 2,
    GradeEnum.middle: 3,
    GradeEnum.senior: 4,
}


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
    budget: float,
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
        budget: Бюджет квеста
        quest_grade: Требуемый грейд квеста
        user_grade: Грейд исполнителя
        custom_xp: Кастомная награда (если указана клиентом)
    
    Returns:
        Количество XP для начисления
    """
    # Если указана кастомная награда — используем её
    if custom_xp is not None:
        return max(MIN_XP_REWARD, min(custom_xp, MAX_XP_REWARD))
    
    # Базовый расчёт: 10% от бюджета
    base_xp = int(budget * XP_PER_BUDGET_RATIO)
    
    # Проверка сложности
    quest_level = get_grade_level(quest_grade)
    user_level = get_grade_level(user_grade)
    
    # Если квест требует более высокий грейд → бонус
    if quest_level > user_level:
        base_xp = int(base_xp * COMPLEXITY_BONUS_MULTIPLIER)
    
    # Ограничиваем мин/макс
    final_xp = max(MIN_XP_REWARD, min(base_xp, MAX_XP_REWARD))
    
    return final_xp


def calculate_budget_from_xp(
    desired_xp: int,
    quest_grade: GradeEnum,
    user_grade: GradeEnum
) -> float:
    """
    Обратный расчёт: какой бюджет нужен для желаемого XP
    
    Args:
        desired_xp: Желаемая награда в XP
        quest_grade: Требуемый грейд квеста
        user_grade: Грейд исполнителя
    
    Returns:
        Рекомендуемый бюджет
    """
    # Проверка сложности
    quest_level = get_grade_level(quest_grade)
    user_level = get_grade_level(user_grade)
    
    multiplier = COMPLEXITY_BONUS_MULTIPLIER if quest_level > user_level else 1.0
    
    # Обратная формула: budget = xp / (ratio * multiplier)
    budget = desired_xp / (XP_PER_BUDGET_RATIO * multiplier)
    
    return max(100, budget)  # Минимальный бюджет 100


def calculate_quest_rewards(
    budget: float,
    quest_grade: GradeEnum,
    user_grade: GradeEnum,
    custom_xp: int = None
) -> Tuple[int, float]:
    """
    Полный расчёт наград за квест
    
    Args:
        budget: Бюджет квеста
        quest_grade: Требуемый грейд квеста
        user_grade: Грейд исполнителя
        custom_xp: Кастомная награда (если указана)
    
    Returns:
        Кортеж (xp_reward, money_reward)
    """
    xp_reward = calculate_xp_reward(budget, quest_grade, user_grade, custom_xp)
    
    # Денежная награда = бюджет (вся сумма идёт исполнителю)
    # В будущем здесь будет комиссия биржи
    money_reward = budget
    
    return (xp_reward, money_reward)


# Cumulative XP thresholds for grade promotion (single source of truth)
GRADE_XP_THRESHOLDS = {
    GradeEnum.novice: 500,    # 500 XP → junior
    GradeEnum.junior: 2000,   # 2000 XP → middle
    GradeEnum.middle: 5000,   # 5000 XP → senior
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


def check_level_up(current_xp: int, current_grade: GradeEnum) -> Tuple[bool, GradeEnum, int]:
    """
    Проверка повышения уровня/грейда
    
    Args:
        current_xp: Текущий опыт пользователя
        current_grade: Текущий грейд
    
    Returns:
        Кортеж (level_up_occurred, new_grade, new_level)
    """
    # Текущий уровень (примерный, на основе XP)
    # Формула: level = sqrt(xp / 10) + 1
    estimated_level = int((current_xp / 10) ** 0.5) + 1
    
    # Проверка повышения грейда using single source of truth
    new_grade = current_grade
    level_up = False
    
    threshold = GRADE_XP_THRESHOLDS.get(current_grade)
    if threshold is not None and current_xp >= threshold:
        new_grade = GRADE_PROMOTION[current_grade]
        level_up = True
    
    return (level_up, new_grade, estimated_level)


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
