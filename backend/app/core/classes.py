"""
Class Engine — core definitions for RPG character classes.

Contains:
  - ClassId enum (all known class identifiers)
  - ClassConfig dataclass (full specification of a class)
  - PerkConfig / AbilityConfig — perk tree & active abilities
  - CLASS_REGISTRY — lookup table for all registered classes
  - Bonus/multiplier calculators
  - Class XP progression tables

Design: hardcoded in Python (single source of truth, version-controlled).
Can be migrated to DB later when an admin panel is needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────
# Class identifiers
# ────────────────────────────────────────────

class ClassId(str, Enum):
    """All registered character classes."""
    berserk = "berserk"
    # Future: mage = "mage", rogue = "rogue", ...


# ────────────────────────────────────────────
# Passive bonus keys (typed constants)
# ────────────────────────────────────────────

class BonusType(str, Enum):
    """Keys for passive bonuses and weaknesses."""
    xp_urgent_bonus = "xp_urgent_bonus"           # +X% XP for urgent quests
    extra_quest_slot = "extra_quest_slot"           # +N active quest slots
    skip_confirmation = "skip_confirmation"         # skip quest confirmation step
    urgent_search_priority = "urgent_search_priority"  # boost urgent quests in search
    premium_quality_penalty = "premium_quality_penalty"  # -X% pay for premium quests
    portfolio_blocked = "portfolio_blocked"         # cannot take portfolio-required quests
    burnout_threshold = "burnout_threshold"         # N consecutive quests → burnout debuff
    burnout_xp_penalty = "burnout_xp_penalty"       # -X% XP when burned out
    burnout_duration_hours = "burnout_duration_hours"  # burnout duration


# ────────────────────────────────────────────
# Perk system
# ────────────────────────────────────────────

@dataclass(frozen=True)
class PerkConfig:
    """A single perk node in the class perk tree."""
    id: str                        # unique perk identifier
    name: str
    name_ru: str
    description_ru: str
    icon: str
    tier: int                      # 1-3 (tier 1 = unlocked first)
    required_class_level: int      # minimum class level to unlock
    perk_point_cost: int           # perk points to purchase (default 1)
    prerequisite_ids: list[str] = field(default_factory=list)  # perks that must be owned first
    # Effect — key:value pairs interpreted by the service layer
    effects: dict[str, float | int | bool] = field(default_factory=dict)


# ────────────────────────────────────────────
# Active ability system
# ────────────────────────────────────────────

@dataclass(frozen=True)
class AbilityConfig:
    """An activatable ability (ultimate) for a character class."""
    id: str
    name: str
    name_ru: str
    description_ru: str
    icon: str
    required_class_level: int       # class level to unlock the ability
    cooldown_hours: int             # hours between activations
    duration_hours: int             # how long the ability lasts once activated
    # Effects applied while the ability is active
    effects: dict[str, float | int | bool] = field(default_factory=dict)


# ────────────────────────────────────────────
# Class configuration
# ────────────────────────────────────────────

@dataclass(frozen=True)
class ClassConfig:
    """Complete specification for a character class."""
    id: ClassId
    name: str
    name_ru: str
    icon: str
    color: str                     # CSS color for theming (hex or tailwind key)
    description: str
    description_ru: str
    min_unlock_level: int          # minimum user level to unlock this class
    passive_bonuses: dict[str, float | int | bool]
    weaknesses: dict[str, float | int | bool]
    # stat growth bias: keys are "int", "dex", "cha" – extra points per class level-up
    stat_bias: dict[str, int] = field(default_factory=dict)
    # Phase 2: perk tree & active abilities
    perks: list[PerkConfig] = field(default_factory=list)
    abilities: list[AbilityConfig] = field(default_factory=list)
    # Perk points awarded per class level
    perk_points_per_level: int = 1


# ────────────────────────────────────────────
# Berserker perk tree
# ────────────────────────────────────────────

BERSERK_PERKS: list[PerkConfig] = [
    # ── Tier 1 (class level 2+) ──
    PerkConfig(
        id="berserk_adrenaline",
        name="Adrenaline Rush",
        name_ru="Адреналиновый прилив",
        description_ru="Срочные квесты дают ещё +10% XP (итого +30%).",
        icon="⚡",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"xp_urgent_bonus_extra": 0.10},
    ),
    PerkConfig(
        id="berserk_thick_skin",
        name="Thick Skin",
        name_ru="Толстая кожа",
        description_ru="Порог выгорания увеличен на +2 квеста (7 вместо 5).",
        icon="🛡️",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"burnout_threshold_bonus": 2},
    ),
    PerkConfig(
        id="berserk_battle_cry",
        name="Battle Cry",
        name_ru="Боевой клич",
        description_ru="При отклике на срочный квест — +5% шанс мгновенного назначения.",
        icon="📯",
        tier=1,
        required_class_level=3,
        perk_point_cost=1,
        effects={"instant_assign_chance": 0.05},
    ),
    # ── Tier 2 (class level 4+) ──
    PerkConfig(
        id="berserk_fury",
        name="Focused Fury",
        name_ru="Сфокусированная ярость",
        description_ru="XP за обычные (не срочные) квесты +15% (вместо 0).",
        icon="🔥",
        tier=2,
        required_class_level=4,
        perk_point_cost=2,
        prerequisite_ids=["berserk_adrenaline"],
        effects={"xp_normal_bonus": 0.15},
    ),
    PerkConfig(
        id="berserk_iron_will",
        name="Iron Will",
        name_ru="Железная воля",
        description_ru="Длительность выгорания снижена на 8 часов (16ч вместо 24ч).",
        icon="🧠",
        tier=2,
        required_class_level=5,
        perk_point_cost=2,
        prerequisite_ids=["berserk_thick_skin"],
        effects={"burnout_duration_reduction_hours": 8},
    ),
    # ── Tier 3 (class level 7+) ──
    PerkConfig(
        id="berserk_warlord",
        name="Warlord",
        name_ru="Полководец",
        description_ru="Ещё +1 слот активных квестов (итого +2). Снятие штрафа premium quality.",
        icon="👑",
        tier=3,
        required_class_level=7,
        perk_point_cost=3,
        prerequisite_ids=["berserk_fury", "berserk_iron_will"],
        effects={"extra_quest_slot_bonus": 1, "remove_premium_penalty": True},
    ),
]

# ────────────────────────────────────────────
# Berserker active ability: Rage Mode
# ────────────────────────────────────────────

BERSERK_RAGE_MODE = AbilityConfig(
    id="rage_mode",
    name="Rage Mode",
    name_ru="Режим ярости",
    description_ru=(
        "Активируйте режим ярости на 4 часа: +50% XP за все квесты, "
        "выгорание невозможно, но после окончания — гарантированный "
        "период выгорания 12ч. Перезарядка: 72 часа."
    ),
    icon="💀",
    required_class_level=5,
    cooldown_hours=72,
    duration_hours=4,
    effects={
        "xp_all_bonus": 0.50,         # +50% XP for ALL quests while active
        "burnout_immune": True,         # can't get burnout during rage
        "post_rage_burnout_hours": 12,  # forced burnout after rage ends
    },
)


# ────────────────────────────────────────────
# Berserker class definition
# ────────────────────────────────────────────

BERSERK_CONFIG = ClassConfig(
    id=ClassId.berserk,
    name="Berserker",
    name_ru="Берсерк",
    icon="⚔️",
    color="#dc2626",  # red-600
    description="Speed-focused warrior. Excels at urgent quests, trades quality for velocity.",
    description_ru=(
        "Воин скорости. Получает бонусы за срочные квесты, "
        "но теряет преимущества на заданиях, требующих портфолио и высокого качества."
    ),
    min_unlock_level=5,
    passive_bonuses={
        BonusType.xp_urgent_bonus: 0.20,            # +20% XP for urgent quests
        BonusType.extra_quest_slot: 1,               # +1 active quest slot
        BonusType.skip_confirmation: True,            # instant apply (no confirmation delay)
        BonusType.urgent_search_priority: True,       # urgent quests highlighted
    },
    weaknesses={
        BonusType.premium_quality_penalty: -0.10,     # -10% pay for premium quality quests
        BonusType.portfolio_blocked: True,            # cannot take portfolio-required quests
        BonusType.burnout_threshold: 5,               # burnout after 5 consecutive quests
        BonusType.burnout_xp_penalty: -0.10,          # -10% XP during burnout
        BonusType.burnout_duration_hours: 24,          # burnout lasts 24h
    },
    stat_bias={"dex": 2, "int": 0, "cha": 1},  # Berserker grows DEX faster
    perks=BERSERK_PERKS,
    abilities=[BERSERK_RAGE_MODE],
    perk_points_per_level=1,
)


# ────────────────────────────────────────────
# Class registry
# ────────────────────────────────────────────

CLASS_REGISTRY: dict[ClassId, ClassConfig] = {
    ClassId.berserk: BERSERK_CONFIG,
}


def get_class_config(class_id: str | ClassId) -> Optional[ClassConfig]:
    """Lookup a class config by id string or enum."""
    if isinstance(class_id, str):
        try:
            class_id = ClassId(class_id)
        except ValueError:
            return None
    return CLASS_REGISTRY.get(class_id)


def get_available_classes(user_level: int) -> list[ClassConfig]:
    """Return all classes that the user may unlock (level >= min_unlock_level)."""
    return [c for c in CLASS_REGISTRY.values() if user_level >= c.min_unlock_level]


def get_all_classes() -> list[ClassConfig]:
    """Return all registered classes (regardless of user level)."""
    return list(CLASS_REGISTRY.values())


# ────────────────────────────────────────────
# Class XP progression
# ────────────────────────────────────────────

# Cumulative XP thresholds to reach each class level (1-indexed)
# Level 1 = 0 XP (starting), Level 10 = legend tier
CLASS_LEVEL_THRESHOLDS: list[int] = [
    0,       # Level 1 (start)
    500,     # Level 2
    1_500,   # Level 3
    3_000,   # Level 4
    6_000,   # Level 5
    10_000,  # Level 6
    16_000,  # Level 7
    24_000,  # Level 8
    35_000,  # Level 9
    50_000,  # Level 10 (legend)
]

MAX_CLASS_LEVEL = len(CLASS_LEVEL_THRESHOLDS)


def class_level_from_xp(class_xp: int) -> int:
    """Compute class level from cumulative class XP."""
    level = 1
    for i, threshold in enumerate(CLASS_LEVEL_THRESHOLDS):
        if class_xp >= threshold:
            level = i + 1
        else:
            break
    return min(level, MAX_CLASS_LEVEL)


def class_xp_to_next(class_xp: int, class_level: int) -> int:
    """XP remaining to reach the next class level. 0 if max level."""
    if class_level >= MAX_CLASS_LEVEL:
        return 0
    next_threshold = CLASS_LEVEL_THRESHOLDS[class_level]  # 0-indexed: level N threshold is at index N
    return max(0, next_threshold - class_xp)


# ────────────────────────────────────────────
# Class XP participation ratio
# ────────────────────────────────────────────

def class_participation_ratio(class_id: ClassId, *, is_urgent: bool, required_portfolio: bool) -> float:
    """How much of the base quest XP counts towards class XP.

    Returns:
        1.0 — quest fits the class (urgent for Berserker)
        0.5 — neutral quest
        0.0 — quest contradicts the class (portfolio-required for Berserker)
    """
    cfg = get_class_config(class_id)
    if cfg is None:
        return 0.5

    if class_id == ClassId.berserk:
        if required_portfolio and cfg.weaknesses.get(BonusType.portfolio_blocked):
            return 0.0
        if is_urgent:
            return 1.0
        return 0.5

    # Default for unknown classes
    return 0.5


# ────────────────────────────────────────────
# Bonus calculator
# ────────────────────────────────────────────

def calculate_class_xp_multiplier(
    class_id: ClassId | str | None,
    *,
    is_urgent: bool = False,
    is_burnout: bool = False,
) -> float:
    """Calculate XP multiplier from class passive bonuses.

    Returns a multiplier to apply to base XP (e.g. 1.2 for +20%).
    """
    if class_id is None:
        return 1.0

    cfg = get_class_config(class_id)
    if cfg is None:
        return 1.0

    multiplier = 1.0

    # Urgent XP boost
    if is_urgent:
        urgent_bonus = cfg.passive_bonuses.get(BonusType.xp_urgent_bonus, 0)
        multiplier += urgent_bonus  # e.g. 1.0 + 0.20 = 1.20

    # Burnout penalty
    if is_burnout:
        penalty = cfg.weaknesses.get(BonusType.burnout_xp_penalty, 0)
        multiplier += penalty  # e.g. 1.20 + (-0.10) = 1.10

    return max(0.1, multiplier)  # floor at 10% to prevent zero/negative


def should_block_quest(class_id: ClassId | str | None, *, required_portfolio: bool) -> bool:
    """Check if this quest should be blocked for the user's class."""
    if class_id is None or not required_portfolio:
        return False
    cfg = get_class_config(class_id)
    if cfg is None:
        return False
    return bool(cfg.weaknesses.get(BonusType.portfolio_blocked, False))


# ────────────────────────────────────────────
# Perk helpers
# ────────────────────────────────────────────

def get_perk_config(class_id: ClassId | str, perk_id: str) -> Optional[PerkConfig]:
    """Lookup a perk by class and perk id."""
    cfg = get_class_config(class_id)
    if cfg is None:
        return None
    for p in cfg.perks:
        if p.id == perk_id:
            return p
    return None


def get_class_perks(class_id: ClassId | str) -> list[PerkConfig]:
    """Return all perks for a class, sorted by tier then level."""
    cfg = get_class_config(class_id)
    if cfg is None:
        return []
    return sorted(cfg.perks, key=lambda p: (p.tier, p.required_class_level))


def calculate_perk_points_available(class_level: int, perk_points_per_level: int = 1) -> int:
    """Total perk points earned at a given class level (earned starting level 2)."""
    if class_level <= 1:
        return 0
    return (class_level - 1) * perk_points_per_level


def can_unlock_perk(
    perk: PerkConfig,
    class_level: int,
    owned_perk_ids: set[str],
    available_points: int,
) -> tuple[bool, str]:
    """Check if a perk can be unlocked; returns (ok, reason)."""
    if perk.id in owned_perk_ids:
        return False, "Перк уже разблокирован"
    if class_level < perk.required_class_level:
        return False, f"Требуется уровень класса {perk.required_class_level}"
    if available_points < perk.perk_point_cost:
        return False, f"Нужно {perk.perk_point_cost} очков перков, доступно {available_points}"
    for prereq in perk.prerequisite_ids:
        if prereq not in owned_perk_ids:
            return False, f"Сначала разблокируйте перк: {prereq}"
    return True, "ok"


# ────────────────────────────────────────────
# Ability helpers
# ────────────────────────────────────────────

def get_ability_config(class_id: ClassId | str, ability_id: str) -> Optional[AbilityConfig]:
    """Lookup an ability by class and ability id."""
    cfg = get_class_config(class_id)
    if cfg is None:
        return None
    for a in cfg.abilities:
        if a.id == ability_id:
            return a
    return None


def get_class_abilities(class_id: ClassId | str) -> list[AbilityConfig]:
    """Return all abilities for a class."""
    cfg = get_class_config(class_id)
    if cfg is None:
        return []
    return list(cfg.abilities)
