"""Guild economy progression tied to confirmed quest completions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

import asyncpg

from app.services import guild_card_service, guild_progression_service, notification_service, wallet_service


GUILD_TREASURY_SHARE_OF_PLATFORM_FEE = Decimal("0.35")
GUILD_TOKEN_BUDGET_STEP = Decimal("500.00")
GUILD_TOKEN_XP_STEP = 180
GUILD_CONTRIBUTION_TOKEN_WEIGHT = 30
GUILD_CONTRIBUTION_TREASURY_WEIGHT = Decimal("10")


def _seasonal_reward_payload(reward: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": reward["id"],
        "family": reward["family"],
        "season_code": reward["season_code"],
        "label": reward["label"],
        "accent": reward["accent"],
        "treasury_bonus": f"{wallet_service.quantize_money(reward['treasury_bonus']):.2f}",
        "guild_tokens_bonus": int(reward["guild_tokens_bonus"]),
        "badge_name": reward["badge_name"],
        "claimed_at": reward["claimed_at"].isoformat() if reward.get("claimed_at") else None,
    }


def _seasonal_reward_summary(rewards: list[dict[str, Any]]) -> str:
    if not rewards:
        return ""

    fragments = [
        (
            f"{reward['badge_name']} "
            f"(+{wallet_service.quantize_money(reward['treasury_bonus'])} treasury, "
            f"+{int(reward['guild_tokens_bonus'])} tokens)"
        )
        for reward in rewards
    ]
    return "; ".join(fragments)


def _build_seasonal_reward_notification_message(reward: dict[str, Any]) -> str:
    return (
        f"Guild seasonal reward claimed: {reward['badge_name']}. "
        f"Treasury +{wallet_service.quantize_money(reward['treasury_bonus'])}, "
        f"tokens +{int(reward['guild_tokens_bonus'])}."
    )


async def notify_guild_seasonal_claim(
    conn: asyncpg.Connection,
    *,
    guild_id: str,
    seasonal_rewards: list[dict[str, Any]],
) -> None:
    if not seasonal_rewards:
        return

    recipients = await conn.fetch(
        """
        SELECT user_id
        FROM guild_members
        WHERE guild_id = $1 AND status = 'active'
        ORDER BY joined_at ASC
        """,
        guild_id,
    )
    for reward in seasonal_rewards:
        for recipient in recipients:
            await notification_service.create_notification(
                conn,
                user_id=str(recipient["user_id"]),
                title=f"Guild seasonal reward claimed: {reward['badge_name']}",
                message=_build_seasonal_reward_notification_message(reward),
                event_type="guild_seasonal_reward",
            )


def _assert_in_transaction(conn: asyncpg.Connection) -> None:
    if not conn.is_in_transaction():
        raise RuntimeError("Guild economy mutations must run inside a DB transaction")


def derive_quest_completion_deltas(*, gross_amount, platform_fee, xp_reward: int) -> dict[str, int | Decimal]:
    gross = wallet_service.quantize_money(gross_amount)
    fee = wallet_service.quantize_money(platform_fee)
    treasury_delta = wallet_service.quantize_money(fee * GUILD_TREASURY_SHARE_OF_PLATFORM_FEE)

    budget_tokens = int(gross / GUILD_TOKEN_BUDGET_STEP)
    xp_tokens = max(0, int(xp_reward) // GUILD_TOKEN_XP_STEP)
    guild_tokens_delta = max(1, budget_tokens + xp_tokens)

    treasury_points = int(
        (treasury_delta * GUILD_CONTRIBUTION_TREASURY_WEIGHT).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )
    contribution_delta = max(
        1,
        int(xp_reward) + guild_tokens_delta * GUILD_CONTRIBUTION_TOKEN_WEIGHT + treasury_points,
    )
    rating_delta = max(1, guild_tokens_delta * 8 + contribution_delta // 25)

    return {
        "treasury_delta": treasury_delta,
        "guild_tokens_delta": guild_tokens_delta,
        "contribution_delta": contribution_delta,
        "rating_delta": rating_delta,
    }


async def record_guild_activity(
    conn: asyncpg.Connection,
    *,
    guild_id: str,
    event_type: str,
    summary: str,
    user_id: Optional[str] = None,
    quest_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    treasury_delta=Decimal("0.00"),
    guild_tokens_delta: int = 0,
    contribution_delta: int = 0,
    created_at: Optional[datetime] = None,
) -> str:
    _assert_in_transaction(conn)

    activity_id = f"gact_{uuid.uuid4().hex[:12]}"
    timestamp = created_at or datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO guild_activity (
            id, guild_id, user_id, quest_id, event_type, summary, payload,
            treasury_delta, guild_tokens_delta, contribution_delta, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10, $11)
        """,
        activity_id,
        guild_id,
        user_id,
        quest_id,
        event_type,
        summary,
        json.dumps(payload or {}),
        wallet_service.quantize_money(treasury_delta),
        guild_tokens_delta,
        contribution_delta,
        timestamp,
    )
    return activity_id


async def apply_quest_completion_rewards(
    conn: asyncpg.Connection,
    *,
    quest_id: str,
    freelancer_id: str,
    gross_amount,
    platform_fee,
    xp_reward: int,
    is_urgent: bool = False,
    confirmed_at: Optional[datetime] = None,
    source: str = "quest_confirmed",
) -> Optional[dict[str, Any]]:
    _assert_in_transaction(conn)

    membership = await conn.fetchrow(
        """
        SELECT
            gm.guild_id,
            gm.role,
            g.name AS guild_name
        FROM guild_members gm
        JOIN guilds g ON g.id = gm.guild_id
        WHERE gm.user_id = $1 AND gm.status = 'active'
        FOR UPDATE OF gm, g
        """,
        freelancer_id,
    )
    if not membership:
        return None

    deltas = derive_quest_completion_deltas(
        gross_amount=gross_amount,
        platform_fee=platform_fee,
        xp_reward=xp_reward,
    )
    timestamp = confirmed_at or datetime.now(timezone.utc)

    card_drop = await guild_card_service.award_quest_card_drop(
        conn,
        guild_id=membership["guild_id"],
        quest_id=quest_id,
        freelancer_id=freelancer_id,
        gross_amount=gross_amount,
        xp_reward=xp_reward,
        is_urgent=is_urgent,
        dropped_at=timestamp,
    )
    seasonal_rewards = await guild_card_service.claim_completed_seasonal_rewards(
        conn,
        guild_id=membership["guild_id"],
        awarded_at=timestamp,
    )
    await notify_guild_seasonal_claim(
        conn,
        guild_id=membership["guild_id"],
        seasonal_rewards=seasonal_rewards,
    )

    total_treasury_delta = deltas["treasury_delta"] + sum(
        (wallet_service.quantize_money(reward["treasury_bonus"]) for reward in seasonal_rewards),
        Decimal("0.00"),
    )
    total_guild_tokens_delta = deltas["guild_tokens_delta"] + sum(
        int(reward["guild_tokens_bonus"]) for reward in seasonal_rewards
    )

    await conn.execute(
        """
        UPDATE guilds
        SET treasury_balance = treasury_balance + $1,
            guild_tokens = guild_tokens + $2,
            rating = rating + $3,
            updated_at = $4
        WHERE id = $5
        """,
        total_treasury_delta,
        total_guild_tokens_delta,
        deltas["rating_delta"],
        timestamp,
        membership["guild_id"],
    )
    await conn.execute(
        """
        UPDATE guild_members
        SET contribution = contribution + $1
        WHERE guild_id = $2 AND user_id = $3 AND status = 'active'
        """,
        deltas["contribution_delta"],
        membership["guild_id"],
        freelancer_id,
    )

    await record_guild_activity(
        conn,
        guild_id=membership["guild_id"],
        user_id=freelancer_id,
        quest_id=quest_id,
        event_type="quest_confirmed",
        summary=(
            f"Quest confirmation added treasury +{wallet_service.quantize_money(total_treasury_delta)}, "
            f"tokens +{total_guild_tokens_delta} and contribution +{deltas['contribution_delta']}"
            + (f". Card drop: {card_drop['name']} ({card_drop['rarity']})" if card_drop else "")
            + (f". Seasonal rewards: {_seasonal_reward_summary(seasonal_rewards)}" if seasonal_rewards else "")
        ),
        payload={
            "source": source,
            "guild_name": membership["guild_name"],
            "role": membership["role"],
            "xp_reward": xp_reward,
            "card_drop": card_drop,
            "seasonal_rewards": [_seasonal_reward_payload(reward) for reward in seasonal_rewards],
        },
        treasury_delta=total_treasury_delta,
        guild_tokens_delta=int(total_guild_tokens_delta),
        contribution_delta=int(deltas["contribution_delta"]),
        created_at=timestamp,
    )

    progression = await guild_progression_service.apply_guild_xp_gain(
        conn,
        guild_id=membership["guild_id"],
        xp_gain=xp_reward,
        source=source,
        user_id=freelancer_id,
        quest_id=quest_id,
        occurred_at=timestamp,
    )

    await guild_progression_service.check_and_unlock_milestones(
        conn,
        guild_id=membership["guild_id"],
        seasonal_xp=int(progression.get("seasonal_xp", 0)),
        season_code=str(progression.get("season_code", "")),
        occurred_at=timestamp,
    )

    return {
        "guild_id": membership["guild_id"],
        "guild_name": membership["guild_name"],
        "card_drop": card_drop,
        "seasonal_rewards": seasonal_rewards,
        "treasury_delta": total_treasury_delta,
        "guild_tokens_delta": total_guild_tokens_delta,
        "contribution_delta": deltas["contribution_delta"],
        "rating_delta": deltas["rating_delta"],
        "progression": progression,
    }


async def award_solo_artifact_drop(
    conn: asyncpg.Connection,
    *,
    quest_id: str,
    freelancer_id: str,
    gross_amount,
    platform_fee,
    xp_reward: int,
    is_urgent: bool = False,
    confirmed_at: Optional[datetime] = None,
) -> Optional[dict[str, Any]]:
    """Award an artifact card drop to a solo (non-guild) freelancer.

    Called after quest confirmation for users who are not in any active guild.
    Returns the dropped card dict, or None if the drop threshold wasn't met.
    Duplicate handling: idempotent by quest_id — repeated calls return the
    existing record without a second insert.
    """
    _assert_in_transaction(conn)

    timestamp = confirmed_at or datetime.now(timezone.utc)
    card_drop = await guild_card_service.award_solo_quest_card_drop(
        conn,
        quest_id=quest_id,
        freelancer_id=freelancer_id,
        gross_amount=gross_amount,
        xp_reward=xp_reward,
        is_urgent=is_urgent,
        dropped_at=timestamp,
    )
    return card_drop