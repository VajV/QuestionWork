"""
Class service — business logic for character class selection, progression, and bonuses.

All write operations require an asyncpg connection inside an explicit transaction.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg

from app.core.classes import (
    CLASS_REGISTRY,
    BonusType,
    ClassId,
    class_level_from_xp,
    class_participation_ratio,
    class_xp_to_next,
    get_all_classes,
    get_available_classes,
    get_class_config,
    calculate_class_xp_multiplier,
    should_block_quest,
    # Phase 2: perks & abilities
    get_class_perks,
    get_perk_config,
    calculate_perk_points_available,
    can_unlock_perk,
    get_class_abilities,
    get_ability_config,
)
from app.core.events import ClassLevelUp, event_bus
from app.core.cache import redis_cache, invalidate_cache_scope
from app.models.character_class import (
    CharacterClassInfo,
    ClassBonusInfo,
    ClassListResponse,
    ClassSelectResponse,
    UserClassInfo,
    # Phase 2
    PerkInfo,
    PerkTreeResponse,
    PerkUnlockResponse,
    AbilityInfo,
    AbilityActivateResponse,
)
from app.models.user import UserProfile, UserRoleEnum
from app.services import notification_service

logger = logging.getLogger(__name__)

# Trial duration: 24 hours
TRIAL_DURATION = timedelta(hours=24)
# Class change cooldown: 30 days
CLASS_CHANGE_COOLDOWN = timedelta(days=30)


# ────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────

_BONUS_LABELS: dict[str, str] = {
    BonusType.xp_urgent_bonus: "+{v:.0%} XP за срочные квесты",
    BonusType.extra_quest_slot: "+{v} слот активных квестов",
    BonusType.skip_confirmation: "Мгновенный отклик на квесты",
    BonusType.urgent_search_priority: "Приоритет срочных квестов в поиске",
    BonusType.premium_quality_penalty: "{v:.0%} оплата за Premium Quality",
    BonusType.portfolio_blocked: "Блокировка квестов с портфолио",
    BonusType.burnout_threshold: "Выгорание после {v} квестов подряд",
    BonusType.burnout_xp_penalty: "{v:.0%} XP при выгорании",
    BonusType.burnout_duration_hours: "Выгорание длится {v}ч",
    BonusType.first_apply_bonus: "+{v:.0%} XP за первый отклик",
    BonusType.exclusive_blocked: "Блокировка эксклюзивных квестов",
    BonusType.stale_bonus: "+{v:.0%} XP за залежавшиеся квесты",
    BonusType.urgent_penalty: "{v:.0%} XP на срочных квестах",
    BonusType.ontime_bonus: "+{v:.0%} XP за работу в срок",
    BonusType.five_star_bonus: "+{v:.0%} XP за 5★ результат",
    BonusType.anonymous_blocked: "Блокировка анонимных квестов",
    BonusType.high_budget_bonus: "+{v:.0%} XP за дорогие контракты",
    BonusType.normal_budget_penalty: "{v:.0%} XP на обычных бюджетах",
    BonusType.urgent_blocked: "Блокировка срочных квестов",
    BonusType.analytics_bonus: "+{v:.0%} XP за аналитические задачи",
    BonusType.creative_penalty: "{v:.0%} XP на креативных задачах",
}


def _bonus_info(key: str, value, is_weakness: bool = False) -> ClassBonusInfo:
    template = _BONUS_LABELS.get(key, "{v}")
    try:
        label = template.format(v=value)
    except (ValueError, KeyError):
        label = f"{key}: {value}"
    return ClassBonusInfo(key=key, label=label, value=value, is_weakness=is_weakness)


def _config_to_info(cfg) -> CharacterClassInfo:
    """Convert a ClassConfig to an API-friendly CharacterClassInfo."""
    bonuses = [_bonus_info(k, v) for k, v in cfg.passive_bonuses.items()]
    weaknesses = [_bonus_info(k, v, is_weakness=True) for k, v in cfg.weaknesses.items()]
    return CharacterClassInfo(
        class_id=cfg.id.value,
        name=cfg.name,
        name_ru=cfg.name_ru,
        icon=cfg.icon,
        color=cfg.color,
        description=cfg.description,
        description_ru=cfg.description_ru,
        min_unlock_level=cfg.min_unlock_level,
        bonuses=bonuses,
        weaknesses=weaknesses,
        perk_count=len(cfg.perks),
        ability_count=len(cfg.abilities),
    )


# ────────────────────────────────────────────
# Read operations (no transaction required)
# ────────────────────────────────────────────

def list_classes(user_level: int, current_class: Optional[str] = None) -> ClassListResponse:
    """List classes available at the given user level."""
    available_configs = get_available_classes(user_level)
    classes = [_config_to_info(c) for c in available_configs]
    return ClassListResponse(classes=classes, user_level=user_level, current_class=current_class)


def build_empty_user_class_info() -> UserClassInfo:
    return UserClassInfo(
        has_class=False,
        class_id="",
        name="",
        name_ru="Класс не выбран",
        icon="🜁",
        color="#64748b",
    )


async def _compute_user_class_info(conn: asyncpg.Connection, user_id: str) -> Optional[UserClassInfo]:
    """Load user's current class and progression from DB (un-cached internal helper)."""
    user_row = await conn.fetchrow(
        "SELECT character_class, class_selected_at, class_trial_expires_at FROM users WHERE id = $1",
        user_id,
    )
    if not user_row or not user_row["character_class"]:
        return None

    class_id_str = user_row["character_class"]
    cfg = get_class_config(class_id_str)
    if cfg is None:
        return None

    # Load progression
    progress = await conn.fetchrow(
        "SELECT * FROM user_class_progress WHERE user_id = $1",
        user_id,
    )

    now = datetime.now(timezone.utc)
    trial_expires = user_row["class_trial_expires_at"]
    is_trial = trial_expires is not None and trial_expires > now

    class_xp = progress["class_xp"] if progress else 0
    class_level = progress["class_level"] if progress else 1
    quests_completed = progress["quests_completed"] if progress else 0
    consecutive = progress["consecutive_quests"] if progress else 0
    burnout_until = progress["burnout_until"] if progress else None
    perk_points_spent = progress["perk_points_spent"] if progress else 0
    bonus_perk_points = progress["bonus_perk_points"] if progress else 0
    rage_active_until = progress["rage_active_until"] if progress else None

    is_burnout = burnout_until is not None and burnout_until > now
    perk_points_total = calculate_perk_points_available(class_level, cfg.perk_points_per_level) + bonus_perk_points
    perk_points_available = perk_points_total - perk_points_spent
    rage_active = rage_active_until is not None and rage_active_until > now

    # Load unlocked perk ids
    perk_rows = await conn.fetch(
        "SELECT perk_id FROM user_perks WHERE user_id = $1 AND class_id = $2",
        user_id, class_id_str,
    )
    unlocked_perks = [r["perk_id"] for r in perk_rows]

    bonuses = [_bonus_info(k, v) for k, v in cfg.passive_bonuses.items()]
    weaknesses = [_bonus_info(k, v, is_weakness=True) for k, v in cfg.weaknesses.items()]

    return UserClassInfo(
        has_class=True,
        class_id=cfg.id.value,
        name=cfg.name,
        name_ru=cfg.name_ru,
        icon=cfg.icon,
        color=cfg.color,
        class_level=class_level,
        class_xp=class_xp,
        class_xp_to_next=class_xp_to_next(class_xp, class_level),
        quests_completed_as_class=quests_completed,
        consecutive_quests=consecutive,
        is_trial=is_trial,
        trial_expires_at=trial_expires if is_trial else None,
        active_bonuses=bonuses,
        weaknesses=weaknesses,
        is_burnout=is_burnout,
        burnout_until=burnout_until if is_burnout else None,
        perk_points_total=perk_points_total,
        perk_points_spent=perk_points_spent,
        perk_points_available=perk_points_available,
        bonus_perk_points=bonus_perk_points,
        unlocked_perks=unlocked_perks,
        rage_active=rage_active,
        rage_active_until=rage_active_until if rage_active else None,
    )


@redis_cache(ttl_seconds=180, key_prefix="class_info", scope_builder=lambda conn, user_id: f"user:{user_id}")
async def _cached_class_info_dict(conn: asyncpg.Connection, user_id: str) -> Optional[dict]:
    """Cached dict representation of class info for Redis storage."""
    result = await _compute_user_class_info(conn, user_id)
    if result is None:
        return None
    return result.model_dump(mode="json")


async def get_user_class_info(conn: asyncpg.Connection, user_id: str) -> Optional[UserClassInfo]:
    """Load user's current class and progression, with Redis cache (TTL 180s)."""
    data = await _cached_class_info_dict(conn, user_id)
    if data is None:
        return None
    return UserClassInfo.model_validate(data)


# ────────────────────────────────────────────
# Class selection
# ────────────────────────────────────────────

async def select_class(
    conn: asyncpg.Connection,
    user: UserProfile,
    class_id: str,
    trial: bool = True,
) -> ClassSelectResponse:
    """Select a character class. Starts trial period if trial=True.

    Validations:
      - User must be freelancer
      - User level >= min_unlock_level
      - No active class (or expired trial)
    """
    # Validation
    if user.role != UserRoleEnum.freelancer.value:
        raise PermissionError("Только фрилансеры могут выбирать класс")

    if getattr(user, "is_banned", False):
        raise PermissionError("Заблокированные пользователи не могут выбирать класс")

    cfg = get_class_config(class_id)
    if cfg is None:
        raise ValueError(f"Неизвестный класс: {class_id}")

    if user.level < cfg.min_unlock_level:
        raise ValueError(
            f"Требуется уровень {cfg.min_unlock_level}, ваш уровень: {user.level}"
        )

    # Check existing class
    existing = await conn.fetchrow(
        "SELECT character_class, class_trial_expires_at, class_selected_at FROM users WHERE id = $1 FOR UPDATE",
        user.id,
    )
    now = datetime.now(timezone.utc)

    if existing and existing["character_class"]:
        trial_expires = existing["class_trial_expires_at"]
        # If trial expired, allow re-selection
        if trial_expires and trial_expires > now:
            raise ValueError("У вас уже активен пробный период. Дождитесь окончания или подтвердите выбор.")
        # If class is confirmed (no trial), check cooldown
        if trial_expires is None and existing["class_selected_at"]:
            cooldown_end = existing["class_selected_at"] + CLASS_CHANGE_COOLDOWN
            if now < cooldown_end:
                days_left = (cooldown_end - now).days
                raise ValueError(f"Смена класса доступна через {days_left} дней")

    # Set class
    trial_expires_at = now + TRIAL_DURATION if trial else None

    await conn.execute(
        """
        UPDATE users
        SET character_class = $1, class_selected_at = $2, class_trial_expires_at = $3,
            updated_at = $4
        WHERE id = $5
        """,
        class_id,
        now,
        trial_expires_at,
        now,
        user.id,
    )

    # Upsert class progression
    await conn.execute(
        """
        INSERT INTO user_class_progress (user_id, class_id, class_xp, class_level,
                                          quests_completed, consecutive_quests, updated_at)
        VALUES ($1, $2, 0, 1, 0, 0, $3)
        ON CONFLICT (user_id) DO UPDATE
        SET class_id = $2, class_xp = 0, class_level = 1,
            quests_completed = 0, consecutive_quests = 0,
            burnout_until = NULL, updated_at = $3
        """,
        user.id,
        class_id,
        now,
    )

    # Notification
    await notification_service.create_notification(
        conn,
        user_id=user.id,
        title=f"{cfg.icon} Класс выбран: {cfg.name_ru}!",
        message=(
            f"Вы начали пробный период класса {cfg.name_ru}. "
            f"У вас 24 часа, чтобы оценить бонусы."
        ) if trial else (
            f"Класс {cfg.name_ru} активирован! Ваши бонусы уже работают."
        ),
        event_type="class_selected",
    )

    await invalidate_cache_scope("class_info", "user", user.id)
    class_info = await get_user_class_info(conn, user.id)
    msg = (
        f"Пробный период {cfg.name_ru} начат! 24 часа для тестирования."
        if trial else
        f"Класс {cfg.name_ru} активирован!"
    )
    return ClassSelectResponse(message=msg, class_info=class_info)  # type: ignore[arg-type]


async def confirm_class(conn: asyncpg.Connection, user: UserProfile) -> ClassSelectResponse:
    """Confirm a class after trial period (or before it expires)."""
    row = await conn.fetchrow(
        "SELECT character_class, class_trial_expires_at FROM users WHERE id = $1",
        user.id,
    )
    if not row or not row["character_class"]:
        raise ValueError("У вас нет выбранного класса для подтверждения")

    if row["class_trial_expires_at"] is None:
        raise ValueError("Класс уже подтверждён")

    now = datetime.now(timezone.utc)

    if row["class_trial_expires_at"] < now:
        raise ValueError("Пробный период истёк. Выберите класс заново.")

    # Clear trial — class is now permanent
    await conn.execute(
        "UPDATE users SET class_trial_expires_at = NULL, class_selected_at = $1, updated_at = $2 WHERE id = $3",
        now,
        now,
        user.id,
    )

    cfg = get_class_config(row["character_class"])
    await notification_service.create_notification(
        conn,
        user_id=user.id,
        title=f"{cfg.icon} Класс подтверждён!",
        message=f"Класс {cfg.name_ru} зафиксирован. Удачной охоты!",
        event_type="class_selected",
    )

    await invalidate_cache_scope("class_info", "user", user.id)
    class_info = await get_user_class_info(conn, user.id)
    return ClassSelectResponse(
        message=f"Класс {cfg.name_ru} подтверждён!",
        class_info=class_info,  # type: ignore[arg-type]
    )


async def reset_class(conn: asyncpg.Connection, user: UserProfile) -> dict:
    """Reset user's class. Progression is preserved in user_class_progress but class is cleared."""
    row = await conn.fetchrow(
        "SELECT character_class FROM users WHERE id = $1",
        user.id,
    )
    if not row or not row["character_class"]:
        raise ValueError("У вас нет активного класса")

    now = datetime.now(timezone.utc)
    await conn.execute(
        "UPDATE users SET character_class = NULL, class_selected_at = $1, class_trial_expires_at = NULL, updated_at = $2 WHERE id = $3",
        now,
        now,
        user.id,
    )
    await invalidate_cache_scope("class_info", "user", user.id)
    return {"message": "Класс сброшен. Вы можете выбрать новый класс через 30 дней."}


# ────────────────────────────────────────────
# Class XP & progression (called after quest completion)
# ────────────────────────────────────────────

async def add_class_xp(
    conn: asyncpg.Connection,
    user_id: str,
    base_xp: int,
    *,
    is_urgent: bool = False,
    required_portfolio: bool = False,
) -> dict:
    """Award class XP after a quest completion.

    Returns dict with class progression details.
    Must be called inside an active DB transaction.
    """
    if not conn.is_in_transaction():
        raise RuntimeError("add_class_xp must be called inside a DB transaction")

    user_row = await conn.fetchrow(
        "SELECT character_class FROM users WHERE id = $1",
        user_id,
    )
    if not user_row or not user_row["character_class"]:
        return {"class_xp_gained": 0, "class_level_up": False}

    class_id_str = user_row["character_class"]
    try:
        class_id = ClassId(class_id_str)
    except ValueError:
        return {"class_xp_gained": 0, "class_level_up": False}

    # Calculate class XP gain
    ratio = class_participation_ratio(class_id, is_urgent=is_urgent, required_portfolio=required_portfolio)
    class_xp_gain = int(base_xp * ratio)

    if class_xp_gain <= 0:
        return {"class_xp_gained": 0, "class_level_up": False}

    # ── Phase 2: apply perk XP bonuses and active ability effects ──
    perk_effects = await get_active_perk_effects(conn, user_id, class_id_str)
    ability_effects = await get_active_ability_effects(conn, user_id)
    # rage_active = burnout_immune is active (only Berserk rage_mode sets this)
    rage_active = bool(ability_effects.get("burnout_immune", False))

    perk_multiplier = 1.0
    # Perk: xp_urgent_bonus_extra (only for urgent quests)
    if is_urgent and "xp_urgent_bonus_extra" in perk_effects:
        perk_multiplier += perk_effects["xp_urgent_bonus_extra"]
    # Perk: xp_normal_bonus (for non-urgent quests)
    if not is_urgent and "xp_normal_bonus" in perk_effects:
        perk_multiplier += perk_effects["xp_normal_bonus"]
    # Active abilities: xp_all_bonus (any class — Rage Mode, Arcane Surge, etc.)
    if ability_effects.get("xp_all_bonus", 0):
        perk_multiplier += ability_effects["xp_all_bonus"]

    class_xp_gain = int(class_xp_gain * perk_multiplier)

    now = datetime.now(timezone.utc)

    # Update progression (FOR UPDATE to prevent race on consecutive_quests)
    progress = await conn.fetchrow(
        "SELECT class_xp, class_level, quests_completed, consecutive_quests FROM user_class_progress WHERE user_id = $1 FOR UPDATE",
        user_id,
    )
    if not progress:
        # Auto-create if missing
        await conn.execute(
            "INSERT INTO user_class_progress (user_id, class_id, class_xp, class_level, quests_completed, consecutive_quests, updated_at) VALUES ($1,$2,$3,1,1,1,$4)",
            user_id,
            class_id_str,
            class_xp_gain,
            now,
        )
        return {"class_xp_gained": class_xp_gain, "class_level_up": False, "new_class_level": 1}

    old_level = progress["class_level"]
    new_xp = progress["class_xp"] + class_xp_gain
    new_level = class_level_from_xp(new_xp)
    new_consecutive = progress["consecutive_quests"] + 1
    new_completed = progress["quests_completed"] + 1

    # Check burnout (Phase 2: perks + Rage Mode modify thresholds)
    cfg = get_class_config(class_id)
    burnout_threshold = cfg.weaknesses.get(BonusType.burnout_threshold, 999) if cfg else 999
    # Perk: burnout_threshold_bonus increases the threshold
    burnout_threshold += int(perk_effects.get("burnout_threshold_bonus", 0))
    burnout_until = progress["burnout_until"]

    # Detect if rage mode just expired (rage_active_until in past, not yet cleared)
    rage_just_expired = (
        not rage_active
        and progress["rage_active_until"] is not None
        and progress["rage_active_until"] < now
    )

    # Rage Mode: burnout immune while active
    if rage_active:
        pass  # skip burnout check entirely
    elif rage_just_expired and (burnout_until is None or burnout_until < now):
        # Post-rage burnout: forced burnout after rage expires
        rage_ability = get_ability_config(class_id_str, "rage_mode")
        post_rage_hours = int(rage_ability.effects.get("post_rage_burnout_hours", 12)) if rage_ability else 12
        burnout_until = now + timedelta(hours=post_rage_hours)
        new_consecutive = 0
        logger.info(f"Post-rage burnout for user {user_id}, class {class_id_str}, until {burnout_until}")
    elif new_consecutive >= burnout_threshold and (burnout_until is None or burnout_until < now):
        burnout_hours = cfg.weaknesses.get(BonusType.burnout_duration_hours, 24) if cfg else 24
        # Perk: burnout_duration_reduction_hours reduces duration
        burnout_hours = max(4, int(burnout_hours) - int(perk_effects.get("burnout_duration_reduction_hours", 0)))
        burnout_until = now + timedelta(hours=burnout_hours)
        new_consecutive = 0  # reset counter after burnout triggers
        logger.info(f"Burnout triggered for user {user_id}, class {class_id_str}, until {burnout_until}")

    # Clear rage_active_until once rage has expired so post-rage burnout triggers only once
    new_rage_until = None if rage_just_expired else progress["rage_active_until"]

    await conn.execute(
        """
        UPDATE user_class_progress
        SET class_xp = $1, class_level = $2, quests_completed = $3,
            consecutive_quests = $4, last_quest_at = $5, burnout_until = $6,
            updated_at = $7, rage_active_until = $8
        WHERE user_id = $9
        """,
        new_xp,
        new_level,
        new_completed,
        new_consecutive,
        now,
        burnout_until,
        now,
        new_rage_until,
        user_id,
    )

    level_up = new_level > old_level
    if level_up:
        levels_gained = new_level - old_level
        await event_bus.emit(conn, ClassLevelUp(
            user_id=user_id,
            class_id=class_id_str,
            old_level=old_level,
            new_level=new_level,
        ))
        await notification_service.create_notification(
            conn,
            user_id=user_id,
            title=f"⬆️ Уровень класса {cfg.name_ru}: {new_level}!",
            message=f"Ваш класс {cfg.name_ru} достиг уровня {new_level}.",
            event_type="class_level_up",
        )

        # Phase 2: apply stat_bias on class level-up
        if cfg.stat_bias:
            stat_updates = []
            stat_args = []
            idx = 1
            _VALID_STATS = {"int", "dex", "cha"}
            for stat_key, bonus_per_level in cfg.stat_bias.items():
                if stat_key not in _VALID_STATS:
                    continue
                if bonus_per_level <= 0:
                    continue
                delta = bonus_per_level * levels_gained
                col = f"stats_{stat_key}"  # e.g. stats_dex
                stat_updates.append(f"{col} = LEAST({col} + ${idx}, 100)")  # R-06: cap at 100
                stat_args.append(delta)
                idx += 1
            if stat_updates:
                stat_args.append(now)
                stat_args.append(user_id)
                await conn.execute(
                    f"UPDATE users SET {', '.join(stat_updates)}, updated_at = ${idx} WHERE id = ${idx + 1}",
                    *stat_args,
                )

    await invalidate_cache_scope("class_info", "user", user_id)
    return {
        "class_xp_gained": class_xp_gain,
        "class_level_up": level_up,
        "new_class_level": new_level,
        "new_class_xp": new_xp,
        "consecutive_quests": new_consecutive,
        "is_burnout": burnout_until is not None and burnout_until > now,
    }


async def check_burnout(conn: asyncpg.Connection, user_id: str) -> bool:
    """Check if the user currently has a burnout debuff."""
    progress = await conn.fetchrow(
        "SELECT burnout_until FROM user_class_progress WHERE user_id = $1",
        user_id,
    )
    if not progress or not progress["burnout_until"]:
        return False
    return progress["burnout_until"] > datetime.now(timezone.utc)


async def reset_consecutive_if_stale(conn: asyncpg.Connection, user_id: str) -> None:
    """Reset consecutive quest counter if last quest was over 24h ago.

    Should be called before quest assignment to ensure burnout tracking is fresh.
    """
    progress = await conn.fetchrow(
        "SELECT last_quest_at FROM user_class_progress WHERE user_id = $1",
        user_id,
    )
    if not progress or not progress["last_quest_at"]:
        return

    now = datetime.now(timezone.utc)
    if now - progress["last_quest_at"] > timedelta(hours=24):
        await conn.execute(
            "UPDATE user_class_progress SET consecutive_quests = 0, updated_at = $1 WHERE user_id = $2",
            now,
            user_id,
        )


# ════════════════════════════════════════════
# Phase 2: Perk Tree
# ════════════════════════════════════════════

async def _load_user_class_ctx(
    conn: asyncpg.Connection, user_id: str
) -> tuple[str, int, int, int, set[str]]:
    """Load class context needed by perk/ability functions.

    Returns (class_id_str, class_level, perk_points_spent, bonus_perk_points, owned_perk_ids).
    Raises ValueError if user has no active class.
    """
    row = await conn.fetchrow(
        "SELECT character_class FROM users WHERE id = $1", user_id
    )
    if not row or not row["character_class"]:
        raise ValueError("У вас нет активного класса")

    class_id_str = row["character_class"]
    progress = await conn.fetchrow(
        "SELECT class_level, perk_points_spent, bonus_perk_points FROM user_class_progress WHERE user_id = $1 FOR UPDATE",
        user_id,
    )
    class_level = progress["class_level"] if progress else 1
    perk_points_spent = progress["perk_points_spent"] if progress else 0
    bonus_perk_points = progress["bonus_perk_points"] if progress else 0

    perk_rows = await conn.fetch(
        "SELECT perk_id FROM user_perks WHERE user_id = $1 AND class_id = $2",
        user_id, class_id_str,
    )
    owned_perk_ids = {r["perk_id"] for r in perk_rows}
    return class_id_str, class_level, perk_points_spent, bonus_perk_points, owned_perk_ids


def _perk_to_info(
    perk, *, is_unlocked: bool, can_do: bool, reason: str
) -> PerkInfo:
    """Convert a PerkConfig + status to PerkInfo API model."""
    return PerkInfo(
        perk_id=perk.id,
        name=perk.name,
        name_ru=perk.name_ru,
        description_ru=perk.description_ru,
        icon=perk.icon,
        tier=perk.tier,
        required_class_level=perk.required_class_level,
        perk_point_cost=perk.perk_point_cost,
        prerequisite_ids=list(perk.prerequisite_ids),
        effects=dict(perk.effects),
        is_unlocked=is_unlocked,
        can_unlock=can_do,
        lock_reason=reason if not can_do and not is_unlocked else None,
    )


async def get_user_perk_tree(
    conn: asyncpg.Connection, user_id: str
) -> PerkTreeResponse:
    """Build the full perk tree for the user's current class."""
    class_id_str, class_level, perk_points_spent, bonus_perk_points, owned_ids = (
        await _load_user_class_ctx(conn, user_id)
    )
    cfg = get_class_config(class_id_str)
    if cfg is None:
        raise ValueError("Неизвестный класс")

    total_points = calculate_perk_points_available(class_level, cfg.perk_points_per_level) + bonus_perk_points
    available = total_points - perk_points_spent

    perks: list[PerkInfo] = []
    all_perks = get_class_perks(class_id_str)
    for p in all_perks:
        if p.id in owned_ids:
            perks.append(_perk_to_info(p, is_unlocked=True, can_do=False, reason="ok"))
        else:
            can_do, reason = can_unlock_perk(p, class_level, owned_ids, available, all_perks=all_perks)
            perks.append(_perk_to_info(p, is_unlocked=False, can_do=can_do, reason=reason))

    return PerkTreeResponse(
        class_id=class_id_str,
        perks=perks,
        perk_points_total=total_points,
        perk_points_spent=perk_points_spent,
        perk_points_available=available,
    )


async def unlock_perk(
    conn: asyncpg.Connection, user_id: str, perk_id: str
) -> PerkUnlockResponse:
    """Unlock a perk for the user. Must be called inside a transaction."""
    class_id_str, class_level, perk_points_spent, bonus_perk_points, owned_ids = (
        await _load_user_class_ctx(conn, user_id)
    )
    cfg = get_class_config(class_id_str)
    if cfg is None:
        raise ValueError("Неизвестный класс")

    perk = get_perk_config(class_id_str, perk_id)
    if perk is None:
        raise ValueError(f"Перк не найден: {perk_id}")

    total_points = calculate_perk_points_available(class_level, cfg.perk_points_per_level) + bonus_perk_points
    available = total_points - perk_points_spent

    ok, reason = can_unlock_perk(perk, class_level, owned_ids, available, all_perks=get_class_perks(class_id_str))
    if not ok:
        raise ValueError(reason)

    # Insert perk record
    perk_record_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await conn.execute(
        "INSERT INTO user_perks (id, user_id, perk_id, class_id, unlocked_at) VALUES ($1,$2,$3,$4,$5)",
        perk_record_id, user_id, perk_id, class_id_str, now,
    )

    # Increment spent points
    new_spent = perk_points_spent + perk.perk_point_cost
    await conn.execute(
        "UPDATE user_class_progress SET perk_points_spent = $1, updated_at = $2 WHERE user_id = $3",
        new_spent, now, user_id,
    )

    new_available = total_points - new_spent

    # Notification
    await notification_service.create_notification(
        conn,
        user_id=user_id,
        title=f"{perk.icon} Перк разблокирован: {perk.name_ru}!",
        message=perk.description_ru,
        event_type="perk_unlocked",
    )

    perk_info = _perk_to_info(perk, is_unlocked=True, can_do=False, reason="ok")
    await invalidate_cache_scope("class_info", "user", user_id)
    return PerkUnlockResponse(
        message=f"Перк «{perk.name_ru}» разблокирован!",
        perk=perk_info,
        perk_points_available=new_available,
    )


# ════════════════════════════════════════════
# Phase 2: Active Abilities (Rage Mode etc.)
# ════════════════════════════════════════════

def _ability_to_info(
    ability, *, class_level: int, db_row=None
) -> AbilityInfo:
    """Convert AbilityConfig + optional DB row to AbilityInfo."""
    now = datetime.now(timezone.utc)
    is_unlocked = class_level >= ability.required_class_level
    is_active = False
    active_until = None
    is_on_cooldown = False
    cooldown_until = None
    times_used = 0

    if db_row:
        active_until_val = db_row["active_until"]
        cooldown_until_val = db_row["cooldown_until"]
        times_used = db_row["times_used"] or 0

        if active_until_val and active_until_val > now:
            is_active = True
            active_until = active_until_val
        if cooldown_until_val and cooldown_until_val > now:
            is_on_cooldown = True
            cooldown_until = cooldown_until_val

    return AbilityInfo(
        ability_id=ability.id,
        name=ability.name,
        name_ru=ability.name_ru,
        description_ru=ability.description_ru,
        icon=ability.icon,
        required_class_level=ability.required_class_level,
        cooldown_hours=ability.cooldown_hours,
        duration_hours=ability.duration_hours,
        effects=dict(ability.effects),
        is_unlocked=is_unlocked,
        is_active=is_active,
        active_until=active_until,
        is_on_cooldown=is_on_cooldown,
        cooldown_until=cooldown_until,
        times_used=times_used,
    )


async def get_user_abilities(
    conn: asyncpg.Connection, user_id: str
) -> list[AbilityInfo]:
    """Get all abilities for user's current class with live status."""
    row = await conn.fetchrow(
        "SELECT character_class FROM users WHERE id = $1", user_id
    )
    if not row or not row["character_class"]:
        return []

    class_id_str = row["character_class"]
    progress = await conn.fetchrow(
        "SELECT class_level FROM user_class_progress WHERE user_id = $1", user_id
    )
    class_level = progress["class_level"] if progress else 1

    abilities_cfg = get_class_abilities(class_id_str)
    if not abilities_cfg:
        return []

    # Load DB state for all abilities at once
    ability_ids = [a.id for a in abilities_cfg]
    db_rows = await conn.fetch(
        "SELECT * FROM user_abilities WHERE user_id = $1 AND ability_id = ANY($2::text[])",
        user_id, ability_ids,
    )
    db_map = {r["ability_id"]: r for r in db_rows}

    result = []
    for a in abilities_cfg:
        result.append(_ability_to_info(a, class_level=class_level, db_row=db_map.get(a.id)))
    return result


async def activate_ability(
    conn: asyncpg.Connection, user_id: str, ability_id: str
) -> AbilityActivateResponse:
    """Activate an ability. Must be called inside a transaction.

    For Rage Mode: sets active_until, cooldown_until, rage_active_until on progress.
    """
    row = await conn.fetchrow(
        "SELECT character_class FROM users WHERE id = $1", user_id
    )
    if not row or not row["character_class"]:
        raise ValueError("У вас нет активного класса")

    class_id_str = row["character_class"]
    ability = get_ability_config(class_id_str, ability_id)
    if ability is None:
        raise ValueError(f"Способность не найдена: {ability_id}")

    progress = await conn.fetchrow(
        "SELECT class_level, rage_active_until FROM user_class_progress WHERE user_id = $1",
        user_id,
    )
    class_level = progress["class_level"] if progress else 1

    if class_level < ability.required_class_level:
        raise ValueError(
            f"Требуется уровень класса {ability.required_class_level}, ваш: {class_level}"
        )

    now = datetime.now(timezone.utc)

    # Check cooldown
    db_ability = await conn.fetchrow(
        "SELECT cooldown_until, active_until FROM user_abilities WHERE user_id = $1 AND ability_id = $2",
        user_id, ability_id,
    )
    if db_ability:
        cooldown_val = db_ability["cooldown_until"]
        if cooldown_val and cooldown_val > now:
            remaining_hours = int((cooldown_val - now).total_seconds() / 3600)
            raise ValueError(
                f"Перезарядка: ещё ~{remaining_hours}ч (до {cooldown_val.strftime('%d.%m %H:%M')} UTC)"
            )
        active_val = db_ability["active_until"]
        if active_val and active_val > now:
            raise ValueError("Способность уже активна")

    active_until = now + timedelta(hours=ability.duration_hours)
    cooldown_until = now + timedelta(hours=ability.cooldown_hours)

    # Upsert ability state
    await conn.execute(
        """
        INSERT INTO user_abilities (user_id, ability_id, class_id, last_activated_at, active_until, cooldown_until, times_used)
        VALUES ($1, $2, $3, $4, $5, $6, 1)
        ON CONFLICT (user_id, ability_id) DO UPDATE
        SET last_activated_at = $4, active_until = $5, cooldown_until = $6,
            times_used = user_abilities.times_used + 1
        """,
        user_id, ability_id, class_id_str, now, active_until, cooldown_until,
    )

    # If this is Rage Mode, set rage_active_until on class progress for quick checks
    if ability_id == "rage_mode":
        await conn.execute(
            "UPDATE user_class_progress SET rage_active_until = $1, updated_at = $2 WHERE user_id = $3",
            active_until, now, user_id,
        )

    # Notification
    await notification_service.create_notification(
        conn,
        user_id=user_id,
        title=f"{ability.icon} {ability.name_ru} активирован!",
        message=f"Действует {ability.duration_hours}ч. Перезарядка: {ability.cooldown_hours}ч.",
        event_type="ability_activated",
    )

    # Build response
    new_db_row_proxy = {
        "active_until": active_until,
        "cooldown_until": cooldown_until,
        "times_used": (db_ability["times_used"] + 1) if db_ability else 1,
    }
    ability_info = _ability_to_info(ability, class_level=class_level, db_row=new_db_row_proxy)

    return AbilityActivateResponse(
        message=f"{ability.name_ru} активирован на {ability.duration_hours}ч!",
        ability=ability_info,
    )


# ════════════════════════════════════════════
# Phase 2: Perk effect helpers (called by quest/XP logic)
# ════════════════════════════════════════════

async def get_active_perk_effects(
    conn: asyncpg.Connection, user_id: str, class_id: str
) -> dict[str, float | int | bool]:
    """Aggregate all active perk effects for a user's unlocked perks.

    Returns a merged dict of effect_key → value (summed for floats/ints, OR for bools).
    """
    perk_rows = await conn.fetch(
        "SELECT perk_id FROM user_perks WHERE user_id = $1 AND class_id = $2",
        user_id, class_id,
    )
    if not perk_rows:
        return {}

    merged: dict[str, float | int | bool] = {}
    for row in perk_rows:
        perk = get_perk_config(class_id, row["perk_id"])
        if perk is None:
            continue
        for ek, ev in perk.effects.items():
            if isinstance(ev, bool):
                merged[ek] = merged.get(ek, False) or ev  # type: ignore[assignment]
            else:
                merged[ek] = merged.get(ek, 0) + ev  # type: ignore[assignment]
    return merged


async def is_rage_mode_active(
    conn: asyncpg.Connection, user_id: str
) -> bool:
    """Quick check: is the user currently in Rage Mode?"""
    row = await conn.fetchrow(
        "SELECT rage_active_until FROM user_class_progress WHERE user_id = $1",
        user_id,
    )
    if not row or not row["rage_active_until"]:
        return False
    return row["rage_active_until"] > datetime.now(timezone.utc)


async def get_active_ability_effects(
    conn: asyncpg.Connection, user_id: str
) -> dict[str, float | int | bool]:
    """Aggregate effects from ALL currently active abilities for a user.

    Queries `user_abilities WHERE active_until > now`, then merges effects
    from each ability's config (sum numbers, OR booleans).
    """
    now = datetime.now(timezone.utc)
    rows = await conn.fetch(
        "SELECT ability_id, class_id FROM user_abilities "
        "WHERE user_id = $1 AND active_until > $2",
        user_id, now,
    )
    if not rows:
        return {}

    merged: dict[str, float | int | bool] = {}
    for row in rows:
        ability_cfg = get_ability_config(row["class_id"], row["ability_id"])
        if ability_cfg is None:
            continue
        for ek, ev in ability_cfg.effects.items():
            if isinstance(ev, bool):
                merged[ek] = merged.get(ek, False) or ev  # type: ignore[assignment]
            else:
                merged[ek] = merged.get(ek, 0) + ev  # type: ignore[assignment]
    return merged
