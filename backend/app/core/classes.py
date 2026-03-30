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

from app.core.config import settings

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────
# Class identifiers
# ────────────────────────────────────────────

class ClassId(str, Enum):
    """All registered character classes."""
    berserk = "berserk"
    rogue = "rogue"
    alchemist = "alchemist"
    paladin = "paladin"
    archmage = "archmage"
    oracle = "oracle"


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
    first_apply_bonus = "first_apply_bonus"
    exclusive_blocked = "exclusive_blocked"
    stale_bonus = "stale_bonus"
    urgent_penalty = "urgent_penalty"
    ontime_bonus = "ontime_bonus"
    five_star_bonus = "five_star_bonus"
    anonymous_blocked = "anonymous_blocked"
    high_budget_bonus = "high_budget_bonus"
    normal_budget_penalty = "normal_budget_penalty"
    urgent_blocked = "urgent_blocked"
    analytics_bonus = "analytics_bonus"
    creative_penalty = "creative_penalty"


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
# Rogue
# ────────────────────────────────────────────

ROGUE_PERKS: list[PerkConfig] = [
    PerkConfig(
        id="rogue_quick_draw",
        name="Quick Draw",
        name_ru="Быстрый старт",
        description_ru="Первый отклик на квест даёт ещё +10% XP.",
        icon="🏹",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"first_apply_bonus_extra": 0.10, "quick_draw_bonus": 0.10},
    ),
    PerkConfig(
        id="rogue_shadow_step",
        name="Shadow Step",
        name_ru="Шаг в тени",
        description_ru="Позволяет работать быстрее и снижает цену ошибки на скоростных контрактах.",
        icon="🌑",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"speed_task_bonus": 0.10, "shadow_step_bonus": 0.10},
    ),
    PerkConfig(
        id="rogue_smoke_screen",
        name="Smoke Screen",
        name_ru="Дымовая завеса",
        description_ru="Даёт небольшой шанс ускользнуть от конкуренции на открытых заданиях.",
        icon="💨",
        tier=2,
        required_class_level=4,
        perk_point_cost=2,
        prerequisite_ids=["rogue_quick_draw"],
        effects={"competition_evasion": 0.05},
    ),
    PerkConfig(
        id="rogue_black_market",
        name="Black Market",
        name_ru="Чёрный рынок",
        description_ru="Добавляет +1 слот активных миссий для быстрых цепочек.",
        icon="🗡️",
        tier=2,
        required_class_level=5,
        perk_point_cost=2,
        prerequisite_ids=["rogue_shadow_step"],
        effects={"extra_quest_slot_bonus": 1},
    ),
    PerkConfig(
        id="rogue_phantom",
        name="Phantom",
        name_ru="Фантом",
        description_ru="Элитный стиль: ещё +10% XP за первые отклики и гибкость на сериях быстрых заказов.",
        icon="👤",
        tier=3,
        required_class_level=7,
        perk_point_cost=3,
        prerequisite_ids=["rogue_quick_draw", "rogue_shadow_step"],
        effects={"first_apply_bonus_extra": 0.10, "chain_bonus": 0.10, "phantom_bonus": 0.10},
    ),
]

ROGUE_VANISH = AbilityConfig(
    id="vanish",
    name="Vanish",
    name_ru="Исчезновение",
    description_ru="На 3 часа усиливает скрытность: +35% XP за быстрые захваты и мгновенный вход в поток.",
    icon="🫥",
    required_class_level=5,
    cooldown_hours=48,
    duration_hours=3,
    effects={"xp_all_bonus": 0.35, "urgent_payout_bonus": 0.10},
)

ROGUE_CONFIG = ClassConfig(
    id=ClassId.rogue,
    name="Rogue",
    name_ru="Роуг",
    icon="🗡️",
    color="#7c3aed",
    description="Fast opportunist who thrives on first contact and flexible execution.",
    description_ru="Специалист по первым откликам и захвату быстрых возможностей раньше остальных.",
    min_unlock_level=5,
    passive_bonuses={
        BonusType.first_apply_bonus: 0.20,
        BonusType.extra_quest_slot: 1,
    },
    weaknesses={
        BonusType.exclusive_blocked: True,
    },
    stat_bias={"int": 0, "dex": 2, "cha": 1},
    perks=ROGUE_PERKS,
    abilities=[ROGUE_VANISH],
    perk_points_per_level=1,
)


# ────────────────────────────────────────────
# Alchemist
# ────────────────────────────────────────────

ALCHEMIST_PERKS: list[PerkConfig] = [
    PerkConfig(
        id="alchemist_catalyst",
        name="Catalyst",
        name_ru="Катализатор",
        description_ru="Застоявшиеся квесты приносят ещё +10% XP.",
        icon="⚗️",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"stale_bonus_extra": 0.10, "catalyst_bonus": 0.10},
    ),
    PerkConfig(
        id="alchemist_transmute",
        name="Transmute",
        name_ru="Трансмутация",
        description_ru="Улучшает эффективность переработки сложных и недооценённых задач.",
        icon="🧪",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"conversion_efficiency": 0.10, "transmute_bonus": 0.10},
    ),
    PerkConfig(
        id="alchemist_stabilizer",
        name="Stabilizer",
        name_ru="Стабилизатор",
        description_ru="Снижает штраф за срочные задания на 5%.",
        icon="🧷",
        tier=2,
        required_class_level=4,
        perk_point_cost=2,
        prerequisite_ids=["alchemist_catalyst"],
        effects={"urgent_penalty_reduction": 0.05},
    ),
    PerkConfig(
        id="alchemist_gold_touch",
        name="Gold Touch",
        name_ru="Золотое прикосновение",
        description_ru="Повышает доходность длинных контрактов и добавляет +1 слот работы.",
        icon="🪙",
        tier=2,
        required_class_level=5,
        perk_point_cost=2,
        prerequisite_ids=["alchemist_transmute"],
        effects={"extra_quest_slot_bonus": 1},
    ),
    PerkConfig(
        id="alchemist_philosophers_stone",
        name="Philosopher's Stone",
        name_ru="Философский камень",
        description_ru="Мастерство трансформации: ещё +15% XP за застойные квесты.",
        icon="💎",
        tier=3,
        required_class_level=7,
        perk_point_cost=3,
        prerequisite_ids=["alchemist_catalyst", "alchemist_transmute"],
        effects={"stale_bonus_extra": 0.15, "philosophers_stone_bonus": 0.15},
    ),
]

ALCHEMIST_TRANSMUTATION = AbilityConfig(
    id="transmutation",
    name="Transmutation",
    name_ru="Великая трансмутация",
    description_ru="На 4 часа усиливает переработку сложных задач: +30% XP и устойчивость к потерям эффективности.",
    icon="🔬",
    required_class_level=6,
    cooldown_hours=60,
    duration_hours=4,
    effects={"xp_all_bonus": 0.30, "deadline_penalty_reduce": 0.10},
)

ALCHEMIST_CONFIG = ClassConfig(
    id=ClassId.alchemist,
    name="Alchemist",
    name_ru="Алхимик",
    icon="⚗️",
    color="#14b8a6",
    description="Transforms stale and ignored work into high-value outcomes.",
    description_ru="Эксперт по задачам, которые залежались на доске: превращает их в чистую выгоду.",
    min_unlock_level=6,
    passive_bonuses={
        BonusType.stale_bonus: 0.20,
    },
    weaknesses={
        BonusType.urgent_penalty: -0.20,
    },
    stat_bias={"int": 2, "dex": 1, "cha": 0},
    perks=ALCHEMIST_PERKS,
    abilities=[ALCHEMIST_TRANSMUTATION],
    perk_points_per_level=1,
)


# ────────────────────────────────────────────
# Paladin
# ────────────────────────────────────────────

PALADIN_PERKS: list[PerkConfig] = [
    PerkConfig(
        id="paladin_oath",
        name="Oath",
        name_ru="Клятва",
        description_ru="Своевременно завершённые квесты дают ещё +10% XP.",
        icon="📜",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"ontime_bonus_extra": 0.10, "oath_bonus": 0.10},
    ),
    PerkConfig(
        id="paladin_bulwark",
        name="Bulwark",
        name_ru="Бастион",
        description_ru="Укрепляет репутацию: +10% XP за пятизвёздочные результаты.",
        icon="🛡️",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"five_star_bonus_extra": 0.10, "bulwark_bonus": 0.10},
    ),
    PerkConfig(
        id="paladin_sanctuary",
        name="Sanctuary",
        name_ru="Святилище",
        description_ru="Даёт устойчивость на длинных публичных контрактах.",
        icon="⛪",
        tier=2,
        required_class_level=4,
        perk_point_cost=2,
        prerequisite_ids=["paladin_oath"],
        effects={"stability_bonus": 0.10},
    ),
    PerkConfig(
        id="paladin_blessed_hands",
        name="Blessed Hands",
        name_ru="Благословенные руки",
        description_ru="Немного повышает шанс получить отличный рейтинг и лояльность клиента.",
        icon="✨",
        tier=2,
        required_class_level=5,
        perk_point_cost=2,
        prerequisite_ids=["paladin_bulwark"],
        effects={"reputation_bonus": 0.10},
    ),
    PerkConfig(
        id="paladin_champion",
        name="Champion",
        name_ru="Чемпион",
        description_ru="Максимум доблести: ещё +10% XP за срок и ещё +10% за пять звёзд.",
        icon="👑",
        tier=3,
        required_class_level=7,
        perk_point_cost=3,
        prerequisite_ids=["paladin_oath", "paladin_bulwark"],
        effects={"ontime_bonus_extra": 0.10, "five_star_bonus_extra": 0.10, "champion_bonus": 0.20},
    ),
]

PALADIN_DIVINE_PROTECTION = AbilityConfig(
    id="divine_protection",
    name="Divine Protection",
    name_ru="Божественная защита",
    description_ru="На 4 часа усиливает надёжность: +25% XP за качественное и своевременное завершение.",
    icon="🕯️",
    required_class_level=6,
    cooldown_hours=72,
    duration_hours=4,
    effects={"xp_all_bonus": 0.25, "cancel_xp_protect": True},
)

PALADIN_CONFIG = ClassConfig(
    id=ClassId.paladin,
    name="Paladin",
    name_ru="Паладин",
    icon="🛡️",
    color="#f59e0b",
    description="A disciplined finisher who shines through trust, punctuality and flawless delivery.",
    description_ru="Оплот надёжности: любит чёткие сроки, честные правила и идеальные отзывы.",
    min_unlock_level=7,
    passive_bonuses={
        BonusType.ontime_bonus: 0.15,
        BonusType.five_star_bonus: 0.15,
    },
    weaknesses={
        BonusType.anonymous_blocked: True,
    },
    stat_bias={"int": 0, "dex": 1, "cha": 2},
    perks=PALADIN_PERKS,
    abilities=[PALADIN_DIVINE_PROTECTION],
    perk_points_per_level=1,
)


# ────────────────────────────────────────────
# Archmage
# ────────────────────────────────────────────

ARCHMAGE_PERKS: list[PerkConfig] = [
    PerkConfig(
        id="archmage_deep_study",
        name="Deep Study",
        name_ru="Глубокое изучение",
        description_ru="Высокобюджетные квесты дают ещё +10% XP.",
        icon="📚",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"high_budget_bonus_extra": 0.10, "deep_study_bonus": 0.10},
    ),
    PerkConfig(
        id="archmage_mana_font",
        name="Mana Font",
        name_ru="Источник маны",
        description_ru="Улучшает стабильность на длинных интеллектуальных задачах.",
        icon="🔷",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"focus_bonus": 0.10},
    ),
    PerkConfig(
        id="archmage_spell_focus",
        name="Spell Focus",
        name_ru="Фокус заклинаний",
        description_ru="Повышает конверсию сложных research-контрактов.",
        icon="🪄",
        tier=2,
        required_class_level=4,
        perk_point_cost=2,
        prerequisite_ids=["archmage_deep_study"],
        effects={"research_bonus": 0.10},
    ),
    PerkConfig(
        id="archmage_rune_mastery",
        name="Rune Mastery",
        name_ru="Мастерство рун",
        description_ru="Даёт +1 слот для комплексных контрактов.",
        icon="🧿",
        tier=2,
        required_class_level=5,
        perk_point_cost=2,
        prerequisite_ids=["archmage_mana_font"],
        effects={"extra_quest_slot_bonus": 1},
    ),
    PerkConfig(
        id="archmage_omniscient",
        name="Omniscient",
        name_ru="Всеведущий",
        description_ru="Элитная концентрация: ещё +15% XP на высокобюджетных задачах.",
        icon="🌌",
        tier=3,
        required_class_level=8,
        perk_point_cost=3,
        prerequisite_ids=["archmage_deep_study", "archmage_mana_font"],
        effects={"high_budget_bonus_extra": 0.15, "omniscient_bonus": 0.15},
    ),
]

ARCHMAGE_ARCANE_SURGE = AbilityConfig(
    id="arcane_surge",
    name="Arcane Surge",
    name_ru="Арканный всплеск",
    description_ru="На 4 часа усиливает интеллектуальный поток: +30% XP на сложных и дорогих заданиях.",
    icon="🔮",
    required_class_level=7,
    cooldown_hours=72,
    duration_hours=4,
    effects={"xp_all_bonus": 0.30, "high_budget_bonus_extra": 0.10, "arcane_surge_bonus": 0.10},
)

ARCHMAGE_CONFIG = ClassConfig(
    id=ClassId.archmage,
    name="Archmage",
    name_ru="Архимаг",
    icon="🧙",
    color="#3b82f6",
    description="Elite strategist for expensive, demanding and research-heavy contracts.",
    description_ru="Мастер сложных и дорогих контрактов, где побеждают анализ и глубина, а не спешка.",
    min_unlock_level=8,
    passive_bonuses={
        BonusType.high_budget_bonus: 0.25,
    },
    weaknesses={
        BonusType.normal_budget_penalty: -0.10,
        BonusType.urgent_blocked: True,
    },
    stat_bias={"int": 2, "dex": 0, "cha": 1},
    perks=ARCHMAGE_PERKS,
    abilities=[ARCHMAGE_ARCANE_SURGE],
    perk_points_per_level=1,
)


# ────────────────────────────────────────────
# Oracle
# ────────────────────────────────────────────

ORACLE_PERKS: list[PerkConfig] = [
    PerkConfig(
        id="oracle_third_eye",
        name="Third Eye",
        name_ru="Третий глаз",
        description_ru="Аналитические задачи дают ещё +10% XP.",
        icon="👁️",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"analytics_bonus_extra": 0.10, "third_eye_bonus": 0.10},
    ),
    PerkConfig(
        id="oracle_prophecy",
        name="Prophecy",
        name_ru="Пророчество",
        description_ru="Даёт лучшее предвидение на data-driven контрактах.",
        icon="📈",
        tier=1,
        required_class_level=2,
        perk_point_cost=1,
        effects={"forecast_bonus": 0.10, "prophecy_bonus": 0.10},
    ),
    PerkConfig(
        id="oracle_pattern_weaving",
        name="Pattern Weaving",
        name_ru="Плетение паттернов",
        description_ru="Повышает качество решений на длинных аналитических циклах.",
        icon="🕸️",
        tier=2,
        required_class_level=4,
        perk_point_cost=2,
        prerequisite_ids=["oracle_third_eye"],
        effects={"pattern_bonus": 0.10},
    ),
    PerkConfig(
        id="oracle_foresight",
        name="Foresight",
        name_ru="Предвидение",
        description_ru="Добавляет +1 слот под long-term аналитические квесты.",
        icon="🧭",
        tier=2,
        required_class_level=5,
        perk_point_cost=2,
        prerequisite_ids=["oracle_prophecy"],
        effects={"extra_quest_slot_bonus": 1},
    ),
    PerkConfig(
        id="oracle_omniscience",
        name="Omniscience",
        name_ru="Омнипознание",
        description_ru="Ещё +15% XP за аналитические задачи высшей сложности.",
        icon="🪐",
        tier=3,
        required_class_level=9,
        perk_point_cost=3,
        prerequisite_ids=["oracle_third_eye", "oracle_prophecy"],
        effects={"analytics_bonus_extra": 0.15, "omniscience_bonus": 0.15},
    ),
]

ORACLE_VISION = AbilityConfig(
    id="vision",
    name="Vision",
    name_ru="Видение",
    description_ru="На 4 часа усиливает аналитический фокус: +30% XP за data-heavy задачи.",
    icon="🔭",
    required_class_level=8,
    cooldown_hours=72,
    duration_hours=4,
    effects={"xp_all_bonus": 0.30, "analytics_bonus_extra": 0.10, "vision_bonus": 0.10},
)

ORACLE_CONFIG = ClassConfig(
    id=ClassId.oracle,
    name="Oracle",
    name_ru="Оракул",
    icon="🔮",
    color="#8b5cf6",
    description="Sees patterns before others and thrives on analytics-first work.",
    description_ru="Читает паттерны рынка раньше остальных и силён в аналитике, а не в креативном хаосе.",
    min_unlock_level=9,
    passive_bonuses={
        BonusType.analytics_bonus: 0.20,
    },
    weaknesses={
        BonusType.creative_penalty: -0.10,
        BonusType.urgent_penalty: -0.15,
    },
    stat_bias={"int": 1, "dex": 0, "cha": 2},
    perks=ORACLE_PERKS,
    abilities=[ORACLE_VISION],
    perk_points_per_level=1,
)


# ────────────────────────────────────────────
# Class registry
# ────────────────────────────────────────────

CLASS_REGISTRY: dict[ClassId, ClassConfig] = {
    ClassId.berserk: BERSERK_CONFIG,
    ClassId.rogue: ROGUE_CONFIG,
    ClassId.alchemist: ALCHEMIST_CONFIG,
    ClassId.paladin: PALADIN_CONFIG,
    ClassId.archmage: ARCHMAGE_CONFIG,
    ClassId.oracle: ORACLE_CONFIG,
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
    *settings.rpg_class_level_thresholds,
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

def _context_flag(context: dict[str, object], *names: str) -> bool:
    for name in names:
        value = context.get(name)
        if isinstance(value, bool):
            return value
    return False


def class_participation_ratio(
    class_id: ClassId | str,
    *,
    is_urgent: bool,
    required_portfolio: bool,
    **context,
) -> float:
    """How much of the base quest XP counts towards class XP.

    Returns:
        1.0 — quest fits the class (urgent for Berserker)
        0.5 — neutral quest
        0.0 — quest contradicts the class (portfolio-required for Berserker)
    """
    # P2-20: normalize raw string to ClassId enum for reliable comparison
    if not isinstance(class_id, ClassId):
        try:
            class_id = ClassId(class_id)
        except ValueError:
            return 0.5

    cfg = get_class_config(class_id)
    if cfg is None:
        return 0.5

    is_high_budget = _context_flag(context, "is_high_budget", "high_budget", "is_highbudget", "highbudget")
    is_ontime = _context_flag(context, "is_ontime", "ontime", "is_on_time", "on_time")
    is_first_apply = _context_flag(context, "is_first_apply", "first_apply", "firstapply")
    is_analytics = _context_flag(context, "is_analytics", "analytics")
    is_stale = _context_flag(context, "is_stale", "stale")
    is_anonymous = _context_flag(context, "is_anonymous", "anonymous")
    is_exclusive = _context_flag(context, "is_exclusive", "exclusive")

    if class_id == ClassId.berserk:
        if required_portfolio and cfg.weaknesses.get(BonusType.portfolio_blocked):
            return 0.0
        if is_urgent:
            return 1.0
        return 0.5

    if class_id == ClassId.rogue:
        if is_exclusive and cfg.weaknesses.get(BonusType.exclusive_blocked):
            return 0.0
        if is_first_apply:
            return 1.0
        return 0.5

    if class_id == ClassId.alchemist:
        if is_stale:
            return 1.0
        if is_urgent:
            return 0.25
        return 0.5

    if class_id == ClassId.paladin:
        if is_anonymous and cfg.weaknesses.get(BonusType.anonymous_blocked):
            return 0.0
        if is_ontime:
            return 1.0
        return 0.5

    if class_id == ClassId.archmage:
        if is_urgent and cfg.weaknesses.get(BonusType.urgent_blocked):
            return 0.0
        if is_high_budget:
            return 1.0
        return 0.5

    if class_id == ClassId.oracle:
        if is_analytics:
            return 1.0
        if is_urgent:
            return 0.25
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
    **context,
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

    is_high_budget = _context_flag(context, "is_high_budget", "high_budget", "is_highbudget", "highbudget")
    is_ontime = _context_flag(context, "is_ontime", "ontime", "is_on_time", "on_time")
    is_five_star = _context_flag(context, "is_five_star", "five_star", "is_fivestar", "fivestar")
    is_first_apply = _context_flag(context, "is_first_apply", "first_apply", "firstapply")
    is_analytics = _context_flag(context, "is_analytics", "analytics")
    is_creative = _context_flag(context, "is_creative", "creative")
    is_stale = _context_flag(context, "is_stale", "stale")

    if is_high_budget:
        multiplier += cfg.passive_bonuses.get(BonusType.high_budget_bonus, 0)
    elif cfg.weaknesses.get(BonusType.normal_budget_penalty):
        multiplier += cfg.weaknesses.get(BonusType.normal_budget_penalty, 0)

    if is_ontime:
        multiplier += cfg.passive_bonuses.get(BonusType.ontime_bonus, 0)

    if is_five_star:
        multiplier += cfg.passive_bonuses.get(BonusType.five_star_bonus, 0)

    if is_first_apply:
        multiplier += cfg.passive_bonuses.get(BonusType.first_apply_bonus, 0)

    if is_analytics:
        multiplier += cfg.passive_bonuses.get(BonusType.analytics_bonus, 0)

    if is_creative:
        multiplier += cfg.weaknesses.get(BonusType.creative_penalty, 0)

    if is_stale:
        multiplier += cfg.passive_bonuses.get(BonusType.stale_bonus, 0)

    if is_urgent and cfg.weaknesses.get(BonusType.urgent_penalty):
        multiplier += cfg.weaknesses.get(BonusType.urgent_penalty, 0)

    return max(0.1, multiplier)  # floor at 10% to prevent zero/negative


def should_block_quest(
    class_id: ClassId | str | None,
    *,
    required_portfolio: bool,
    **context,
) -> bool:
    """Check if this quest should be blocked for the user's class."""
    if class_id is None:
        return False
    cfg = get_class_config(class_id)
    if cfg is None:
        return False

    if required_portfolio and cfg.weaknesses.get(BonusType.portfolio_blocked, False):
        return True

    is_urgent = _context_flag(context, "is_urgent", "urgent")
    is_anonymous = _context_flag(context, "is_anonymous", "anonymous")
    is_exclusive = _context_flag(context, "is_exclusive", "exclusive")

    if is_urgent and cfg.weaknesses.get(BonusType.urgent_blocked, False):
        return True
    if is_anonymous and cfg.weaknesses.get(BonusType.anonymous_blocked, False):
        return True
    if is_exclusive and cfg.weaknesses.get(BonusType.exclusive_blocked, False):
        return True

    return False


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
    all_perks: list[PerkConfig] | None = None,
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
    # P2-21: enforce tier ordering — must own at least one perk of (tier - 1) before buying tier N
    if perk.tier > 1 and all_perks is not None:
        lower_tier_owned = any(
            p.id in owned_perk_ids and p.tier == perk.tier - 1
            for p in all_perks
        )
        if not lower_tier_owned:
            return False, f"Сначала разблокируйте хотя бы один перк уровня {perk.tier - 1}"
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
