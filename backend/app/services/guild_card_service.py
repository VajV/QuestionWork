"""Deterministic guild reward card drops for confirmed quests."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Optional

import asyncpg

from app.services import wallet_service


_BADGE_SLUG_RE = re.compile(r"[^a-z0-9]+")


# Maps each trophy family to its item category for the artifact/cosmetics layer.
# - collectible: lore/history items, kept for prestige display
# - cosmetic:    appearance items, change how profile/guild looks
# - equipable:   utility items with mild display modifiers (non-pay-to-win)
_FAMILY_ITEM_CATEGORY: dict[str, str] = {
    "sigil": "collectible",
    "relic": "collectible",
    "banner": "cosmetic",
    "artifact": "equipable",
    "charter": "cosmetic",
    "crown": "cosmetic",
    "core": "equipable",
}

# Solo-exclusive families — used only in SOLO_CARD_POOLS, never in guild trophies.
_SOLO_FAMILY_ITEM_CATEGORY: dict[str, str] = {
    "wanderer": "collectible",
    "cipher": "collectible",
    "crest": "cosmetic",
    "edge": "equipable",
    "mark": "collectible",
}

# Drop-rate base chances (out of 10 000).
# Guild members drop more frequently; solo players drop less often but get better rarity floor.
GUILD_DROP_BASE_CHANCE: int = 1000   # 10 %
SOLO_DROP_BASE_CHANCE: int = 500     # 5 %
PROFILE_ARTIFACT_SLOT = "profile_artifact"

_EQUIPPABLE_EFFECT_SUMMARIES: dict[str, str] = {
    "artifact": "Подсвечивает профиль как хранителя редких контрактных трофеев.",
    "core": "Даёт легендарный акцент профиля и подчёркивает ключевой артефакт сезона.",
    "edge": "Добавляет соло-ветке резкий профильный акцент без влияния на экономику.",
}

_USER_ARTIFACT_SELECT = """
    SELECT id, card_code, name, rarity, family, description, accent,
           source_quest_id, dropped_at, is_equipped, equip_slot, equipped_at
    FROM guild_reward_cards
"""


# Solo-exclusive card pool — no common tier; minimum rarity is rare.
SOLO_CARD_POOLS: dict[str, list[dict[str, str]]] = {
    "rare": [
        {
            "card_code": "wanderer-seal",
            "name": "Wanderer's Seal",
            "family": "wanderer",
            "description": "Печать странника — трофей фрилансера, закрывающего контракты в одиночку.",
            "accent": "teal",
        },
        {
            "card_code": "lone-cipher",
            "name": "Lone Cipher",
            "family": "cipher",
            "description": "Шифр одиночки — редкий артефакт вольного стрелка.",
            "accent": "indigo",
        },
    ],
    "epic": [
        {
            "card_code": "drifter-crest",
            "name": "Drifter's Crest",
            "family": "crest",
            "description": "Эпический герб для фрилансеров, которые идут своим путём.",
            "accent": "rose",
        },
        {
            "card_code": "phantom-edge",
            "name": "Phantom Edge",
            "family": "edge",
            "description": "Призрачное оружие тех, кто действует в тени гильдии.",
            "accent": "purple",
        },
    ],
    "legendary": [
        {
            "card_code": "sovereign-mark",
            "name": "Sovereign Mark",
            "family": "mark",
            "description": "Легендарная метка суверена — высший трофей соло-пути.",
            "accent": "gold",
        },
    ],
}

CARD_POOLS: dict[str, list[dict[str, str]]] = {
    "common": [
        {
            "card_code": "ember-sigil",
            "name": "Ember Sigil",
            "family": "sigil",
            "description": "Базовая трофейная печать за закрытый контракт.",
            "accent": "amber",
        },
        {
            "card_code": "ledger-shard",
            "name": "Ledger Shard",
            "family": "relic",
            "description": "Осколок контрактной хроники гильдии.",
            "accent": "slate",
        },
    ],
    "rare": [
        {
            "card_code": "storm-banner",
            "name": "Storm Banner",
            "family": "banner",
            "description": "Редкое знамя за устойчивую боевую серию.",
            "accent": "cyan",
        },
        {
            "card_code": "vault-key",
            "name": "Vault Key",
            "family": "artifact",
            "description": "Ключ усиления treasury pressure и статуса гильдии.",
            "accent": "emerald",
        },
    ],
    "epic": [
        {
            "card_code": "astral-charter",
            "name": "Astral Charter",
            "family": "charter",
            "description": "Эпическая грамота за высокий риск и сильный payout flow.",
            "accent": "violet",
        },
        {
            "card_code": "raid-crown",
            "name": "Raid Crown",
            "family": "crown",
            "description": "Эпический трофей для составов, которые закрывают сложные рейды.",
            "accent": "amber",
        },
    ],
    "legendary": [
        {
            "card_code": "sun-forge-core",
            "name": "Sun Forge Core",
            "family": "core",
            "description": "Легендарное ядро кузницы, выпадающее только на сильных подтверждениях.",
            "accent": "gold",
        },
    ],
}


SEASONAL_FAMILY_SETS: dict[str, dict[str, str | int]] = {
    "sigil": {
        "label": "Forge Sigils",
        "accent": "amber",
        "season_code": "forge-awakening",
        "target_cards": 3,
    },
    "relic": {
        "label": "Archive Relics",
        "accent": "slate",
        "season_code": "forge-awakening",
        "target_cards": 3,
    },
    "banner": {
        "label": "Storm Banners",
        "accent": "cyan",
        "season_code": "forge-awakening",
        "target_cards": 4,
    },
    "artifact": {
        "label": "Vault Artifacts",
        "accent": "emerald",
        "season_code": "forge-awakening",
        "target_cards": 4,
    },
    "charter": {
        "label": "Astral Charters",
        "accent": "violet",
        "season_code": "forge-awakening",
        "target_cards": 2,
    },
    "crown": {
        "label": "Raid Crowns",
        "accent": "amber",
        "season_code": "forge-awakening",
        "target_cards": 2,
    },
    "core": {
        "label": "Sun Forge Core",
        "accent": "gold",
        "season_code": "forge-awakening",
        "target_cards": 1,
    },
}


SEASONAL_SET_REWARDS: dict[str, dict[str, str | int | Decimal]] = {
    "sigil": {
        "label": "Forge payroll cache",
        "treasury_bonus": Decimal("18.00"),
        "guild_tokens_bonus": 1,
        "badge_name": "Sigil Wardens",
    },
    "relic": {
        "label": "Archive treasury relay",
        "treasury_bonus": Decimal("22.00"),
        "guild_tokens_bonus": 1,
        "badge_name": "Archive Keepers",
    },
    "banner": {
        "label": "Storm campaign reserve",
        "treasury_bonus": Decimal("40.00"),
        "guild_tokens_bonus": 3,
        "badge_name": "Storm Standard",
    },
    "artifact": {
        "label": "Vault pressure release",
        "treasury_bonus": Decimal("55.00"),
        "guild_tokens_bonus": 4,
        "badge_name": "Vault Ascendants",
    },
    "charter": {
        "label": "Astral expedition grant",
        "treasury_bonus": Decimal("65.00"),
        "guild_tokens_bonus": 5,
        "badge_name": "Astral Cartographers",
    },
    "crown": {
        "label": "Raid command stipend",
        "treasury_bonus": Decimal("75.00"),
        "guild_tokens_bonus": 5,
        "badge_name": "Raid Regents",
    },
    "core": {
        "label": "Sun forge ignition",
        "treasury_bonus": Decimal("120.00"),
        "guild_tokens_bonus": 8,
        "badge_name": "Sunforged Circle",
    },
}


def _default_reward_configs() -> dict[tuple[str, str], dict[str, str | int | Decimal]]:
    configs: dict[tuple[str, str], dict[str, str | int | Decimal]] = {}
    for family, meta in SEASONAL_FAMILY_SETS.items():
        configs[(str(meta["season_code"]), family)] = {
            "season_code": str(meta["season_code"]),
            "family": family,
            "label": str(SEASONAL_SET_REWARDS[family]["label"]),
            "accent": str(meta["accent"]),
            "treasury_bonus": wallet_service.quantize_money(SEASONAL_SET_REWARDS[family]["treasury_bonus"]),
            "guild_tokens_bonus": int(SEASONAL_SET_REWARDS[family]["guild_tokens_bonus"]),
            "badge_name": str(SEASONAL_SET_REWARDS[family]["badge_name"]),
        }
    return configs


def _row_get(row: Any, key: str, default=None):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def get_artifact_effect_summary(family: str, item_category: str) -> str | None:
    if item_category != "equipable":
        return None
    return _EQUIPPABLE_EFFECT_SUMMARIES.get(
        family,
        "Даёт мягкий визуальный эффект профиля без влияния на выплату и XP.",
    )


def serialize_user_artifact(row: Any) -> dict[str, Any]:
    family = str(_row_get(row, "family", ""))
    item_category = _FAMILY_ITEM_CATEGORY.get(family, "collectible")
    return {
        "id": str(_row_get(row, "id", "")),
        "card_code": str(_row_get(row, "card_code", "")),
        "name": str(_row_get(row, "name", "")),
        "rarity": _row_get(row, "rarity"),
        "family": family,
        "description": str(_row_get(row, "description", "")),
        "accent": str(_row_get(row, "accent", "")),
        "item_category": item_category,
        "is_equipped": bool(_row_get(row, "is_equipped", False)),
        "equip_slot": _row_get(row, "equip_slot"),
        "equipped_at": _row_get(row, "equipped_at"),
        "equipped_effect_summary": get_artifact_effect_summary(family, item_category),
        "source_quest_id": str(_row_get(row, "source_quest_id", "")),
        "dropped_at": _row_get(row, "dropped_at"),
    }


async def load_season_reward_configs(
    conn: asyncpg.Connection,
    *,
    season_code: str | None = None,
) -> dict[tuple[str, str], dict[str, str | int | Decimal]]:
    query = """
        SELECT season_code, family, label, accent, treasury_bonus, guild_tokens_bonus, badge_name
        FROM guild_season_reward_configs
        WHERE is_active = TRUE
    """
    args: list[object] = []
    if season_code:
        query += " AND season_code = $1"
        args.append(season_code)

    rows = await conn.fetch(query, *args)
    if not rows:
        return _default_reward_configs()

    configs: dict[tuple[str, str], dict[str, str | int | Decimal]] = {}
    for row in rows:
        configs[(str(row["season_code"]), str(row["family"]))] = {
            "season_code": str(row["season_code"]),
            "family": str(row["family"]),
            "label": str(row["label"]),
            "accent": str(row["accent"]),
            "treasury_bonus": wallet_service.quantize_money(row["treasury_bonus"]),
            "guild_tokens_bonus": int(row["guild_tokens_bonus"] or 0),
            "badge_name": str(row["badge_name"]),
        }
    return configs


def _hash_int(*parts: object) -> int:
    payload = "::".join(str(part) for part in parts)
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest(), 16)


def _slugify_badge(value: str) -> str:
    slug = _BADGE_SLUG_RE.sub("-", value.lower()).strip("-")
    return slug[:80] or f"guild-badge-{uuid.uuid4().hex[:8]}"


def _drop_threshold(
    gross_amount,
    xp_reward: int,
    *,
    is_urgent: bool,
    drop_track: str = "guild",
) -> int:
    """Return the drop-chance threshold (out of 10 000).

    ``chance_roll < threshold`` → card drops.
    Guild track uses ``GUILD_DROP_BASE_CHANCE`` (10 %), solo track uses
    ``SOLO_DROP_BASE_CHANCE`` (5 %).  Quality bonuses scale the chance up
    for high-value quests (up to 2× the base for solo, ~20 % for guild).
    """
    base = GUILD_DROP_BASE_CHANCE if drop_track == "guild" else SOLO_DROP_BASE_CHANCE
    gross = wallet_service.quantize_money(gross_amount)
    bonus = min(500, max(0, xp_reward) * 1)                  # up to +5 % for XP
    bonus += min(300, int(gross // Decimal("250")) * 25)      # up to +3 % for budget
    if is_urgent:
        bonus += 200                                           # +2 % for urgency
    return base + bonus


def roll_quest_card_drop(
    *,
    quest_id: str,
    guild_id: str,
    freelancer_id: str,
    gross_amount,
    xp_reward: int,
    is_urgent: bool,
) -> Optional[dict[str, str]]:
    chance_roll = _hash_int("drop", quest_id, guild_id, freelancer_id) % 10000
    if chance_roll >= _drop_threshold(gross_amount, xp_reward, is_urgent=is_urgent, drop_track="guild"):
        return None

    rarity_roll = _hash_int("rarity", quest_id, guild_id, freelancer_id, xp_reward) % 10000
    if rarity_roll < 180:
        rarity = "legendary"
    elif rarity_roll < 1250:
        rarity = "epic"
    elif rarity_roll < 3900:
        rarity = "rare"
    else:
        rarity = "common"

    pool = CARD_POOLS[rarity]
    template = pool[_hash_int("card", quest_id, guild_id, freelancer_id, rarity) % len(pool)]
    family = template["family"]
    return {
        **template,
        "rarity": rarity,
        "item_category": _FAMILY_ITEM_CATEGORY.get(family, "collectible"),
    }


def _format_money(value: Decimal | int | float | None) -> str:
    if value is None:
        return "0.00"
    return f"{wallet_service.quantize_money(value):.2f}"


def _resolve_reward_configs(
    reward_configs: dict[tuple[str, str], dict[str, str | int | Decimal]] | None,
) -> dict[tuple[str, str], dict[str, str | int | Decimal]]:
    return reward_configs or _default_reward_configs()


def _get_reward_metadata(
    family: str,
    season_code: str,
    reward_configs: dict[tuple[str, str], dict[str, str | int | Decimal]] | None = None,
) -> dict[str, str | int | Decimal]:
    family_meta = SEASONAL_FAMILY_SETS.get(family)
    if not family_meta:
        raise ValueError(f"Unknown seasonal family: {family}")
    if str(family_meta["season_code"]) != season_code:
        raise ValueError(f"Unknown season code for family {family}: {season_code}")

    reward_meta = _resolve_reward_configs(reward_configs).get((season_code, family))
    if not reward_meta:
        raise ValueError(f"Missing reward metadata for seasonal family: {family}")
    return reward_meta


async def _fetch_completed_sets_for_backfill(
    conn: asyncpg.Connection,
    guild_id: str,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT family, COUNT(*)::INT AS card_total
        FROM guild_reward_cards
        WHERE guild_id = $1
        GROUP BY family
        """,
        guild_id,
    )

    completed_sets: list[dict[str, Any]] = []
    for row in rows:
        family = str(row["family"])
        family_meta = SEASONAL_FAMILY_SETS.get(family)
        if not family_meta:
            continue

        collected_cards = int(row.get("card_total") or row.get("collected_cards") or 0)
        target_cards = int(family_meta["target_cards"])
        if collected_cards < target_cards:
            continue

        completed_sets.append(
            {
                "family": family,
                "season_code": str(family_meta["season_code"]),
                "card_total": collected_cards,
            }
        )

    return completed_sets


async def _fetch_claimed_reward_pairs(
    conn: asyncpg.Connection,
    guild_id: str,
) -> set[tuple[str, str]]:
    rows = await conn.fetch(
        """
        SELECT family, season_code
        FROM guild_seasonal_rewards
        WHERE guild_id = $1
        """,
        guild_id,
    )
    return {
        (str(row["season_code"]), str(row["family"]))
        for row in rows
    }


async def _insert_claimed_reward(
    conn: asyncpg.Connection,
    guild_id: str,
    seasonal_set: dict[str, Any],
    reward_meta: dict[str, str | int | Decimal],
    *,
    awarded_at: datetime,
) -> asyncpg.Record | None:
    family = str(seasonal_set["family"])
    family_meta = SEASONAL_FAMILY_SETS[family]
    reward_id = f"gset_{uuid.uuid4().hex[:12]}"
    return await conn.fetchrow(
        """
        INSERT INTO guild_seasonal_rewards (
            id, guild_id, family, season_code, label, accent,
            treasury_bonus, guild_tokens_bonus, badge_name, claimed_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (guild_id, season_code, family) DO NOTHING
        RETURNING id, family, season_code, label, accent, treasury_bonus, guild_tokens_bonus, badge_name, claimed_at
        """,
        reward_id,
        guild_id,
        family,
        str(seasonal_set["season_code"]),
        str(reward_meta["label"]),
        str(family_meta["accent"]),
        wallet_service.quantize_money(reward_meta["treasury_bonus"]),
        int(reward_meta["guild_tokens_bonus"]),
        str(reward_meta["badge_name"]),
        awarded_at,
    )


async def _upsert_guild_badge(
    conn: asyncpg.Connection,
    guild_id: str,
    seasonal_set: dict[str, Any],
    reward_row: asyncpg.Record,
) -> asyncpg.Record:
    badge_name = str(reward_row["badge_name"])
    badge_code = f"{reward_row['season_code']}:{reward_row['family']}"
    badge_id = f"gbadge_{uuid.uuid4().hex[:12]}"
    family = str(seasonal_set["family"])
    return await conn.fetchrow(
        """
        INSERT INTO guild_badges (
            id, guild_id, badge_code, name, slug, accent, season_code, family, awarded_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (guild_id, badge_code) DO UPDATE
            SET name = EXCLUDED.name,
                slug = EXCLUDED.slug,
                accent = EXCLUDED.accent,
                season_code = EXCLUDED.season_code,
                family = EXCLUDED.family
        RETURNING id, badge_code, name, slug, accent, season_code, family, awarded_at
        """,
        badge_id,
        guild_id,
        badge_code,
        badge_name,
        _slugify_badge(badge_name),
        str(reward_row["accent"] or SEASONAL_FAMILY_SETS[family]["accent"]),
        str(reward_row["season_code"]),
        str(reward_row["family"]),
        reward_row["claimed_at"],
    )


def build_seasonal_set_progress(
    trophies: Iterable[dict],
    claimed_rewards: Iterable[dict] | None = None,
    reward_configs: dict[tuple[str, str], dict[str, str | int | Decimal]] | None = None,
) -> list[dict[str, Any]]:
    family_counts: dict[str, int] = {}
    rarity_by_family: dict[str, str] = {}

    for trophy in trophies:
        family = str(trophy.get("family") or "").strip()
        if not family:
            continue
        family_counts[family] = family_counts.get(family, 0) + 1
        rarity_by_family.setdefault(family, str(trophy.get("rarity") or "common"))

    claimed_reward_by_family: dict[str, dict[str, Any]] = {}
    for reward in claimed_rewards or []:
        family = str(reward.get("family") or "").strip()
        if family:
            claimed_reward_by_family[family] = dict(reward)

    resolved_reward_configs = _resolve_reward_configs(reward_configs)
    seasonal_sets: list[dict[str, Any]] = []
    for family, meta in SEASONAL_FAMILY_SETS.items():
        target_cards = int(meta["target_cards"])
        collected_cards = family_counts.get(family, 0)
        missing_cards = max(target_cards - collected_cards, 0)
        progress_percent = int(min(100, round((collected_cards / target_cards) * 100))) if target_cards else 0
        reward_meta = _get_reward_metadata(family, str(meta["season_code"]), resolved_reward_configs)
        claimed_reward = claimed_reward_by_family.get(family)
        seasonal_sets.append(
            {
                "family": family,
                "label": str(meta["label"]),
                "accent": str(meta["accent"]),
                "season_code": str(meta["season_code"]),
                "target_cards": target_cards,
                "collected_cards": collected_cards,
                "missing_cards": missing_cards,
                "progress_percent": progress_percent,
                "completed": collected_cards >= target_cards,
                "rarity": rarity_by_family.get(family),
                "reward_label": str(reward_meta["label"]),
                "reward_treasury_bonus": _format_money(reward_meta["treasury_bonus"]),
                "reward_guild_tokens_bonus": int(reward_meta["guild_tokens_bonus"]),
                "reward_badge_name": str(reward_meta["badge_name"]),
                "reward_claimed": claimed_reward is not None,
                "reward_claimed_at": claimed_reward.get("claimed_at") if claimed_reward else None,
            }
        )

    seasonal_sets.sort(
        key=lambda item: (
            not bool(item["completed"]),
            -int(item["progress_percent"]),
            str(item["family"]),
        )
    )
    return seasonal_sets


async def claim_completed_seasonal_rewards(
    conn: asyncpg.Connection,
    *,
    guild_id: str,
    awarded_at: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    timestamp = awarded_at or datetime.now(timezone.utc)
    return await backfill_guild_seasonal_rewards(conn, guild_id=guild_id, awarded_at=timestamp)


async def backfill_guild_seasonal_rewards(
    conn: asyncpg.Connection,
    *,
    guild_id: str,
    awarded_at: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    completed_sets = await _fetch_completed_sets_for_backfill(conn, guild_id)
    if not completed_sets:
        return []

    claimed_pairs = await _fetch_claimed_reward_pairs(conn, guild_id)
    reward_configs = await load_season_reward_configs(conn)
    inserted_rewards: list[dict[str, Any]] = []
    timestamp = awarded_at or datetime.now(timezone.utc)

    for seasonal_set in completed_sets:
        reward_key = (str(seasonal_set["season_code"]), str(seasonal_set["family"]))
        if reward_key in claimed_pairs:
            continue

        reward_meta = _get_reward_metadata(
            str(seasonal_set["family"]),
            str(seasonal_set["season_code"]),
            reward_configs,
        )
        inserted = await _insert_claimed_reward(
            conn,
            guild_id,
            seasonal_set,
            reward_meta,
            awarded_at=timestamp,
        )
        if not inserted:
            continue

        guild_badge = await _upsert_guild_badge(
            conn,
            guild_id,
            seasonal_set,
            inserted,
        )

        inserted_rewards.append(
            {
                "id": inserted["id"],
                "family": inserted["family"],
                "season_code": inserted["season_code"],
                "label": inserted["label"],
                "accent": inserted["accent"],
                "treasury_bonus": wallet_service.quantize_money(inserted["treasury_bonus"]),
                "guild_tokens_bonus": int(inserted["guild_tokens_bonus"] or 0),
                "badge_name": inserted["badge_name"],
                "claimed_at": inserted["claimed_at"],
                "guild_badge": {
                    "id": guild_badge["id"],
                    "badge_code": guild_badge["badge_code"],
                    "name": guild_badge["name"],
                    "slug": guild_badge["slug"],
                    "accent": guild_badge["accent"],
                    "season_code": guild_badge["season_code"],
                    "family": guild_badge["family"],
                    "awarded_at": guild_badge["awarded_at"],
                },
            }
        )
        claimed_pairs.add(reward_key)

    return inserted_rewards


async def award_quest_card_drop(
    conn: asyncpg.Connection,
    *,
    guild_id: str,
    quest_id: str,
    freelancer_id: str,
    gross_amount,
    xp_reward: int,
    is_urgent: bool,
    dropped_at: Optional[datetime] = None,
) -> Optional[dict[str, str]]:
    existing = await conn.fetchrow(
        "SELECT * FROM guild_reward_cards WHERE source_quest_id = $1",
        quest_id,
    )
    if existing:
        return {
            "id": existing["id"],
            "card_code": existing["card_code"],
            "name": existing["name"],
            "rarity": existing["rarity"],
            "family": existing["family"],
            "description": existing["description"],
            "accent": existing["accent"],
            "item_category": _FAMILY_ITEM_CATEGORY.get(str(existing["family"]), "collectible"),
        }

    card = roll_quest_card_drop(
        quest_id=quest_id,
        guild_id=guild_id,
        freelancer_id=freelancer_id,
        gross_amount=gross_amount,
        xp_reward=xp_reward,
        is_urgent=is_urgent,
    )
    if not card:
        return None

    card_id = f"gcard_{uuid.uuid4().hex[:12]}"
    timestamp = dropped_at or datetime.now(timezone.utc)
    await conn.execute(
        """
        INSERT INTO guild_reward_cards (
            id, guild_id, source_quest_id, awarded_to_user_id,
            card_code, name, rarity, family, description, accent, dropped_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
        card_id,
        guild_id,
        quest_id,
        freelancer_id,
        card["card_code"],
        card["name"],
        card["rarity"],
        card["family"],
        card["description"],
        card["accent"],
        timestamp,
    )
    return {
        "id": card_id,
        **card,
    }


def roll_solo_quest_card_drop(
    *,
    quest_id: str,
    freelancer_id: str,
    gross_amount,
    xp_reward: int,
    is_urgent: bool,
) -> Optional[dict[str, str]]:
    """Deterministic card drop for solo (non-guild) freelancers.

    Uses a sentinel to keep the hash space independent from guild drops.
    Drop chance is based on ``SOLO_DROP_BASE_CHANCE`` (5 %) — lower than guild
    (10 %) but the solo card pool has a better rarity floor: minimum rarity is
    *rare* (no common cards).
    """
    _SOLO_SENTINEL = "__solo__"
    chance_roll = _hash_int("drop", quest_id, _SOLO_SENTINEL, freelancer_id) % 10000
    if chance_roll >= _drop_threshold(gross_amount, xp_reward, is_urgent=is_urgent, drop_track="solo"):
        return None

    # Solo rarity distribution — no common tier.
    rarity_roll = _hash_int("rarity", quest_id, _SOLO_SENTINEL, freelancer_id, xp_reward) % 10000
    if rarity_roll < 250:
        rarity = "legendary"
    elif rarity_roll < 2200:
        rarity = "epic"
    else:
        rarity = "rare"

    pool = SOLO_CARD_POOLS[rarity]
    template = pool[_hash_int("card", quest_id, _SOLO_SENTINEL, freelancer_id, rarity) % len(pool)]
    family = template["family"]
    return {
        **template,
        "rarity": rarity,
        "item_category": _SOLO_FAMILY_ITEM_CATEGORY.get(family, "collectible"),
    }


async def award_solo_quest_card_drop(
    conn: asyncpg.Connection,
    *,
    quest_id: str,
    freelancer_id: str,
    gross_amount,
    xp_reward: int,
    is_urgent: bool,
    dropped_at: Optional[datetime] = None,
) -> Optional[dict[str, str]]:
    """Award a card drop to a solo (non-guild) freelancer on quest confirmation.

    Solo drops are persisted to ``player_card_drops`` — a dedicated table
    separate from the guild trophy system.  One card per quest (idempotent by
    quest_id).  Repeated calls for the same quest return the existing record
    without a second INSERT.
    """
    existing = await conn.fetchrow(
        "SELECT * FROM player_card_drops WHERE quest_id = $1",
        quest_id,
    )
    required_existing_fields = {
        "id",
        "card_code",
        "name",
        "rarity",
        "family",
        "description",
        "accent",
        "item_category",
    }
    if existing and required_existing_fields.issubset(set(existing.keys())):
        return {
            "id": existing["id"],
            "card_code": existing["card_code"],
            "name": existing["name"],
            "rarity": existing["rarity"],
            "family": existing["family"],
            "description": existing["description"],
            "accent": existing["accent"],
            "item_category": existing["item_category"],
        }

    card = roll_solo_quest_card_drop(
        quest_id=quest_id,
        freelancer_id=freelancer_id,
        gross_amount=gross_amount,
        xp_reward=xp_reward,
        is_urgent=is_urgent,
    )
    if not card:
        return None

    card_id = f"pcard_{uuid.uuid4().hex[:12]}"
    timestamp = dropped_at or datetime.now(timezone.utc)
    await conn.execute(
        """
        INSERT INTO player_card_drops (
            id, freelancer_id, quest_id,
            card_code, name, rarity, family, description, accent, item_category, dropped_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
        card_id,
        freelancer_id,
        quest_id,
        card["card_code"],
        card["name"],
        card["rarity"],
        card["family"],
        card["description"],
        card["accent"],
        card["item_category"],
        timestamp,
    )
    return {
        "id": card_id,
        **card,
    }


async def list_user_artifacts(
    conn: asyncpg.Connection,
    *,
    user_id: str,
) -> dict[str, Any]:
    rows = await conn.fetch(
        f"""
        {_USER_ARTIFACT_SELECT}
        WHERE awarded_to_user_id = $1
        ORDER BY is_equipped DESC, dropped_at DESC
        """,
        user_id,
    )
    cosmetics: list[dict[str, Any]] = []
    collectibles: list[dict[str, Any]] = []
    equipable: list[dict[str, Any]] = []
    for row in rows:
        artifact = serialize_user_artifact(row)
        if artifact["item_category"] == "cosmetic":
            cosmetics.append(artifact)
        elif artifact["item_category"] == "equipable":
            equipable.append(artifact)
        else:
            collectibles.append(artifact)
    return {
        "cosmetics": cosmetics,
        "collectibles": collectibles,
        "equipable": equipable,
        "total": len(rows),
    }


async def equip_user_artifact(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    artifact_id: str,
) -> dict[str, Any]:
    async with conn.transaction():
        row = await conn.fetchrow(
            f"""
            {_USER_ARTIFACT_SELECT}
            WHERE id = $1 AND awarded_to_user_id = $2
            FOR UPDATE
            """,
            artifact_id,
            user_id,
        )
        if not row:
            raise ValueError("Artifact not found in your collection")

        artifact = serialize_user_artifact(row)
        if artifact["item_category"] != "equipable":
            raise ValueError("Only equipable artifacts can be equipped")

        await conn.execute(
            """
            UPDATE guild_reward_cards
            SET is_equipped = FALSE, equip_slot = NULL, equipped_at = NULL
            WHERE awarded_to_user_id = $1 AND equip_slot = $2 AND is_equipped = TRUE
            """,
            user_id,
            PROFILE_ARTIFACT_SLOT,
        )
        timestamp = datetime.now(timezone.utc)
        await conn.execute(
            """
            UPDATE guild_reward_cards
            SET is_equipped = TRUE, equip_slot = $1, equipped_at = $2
            WHERE id = $3 AND awarded_to_user_id = $4
            """,
            PROFILE_ARTIFACT_SLOT,
            timestamp,
            artifact_id,
            user_id,
        )
        updated = await conn.fetchrow(
            f"""
            {_USER_ARTIFACT_SELECT}
            WHERE id = $1 AND awarded_to_user_id = $2
            """,
            artifact_id,
            user_id,
        )
    return serialize_user_artifact(updated)


async def unequip_user_artifact(
    conn: asyncpg.Connection,
    *,
    user_id: str,
    artifact_id: str,
) -> dict[str, Any]:
    async with conn.transaction():
        row = await conn.fetchrow(
            f"""
            {_USER_ARTIFACT_SELECT}
            WHERE id = $1 AND awarded_to_user_id = $2
            FOR UPDATE
            """,
            artifact_id,
            user_id,
        )
        if not row:
            raise ValueError("Artifact not found in your collection")

        artifact = serialize_user_artifact(row)
        if artifact["item_category"] != "equipable":
            raise ValueError("Only equipable artifacts can be unequipped")

        await conn.execute(
            """
            UPDATE guild_reward_cards
            SET is_equipped = FALSE, equip_slot = NULL, equipped_at = NULL
            WHERE id = $1 AND awarded_to_user_id = $2
            """,
            artifact_id,
            user_id,
        )
        updated = await conn.fetchrow(
            f"""
            {_USER_ARTIFACT_SELECT}
            WHERE id = $1 AND awarded_to_user_id = $2
            """,
            artifact_id,
            user_id,
        )
    return serialize_user_artifact(updated)