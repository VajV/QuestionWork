"""Service functions for platform-wide world meta snapshot."""

from datetime import datetime, timedelta, timezone

import asyncpg

from app.core.otel_utils import db_span


def _int_value(row: asyncpg.Record | dict | None, key: str) -> int:
    if not row:
        return 0
    value = row.get(key) if isinstance(row, dict) else row[key]
    return int(value or 0)


def _build_trend_metric(
    metric_id: str,
    label: str,
    current_value: int,
    previous_value: int,
    points: list[dict[str, int | str]],
) -> dict:
    delta_value = current_value - previous_value
    if previous_value > 0:
        delta_percent = round(delta_value / previous_value * 100)
    elif current_value > 0:
        delta_percent = 100
    else:
        delta_percent = 0

    if delta_value > 0:
        direction = "rising"
    elif delta_value < 0:
        direction = "falling"
    else:
        direction = "steady"

    return {
        "id": metric_id,
        "label": label,
        "current_value": current_value,
        "previous_value": previous_value,
        "delta_value": delta_value,
        "delta_percent": delta_percent,
        "direction": direction,
        "points": points,
    }


# ============================================================
# Seasonal map helpers — pure functions, testable without DB
# ============================================================

def _faction_status(trend: str) -> str:
    """Convert a faction trend label to a region status string."""
    return {"surging": "active", "holding": "contested", "recovering": "dormant"}.get(trend, "active")


def _build_season_extras(stage: str, progress_percent: int) -> dict:
    """Return chapter, stage_description, and next_unlock for a given season stage."""
    if stage == "finale":
        return {
            "chapter": "Глава III: Решающий Бой",
            "stage_description": "Финальная фаза. Каждое закрытие контракта сдвигает итоговый баланс.",
            "next_unlock": "Сезон завершается. Соберите все награды до конца цикла.",
        }
    if stage == "ascent":
        return {
            "chapter": "Глава II: Восхождение",
            "stage_description": "Сезон набирает обороты — фракции борются за доминирование.",
            "next_unlock": "Пройдите 75% цели, чтобы открыть Главу III и финальные награды.",
        }
    # muster (default / early stage)
    return {
        "chapter": "Глава I: Призыв к Оружию",
        "stage_description": "Сезон только открылся. Первые квесты формируют расклад сил.",
        "next_unlock": "Пройдите 35% цели, чтобы открыть Главу II и победные бонусы Восхождения.",
    }


def _build_regions(
    metrics: dict,
    faction_rows: list[dict],
    leader: dict,
    season_progress: int,
) -> list[dict]:
    """Derive 4 world map regions from current faction dynamics and activity signals."""
    total_score = sum(r["score"] for r in faction_rows) or 1
    faction_map = {r["id"]: r for r in faction_rows}

    def _pct(faction_id: str) -> int:
        return min(100, round(faction_map[faction_id]["score"] / total_score * 100))

    return [
        {
            "id": "frontier",
            "name": "Рубежи Фронта",
            "status": _faction_status(faction_map["vanguard"]["trend"]),
            "progress_percent": _pct("vanguard"),
            "dominant_faction_id": "vanguard",
            "activity_label": (
                f"{metrics['in_progress_quests']} активных контрактов, "
                f"{metrics['urgent_quests']} срочных"
            ),
        },
        {
            "id": "archive",
            "name": "Архив Трофеев",
            "status": _faction_status(faction_map["artisans"]["trend"]),
            "progress_percent": _pct("artisans"),
            "dominant_faction_id": "artisans",
            "activity_label": (
                f"{metrics['confirmed_quests_week']} закрытых за неделю, "
                f"{metrics['earned_badges']} трофеев"
            ),
        },
        {
            "id": "signals",
            "name": "Сеть Сигналов",
            "status": _faction_status(faction_map["keepers"]["trend"]),
            "progress_percent": _pct("keepers"),
            "dominant_faction_id": "keepers",
            "activity_label": (
                f"{metrics['unread_notifications']} активных сигналов, "
                f"{metrics['revision_requested_quests']} на ревизии"
            ),
        },
        {
            "id": "nexus",
            "name": "Нексус Рынка",
            "status": "active",
            "progress_percent": season_progress,
            "dominant_faction_id": leader["id"],
            "activity_label": (
                f"{metrics['total_users']} участников, "
                f"{metrics['open_quests']} открытых квестов"
            ),
        },
    ]


def _build_lore_beats(
    metrics: dict,
    leader: dict,
    season_stage: str,
    community_momentum: str,
) -> list[dict]:
    """Generate 1–4 lore narrative beats from the current platform state."""
    beats: list[dict] = []

    # Beat 1: season stage narrative
    if season_stage == "finale":
        beats.append({
            "id": "season_finale",
            "text": (
                f"Финальная глава сезона открыта. {leader['name']} ведёт к "
                "решающему закрытию платформенного цикла."
            ),
            "faction_id": leader["id"],
            "beat_type": "milestone",
        })
    elif season_stage == "ascent":
        beats.append({
            "id": "season_ascent",
            "text": (
                f"Сезон набирает обороты. {leader['name']} удерживает первенство "
                "в борьбе за ресурсы рынка."
            ),
            "faction_id": leader["id"],
            "beat_type": "narrative",
        })
    else:
        beats.append({
            "id": "season_muster",
            "text": (
                f"Новый сезон открывается. {leader['name']} первой поднимает стяг "
                "и задаёт направление рынка."
            ),
            "faction_id": leader["id"],
            "beat_type": "narrative",
        })

    # Beat 2: community pressure or quality milestone
    if community_momentum == "under_pressure":
        beats.append({
            "id": "community_pressure",
            "text": (
                f"Комьюнити под давлением: {metrics['revision_requested_quests']} "
                "открытых ревизий тормозят общий ритм прогресса."
            ),
            "faction_id": None,
            "beat_type": "warning",
        })
    elif metrics.get("avg_rating") is not None and metrics["avg_rating"] >= 4.7:
        beats.append({
            "id": "quality_milestone",
            "text": (
                f"Стандарт качества на высоте: средний рейтинг {metrics['avg_rating']}. "
                "Комьюнити работает чисто."
            ),
            "faction_id": "artisans",
            "beat_type": "milestone",
        })
    elif metrics["confirmed_quests_week"] > 0:
        beats.append({
            "id": "weekly_progress",
            "text": (
                f"{metrics['confirmed_quests_week']} квестов подтверждено за "
                "последнюю неделю. Рабочий ритм сохраняется."
            ),
            "faction_id": None,
            "beat_type": "narrative",
        })

    # Beat 3: urgent spike warning
    if metrics["open_quests"] > 0 and metrics["urgent_quests"] > metrics["open_quests"] * 0.3:
        beats.append({
            "id": "urgent_spike",
            "text": (
                f"Рост срочных контрактов: {metrics['urgent_quests']} из "
                f"{metrics['open_quests']} открытых помечены как критические."
            ),
            "faction_id": "vanguard",
            "beat_type": "warning",
        })

    # Fallback: always return at least one beat
    if not beats:
        beats.append({
            "id": "quiet_period",
            "text": (
                "Мир в спокойном состоянии. Новые квесты и участники накапливают "
                "потенциал для следующего сезонного цикла."
            ),
            "faction_id": None,
            "beat_type": "narrative",
        })

    return beats[:4]


# ============================================================
# Faction alignment contribution helpers — pure, testable
# ============================================================

def compute_alignment_contribution(faction_id: str, contribution_score: int) -> dict[str, int]:
    """Convert a single user's faction alignment into a keyed bonus dict.

    Returns {faction_id: bonus_points} where only the aligned faction receives
    the bonus; other factions get 0. Returns all-zero dict when faction_id is
    'none' or unrecognised.
    """
    result: dict[str, int] = {"vanguard": 0, "keepers": 0, "artisans": 0}
    if faction_id in result:
        result[faction_id] = max(0, min(contribution_score, 100))
    return result


def apply_alignment_bonuses(
    faction_rows: list[dict],
    bonuses: dict[str, int] | None,
) -> list[dict]:
    """Return faction_rows with optional per-faction bonus scores applied.

    Backward-compatible: when *bonuses* is None or empty every score is
    unchanged. Trend labels are NOT recomputed here — call the trend-labelling
    logic after this function if necessary.
    """
    if not bonuses:
        return faction_rows
    result = []
    for row in faction_rows:
        bonus = bonuses.get(row["id"], 0)
        result.append({**row, "score": row["score"] + bonus} if bonus else row)
    return result


async def get_world_meta(conn: asyncpg.Connection) -> dict:
    query = """
        SELECT
            (SELECT COUNT(*)::INT FROM users) AS total_users,
            (SELECT COUNT(*)::INT FROM users WHERE role = 'freelancer') AS freelancer_count,
            (SELECT COUNT(*)::INT FROM users WHERE role = 'client') AS client_count,
            (SELECT COUNT(*)::INT FROM quests WHERE status = 'open') AS open_quests,
            (SELECT COUNT(*)::INT FROM quests WHERE status = 'in_progress') AS in_progress_quests,
            (SELECT COUNT(*)::INT FROM quests WHERE status = 'revision_requested') AS revision_requested_quests,
            (SELECT COUNT(*)::INT FROM quests WHERE is_urgent = TRUE AND status IN ('open', 'assigned', 'in_progress', 'revision_requested')) AS urgent_quests,
            (SELECT COUNT(*)::INT FROM quests WHERE status = 'confirmed' AND completed_at >= NOW() - INTERVAL '7 days') AS confirmed_quests_week,
            (SELECT COUNT(*)::INT FROM notifications WHERE is_read = FALSE) AS unread_notifications,
            (SELECT COUNT(*)::INT FROM quest_reviews) AS total_reviews,
            (SELECT AVG(rating)::NUMERIC(3, 2) FROM quest_reviews) AS avg_rating,
            (SELECT COUNT(*)::INT FROM user_badges) AS earned_badges,
            (SELECT COUNT(*)::INT FROM quests WHERE status = 'confirmed' AND completed_at >= NOW() - INTERVAL '14 days' AND completed_at < NOW() - INTERVAL '7 days') AS previous_confirmed_quests_week,
            (SELECT COUNT(*)::INT FROM quests WHERE created_at >= NOW() - INTERVAL '7 days') AS new_quests_week,
            (SELECT COUNT(*)::INT FROM quests WHERE created_at >= NOW() - INTERVAL '14 days' AND created_at < NOW() - INTERVAL '7 days') AS previous_new_quests_week,
            (SELECT COUNT(*)::INT FROM notifications WHERE created_at >= NOW() - INTERVAL '7 days') AS notification_volume_week,
            (SELECT COUNT(*)::INT FROM notifications WHERE created_at >= NOW() - INTERVAL '14 days' AND created_at < NOW() - INTERVAL '7 days') AS previous_notification_volume_week
    """

    trend_history_query = """
        WITH days AS (
            SELECT generate_series(
                CURRENT_DATE - INTERVAL '6 days',
                CURRENT_DATE,
                INTERVAL '1 day'
            )::date AS day
        )
        SELECT
            TO_CHAR(days.day, 'DD Mon') AS label,
            COALESCE((
                SELECT COUNT(*)::INT
                FROM quests q
                WHERE q.status = 'confirmed'
                  AND q.completed_at >= days.day
                  AND q.completed_at < days.day + INTERVAL '1 day'
            ), 0) AS confirmed_quests,
            COALESCE((
                SELECT COUNT(*)::INT
                FROM quests q
                WHERE q.created_at >= days.day
                  AND q.created_at < days.day + INTERVAL '1 day'
            ), 0) AS new_quests,
            COALESCE((
                SELECT COUNT(*)::INT
                FROM notifications n
                WHERE n.created_at >= days.day
                  AND n.created_at < days.day + INTERVAL '1 day'
            ), 0) AS notification_volume
        FROM days
        ORDER BY days.day
    """

    with db_span("db.fetchrow", query=query, params=[]):
        row = await conn.fetchrow(query)
    with db_span("db.fetch", query=trend_history_query, params=[]):
        trend_rows = await conn.fetch(trend_history_query)

    metrics = {
        "total_users": _int_value(row, "total_users"),
        "freelancer_count": _int_value(row, "freelancer_count"),
        "client_count": _int_value(row, "client_count"),
        "open_quests": _int_value(row, "open_quests"),
        "in_progress_quests": _int_value(row, "in_progress_quests"),
        "revision_requested_quests": _int_value(row, "revision_requested_quests"),
        "urgent_quests": _int_value(row, "urgent_quests"),
        "confirmed_quests_week": _int_value(row, "confirmed_quests_week"),
        "unread_notifications": _int_value(row, "unread_notifications"),
        "total_reviews": _int_value(row, "total_reviews"),
        "avg_rating": round(float((row or {}).get("avg_rating")), 2) if row and (row.get("avg_rating") if isinstance(row, dict) else row["avg_rating"]) is not None else None,
        "earned_badges": _int_value(row, "earned_badges"),
    }

    if trend_rows:
        history_points = {
            "confirmed_quests": [
                {"label": trend_row["label"], "value": int(trend_row["confirmed_quests"] or 0)}
                for trend_row in trend_rows
            ],
            "new_quests": [
                {"label": trend_row["label"], "value": int(trend_row["new_quests"] or 0)}
                for trend_row in trend_rows
            ],
            "notification_volume": [
                {"label": trend_row["label"], "value": int(trend_row["notification_volume"] or 0)}
                for trend_row in trend_rows
            ],
        }
    else:
        history_points = {"confirmed_quests": [], "new_quests": [], "notification_volume": []}
        base_day = datetime.now(timezone.utc).date() - timedelta(days=6)
        for offset in range(7):
            label = (base_day + timedelta(days=offset)).strftime("%d %b")
            empty_point = {"label": label, "value": 0}
            history_points["confirmed_quests"].append(empty_point.copy())
            history_points["new_quests"].append(empty_point.copy())
            history_points["notification_volume"].append(empty_point.copy())

    trends = [
        _build_trend_metric(
            "confirmed_quests",
            "Confirmed quests",
            metrics["confirmed_quests_week"],
            _int_value(row, "previous_confirmed_quests_week"),
            history_points["confirmed_quests"],
        ),
        _build_trend_metric(
            "new_quests",
            "New quests",
            _int_value(row, "new_quests_week"),
            _int_value(row, "previous_new_quests_week"),
            history_points["new_quests"],
        ),
        _build_trend_metric(
            "notification_volume",
            "Notification volume",
            _int_value(row, "notification_volume_week"),
            _int_value(row, "previous_notification_volume_week"),
            history_points["notification_volume"],
        ),
    ]

    season_target = max(18, metrics["freelancer_count"] * 2, metrics["open_quests"] + metrics["in_progress_quests"])
    season_progress = 0 if season_target <= 0 else min(100, round(metrics["confirmed_quests_week"] / season_target * 100))

    now = datetime.now(timezone.utc)
    days_in_cycle = 30
    cycle_day = ((now.day - 1) % days_in_cycle) + 1
    days_left = max(0, days_in_cycle - cycle_day)

    vanguard_score = metrics["urgent_quests"] * 5 + metrics["open_quests"] * 2 + metrics["in_progress_quests"] * 3
    keepers_score = metrics["unread_notifications"] * 3 + metrics["revision_requested_quests"] * 4 + metrics["total_users"]
    artisans_score = metrics["confirmed_quests_week"] * 4 + metrics["total_reviews"] * 2 + metrics["earned_badges"]

    faction_rows = [
        {
            "id": "vanguard",
            "name": "Фракция Авангарда",
            "focus": f"{metrics['urgent_quests']} срочных контрактов и {metrics['in_progress_quests']} активных рейдов держат давление рынка.",
            "score": vanguard_score,
        },
        {
            "id": "keepers",
            "name": "Хранители Потока",
            "focus": f"{metrics['unread_notifications']} непрочитанных сигналов и {metrics['revision_requested_quests']} циклов доработки требуют контроля.",
            "score": keepers_score,
        },
        {
            "id": "artisans",
            "name": "Дом Ремесленников",
            "focus": f"{metrics['confirmed_quests_week']} подтверждённых квестов за неделю и {metrics['earned_badges']} собранных трофеев формируют репутацию.",
            "score": artisans_score,
        },
    ]

    max_score = max((row_item["score"] for row_item in faction_rows), default=0)
    leader = next((row_item for row_item in faction_rows if row_item["score"] == max_score), faction_rows[0])

    for row_item in faction_rows:
        if max_score <= 0:
            trend = "stable"
        elif row_item["score"] >= max_score * 0.9:
            trend = "surging"
        elif row_item["score"] >= max_score * 0.6:
            trend = "holding"
        else:
            trend = "recovering"
        row_item["trend"] = trend

    if leader["id"] == "vanguard":
        season_title = "Season of Ember Contracts"
    elif leader["id"] == "keepers":
        season_title = "Season of Quiet Signals"
    else:
        season_title = "Season of Reputation Forge"

    if season_progress >= 75:
        season_stage = "finale"
    elif season_progress >= 35:
        season_stage = "ascent"
    else:
        season_stage = "muster"

    community_target = max(12, metrics["confirmed_quests_week"] + metrics["revision_requested_quests"] + 6)
    community_current = metrics["confirmed_quests_week"]

    if metrics["avg_rating"] is not None and metrics["avg_rating"] >= 4.7:
        headline = f"Комьюнити держит высокий стандарт качества: средний рейтинг {metrics['avg_rating']}."
        momentum = "rising"
    elif metrics["revision_requested_quests"] > metrics["confirmed_quests_week"]:
        headline = "Комьюнити упёрлось в доработки: качество коммуникации важнее скорости публикации."
        momentum = "under_pressure"
    else:
        headline = f"За последнюю неделю подтверждено {metrics['confirmed_quests_week']} квестов, гильдия держит рабочий ритм."
        momentum = "steady"

    season_extras = _build_season_extras(season_stage, season_progress)
    regions = _build_regions(metrics, faction_rows, leader, season_progress)
    lore_beats = _build_lore_beats(metrics, leader, season_stage, momentum)

    return {
        "season": {
            "id": leader["id"],
            "title": season_title,
            "stage": season_stage,
            "progress_percent": season_progress,
            "completed_quests_week": metrics["confirmed_quests_week"],
            "target_quests_week": season_target,
            "days_left": days_left,
            "chapter": season_extras["chapter"],
            "stage_description": season_extras["stage_description"],
            "next_unlock": season_extras["next_unlock"],
        },
        "factions": faction_rows,
        "leading_faction_id": leader["id"],
        "community": {
            "headline": headline,
            "momentum": momentum,
            "target_label": "weekly confirmed quests",
            "current_value": community_current,
            "target_value": community_target,
        },
        "metrics": metrics,
        "trends": trends,
        "regions": regions,
        "lore_beats": lore_beats,
        "generated_at": now,
    }