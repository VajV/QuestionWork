"""
Quest business-logic service.

Extracts logic from endpoint handlers into testable, reusable functions.
All multi-table mutations are wrapped in explicit DB transactions.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

import asyncpg

from app.core.otel_utils import db_span
from app.core.rewards import (
    allocate_stat_points,
    calculate_quest_rewards,
    calculate_xp_reward,
    calculate_xp_to_next,
    check_level_up,
    get_grade_level,
)
from app.core.classes import should_block_quest
from app.models.quest import (
    Quest,
    QuestApplication,
    QuestApplicationCreate,
    QuestCreate,
    QuestListResponse,
    QuestStatusEnum,
)
from app.services import wallet_service, badge_service, notification_service, class_service
from app.models.user import GradeEnum, UserProfile, row_to_user_profile

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────
# Row → Pydantic helpers
# ────────────────────────────────────────────

def row_to_quest(row, applications: list[str] | None = None) -> Quest:
    """Convert an asyncpg Record to a Quest Pydantic model."""
    return Quest(
        id=row["id"],
        client_id=row["client_id"],
        client_username=row["client_username"],
        title=row["title"],
        description=row["description"],
        required_grade=GradeEnum(row["required_grade"]),
        skills=json.loads(row["skills"]) if row["skills"] else [],
        budget=float(row["budget"]),
        currency=row["currency"],
        xp_reward=row["xp_reward"],
        status=QuestStatusEnum(row["status"]),
        applications=applications if applications is not None else [],
        assigned_to=row["assigned_to"],
        is_urgent=row.get("is_urgent", False),
        deadline=row.get("deadline"),
        required_portfolio=row.get("required_portfolio", False),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
    )


async def _fetch_quest_applications(conn: asyncpg.Connection, quest_id: str) -> list[str]:
    """Return list of freelancer_ids who applied to a quest."""
    rows = await conn.fetch(
        "SELECT freelancer_id FROM applications WHERE quest_id = $1", quest_id
    )
    return [r["freelancer_id"] for r in rows]


# ────────────────────────────────────────────
# Read operations
# ────────────────────────────────────────────

async def list_quests(
    conn: asyncpg.Connection,
    *,
    page: int = 1,
    page_size: int = 10,
    status_filter: Optional[QuestStatusEnum] = None,
    grade_filter: Optional[GradeEnum] = None,
    skill_filter: Optional[str] = None,
    min_budget: Optional[float] = None,
    max_budget: Optional[float] = None,
) -> QuestListResponse:
    """List quests with optional filters and pagination."""
    query = "SELECT * FROM quests WHERE 1=1"
    args: list = []
    arg_idx = 1

    if status_filter:
        query += f" AND status = ${arg_idx}"
        args.append(status_filter.value)
        arg_idx += 1
    if grade_filter:
        query += f" AND required_grade = ${arg_idx}"
        args.append(grade_filter.value)
        arg_idx += 1
    if skill_filter:
        query += f" AND skills::jsonb @> ${arg_idx}::jsonb"
        args.append(json.dumps([skill_filter]))
        arg_idx += 1
    if min_budget is not None:
        query += f" AND budget >= ${arg_idx}"
        args.append(min_budget)
        arg_idx += 1
    if max_budget is not None:
        query += f" AND budget <= ${arg_idx}"
        args.append(max_budget)
        arg_idx += 1

    count_query = f"SELECT COUNT(*) FROM ({query}) as count_query"
    with db_span("db.fetchval", query=count_query, params=args):
        total = await conn.fetchval(count_query, *args)

    query += f" ORDER BY created_at DESC LIMIT ${arg_idx} OFFSET ${arg_idx + 1}"
    args.extend([page_size, (page - 1) * page_size])

    with db_span("db.fetch", query=query, params=args):
        rows = await conn.fetch(query, *args)

    # Batch-fetch applications (fix N+1)
    quest_ids = [row["id"] for row in rows]
    apps_map: dict[str, list[str]] = {qid: [] for qid in quest_ids}
    if quest_ids:
        app_rows = await conn.fetch(
            "SELECT quest_id, freelancer_id FROM applications WHERE quest_id = ANY($1)",
            quest_ids,
        )
        for ar in app_rows:
            apps_map[ar["quest_id"]].append(ar["freelancer_id"])

    quests = [row_to_quest(row, apps_map.get(row["id"], [])) for row in rows]
    safe_total = int(total or 0)

    return QuestListResponse(
        quests=quests,
        total=safe_total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < safe_total,
    )


async def get_quest_by_id(conn: asyncpg.Connection, quest_id: str) -> Optional[Quest]:
    """Fetch a single quest by ID, including applications list."""
    row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not row:
        return None
    apps = await _fetch_quest_applications(conn, quest_id)
    return row_to_quest(row, apps)


# ────────────────────────────────────────────
# Create quest
# ────────────────────────────────────────────

async def create_quest(
    conn: asyncpg.Connection,
    quest_data: QuestCreate,
    current_user: UserProfile,
) -> Quest:
    """Insert a new quest. Returns the created Quest model."""
    xp_reward = quest_data.xp_reward
    if xp_reward is None:
        xp_reward = calculate_xp_reward(
            budget=quest_data.budget,
            quest_grade=quest_data.required_grade,
            user_grade=GradeEnum.novice,
        )

    quest_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await conn.execute(
        """
        INSERT INTO quests (
            id, client_id, client_username, title, description, required_grade,
            skills, budget, currency, xp_reward, status,
            is_urgent, deadline, required_portfolio,
            created_at, updated_at
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
        """,
        quest_id,
        current_user.id,
        current_user.username,
        quest_data.title,
        quest_data.description,
        quest_data.required_grade.value,
        json.dumps(quest_data.skills),
        quest_data.budget,
        quest_data.currency,
        xp_reward,
        QuestStatusEnum.open.value,
        quest_data.is_urgent,
        quest_data.deadline,
        quest_data.required_portfolio,
        now,
        now,
    )

    return Quest(
        id=quest_id,
        client_id=current_user.id,
        client_username=current_user.username,
        title=quest_data.title,
        description=quest_data.description,
        required_grade=quest_data.required_grade,
        skills=quest_data.skills,
        budget=quest_data.budget,
        currency=quest_data.currency,
        xp_reward=xp_reward,
        status=QuestStatusEnum.open,
        applications=[],
        assigned_to=None,
        is_urgent=quest_data.is_urgent,
        deadline=quest_data.deadline,
        required_portfolio=quest_data.required_portfolio,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )


# ────────────────────────────────────────────
# Apply to quest
# ────────────────────────────────────────────

async def apply_to_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    application_data: QuestApplicationCreate,
    current_user: UserProfile,
) -> QuestApplication:
    """Validate preconditions and insert an application. Returns the application."""
    quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise ValueError("Quest not found")

    if quest["status"] != QuestStatusEnum.open.value:
        raise ValueError(f"Cannot apply to quest with status: {quest['status']}")

    if quest["client_id"] == current_user.id:
        raise ValueError("Cannot apply to your own quest")

    existing = await conn.fetchrow(
        "SELECT id FROM applications WHERE quest_id = $1 AND freelancer_id = $2",
        quest_id,
        current_user.id,
    )
    if existing:
        raise ValueError("You have already applied to this quest")

    quest_required_grade = GradeEnum(quest["required_grade"])
    if get_grade_level(GradeEnum(current_user.grade)) < get_grade_level(quest_required_grade):
        raise ValueError(
            f"Your grade ({current_user.grade}) is lower than required ({quest_required_grade})"
        )

    # Phase 2: class-based quest blocking (e.g. Berserker can't take portfolio quests)
    required_portfolio = bool(quest.get("requires_portfolio", False))
    if should_block_quest(current_user.character_class, required_portfolio=required_portfolio):
        raise ValueError("Ваш класс не позволяет брать квесты с обязательным портфолио")

    application_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Wrap INSERT + UPDATE in a transaction to avoid orphaned applications
    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO applications (
                id, quest_id, freelancer_id, freelancer_username, freelancer_grade,
                cover_letter, proposed_price, created_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """,
            application_id,
            quest_id,
            current_user.id,
            current_user.username,
            str(current_user.grade),
            application_data.cover_letter,
            application_data.proposed_price,
            now,
        )

        await conn.execute("UPDATE quests SET updated_at = $1 WHERE id = $2", now, quest_id)

    return QuestApplication(
        id=application_id,
        quest_id=quest_id,
        freelancer_id=current_user.id,
        freelancer_username=current_user.username,
        freelancer_grade=current_user.grade,
        cover_letter=application_data.cover_letter,
        proposed_price=application_data.proposed_price,
        created_at=now,
    )


# ────────────────────────────────────────────
# Assign freelancer
# ────────────────────────────────────────────

async def assign_freelancer(
    conn: asyncpg.Connection,
    quest_id: str,
    freelancer_id: str,
    current_user: UserProfile,
) -> Quest:
    """Assign a freelancer to a quest. Returns updated Quest."""
    async with conn.transaction():
        # Lock the quest row to prevent concurrent assignment
        quest = await conn.fetchrow(
            "SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")

        if quest["client_id"] != current_user.id:
            raise PermissionError("Only client can assign freelancer")

        if quest["status"] != QuestStatusEnum.open.value:
            raise ValueError(f"Cannot assign freelancer to quest with status: {quest['status']}")

        app = await conn.fetchrow(
            "SELECT id FROM applications WHERE quest_id = $1 AND freelancer_id = $2",
            quest_id,
            freelancer_id,
        )
        if not app:
            raise ValueError("This user has not applied to the quest")

        now = datetime.now(timezone.utc)
        await conn.execute(
            "UPDATE quests SET assigned_to = $1, status = $2, updated_at = $3 WHERE id = $4",
            freelancer_id,
            QuestStatusEnum.in_progress.value,
            now,
            quest_id,
        )

        updated_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
        apps = await _fetch_quest_applications(conn, quest_id)
    return row_to_quest(updated_row, apps)


# ────────────────────────────────────────────
# Mark quest complete (freelancer)
# ────────────────────────────────────────────

async def mark_quest_complete(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> Tuple[Quest, int]:
    """Freelancer marks a quest as completed. Returns (quest, xp_reward)."""
    async with conn.transaction():
        # Lock quest to prevent concurrent status changes
        quest = await conn.fetchrow(
            "SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")

        if quest["status"] != QuestStatusEnum.in_progress.value:
            raise ValueError("Can only complete quest that is in progress")

        if quest["assigned_to"] != current_user.id:
            raise PermissionError("Only assigned freelancer can complete quest")

        now = datetime.now(timezone.utc)
        await conn.execute(
            "UPDATE quests SET status = $1, completed_at = $2, updated_at = $3 WHERE id = $4",
            QuestStatusEnum.completed.value,
            now,
            now,
            quest_id,
        )

        updated_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
        apps = await _fetch_quest_applications(conn, quest_id)
    return row_to_quest(updated_row, apps), quest["xp_reward"]


# ────────────────────────────────────────────
# Confirm quest completion (client) — ATOMIC
# ────────────────────────────────────────────

async def confirm_quest_completion(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> dict:
    """
    Client confirms quest completion.

    **All mutations run inside a DB transaction** so that a failure at any
    step causes a full rollback (XP, wallet, transaction log).
    """
    # ── Pre-checks (read-only) ────────────────────
    quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise ValueError("Quest not found")

    if quest["client_id"] != current_user.id:
        raise PermissionError("Only client can confirm completion")

    if quest["status"] != QuestStatusEnum.completed.value:
        raise ValueError("Quest has not been marked as completed by freelancer")

    # Guard: if already confirmed, reject (prevents double-payment)
    if quest["status"] == QuestStatusEnum.confirmed.value:
        raise ValueError("Quest has already been confirmed and paid")

    freelancer_row = await conn.fetchrow(
        "SELECT * FROM users WHERE id = $1", quest["assigned_to"]
    )
    if not freelancer_row:
        raise ValueError(f"Freelancer not found: {quest['assigned_to']}")

    # ── Calculate rewards ────────────────────
    quest_grade = GradeEnum(quest["required_grade"])
    freelancer_grade = GradeEnum(freelancer_row["grade"])

    xp_reward = calculate_quest_rewards(
        budget=float(quest["budget"]),
        quest_grade=quest_grade,
        user_grade=freelancer_grade,
    )

    old_level = freelancer_row["level"]
    new_xp = freelancer_row["xp"] + xp_reward
    level_up, new_grade, new_level = check_level_up(new_xp, freelancer_grade)
    new_xp_to_next = calculate_xp_to_next(new_xp, new_grade)

    # Stat growth on level-up
    levels_gained = max(0, new_level - old_level)
    stat_delta = allocate_stat_points(levels_gained) if levels_gained > 0 else {"int": 0, "dex": 0, "cha": 0, "unspent": 0}
    new_stats_int = freelancer_row["stats_int"] + stat_delta["int"]
    new_stats_dex = freelancer_row["stats_dex"] + stat_delta["dex"]
    new_stats_cha = freelancer_row["stats_cha"] + stat_delta["cha"]
    new_stat_points = freelancer_row.get("stat_points", 0) + stat_delta["unspent"]

    now = datetime.now(timezone.utc)

    # ── Atomic transaction ────────────────────
    async with conn.transaction():
        # 0. Lock quest row and flip status to 'confirmed' FIRST to prevent double-payment
        updated = await conn.fetchval(
            "UPDATE quests SET status = $1, updated_at = $2 WHERE id = $3 AND status = $4 RETURNING id",
            QuestStatusEnum.confirmed.value,
            now,
            quest_id,
            QuestStatusEnum.completed.value,
        )
        if not updated:
            raise ValueError("Quest was already confirmed or status changed concurrently")

        # 1. Update freelancer XP / grade / stats
        await conn.execute(
            """
            UPDATE users
            SET xp = $1, level = $2, grade = $3, xp_to_next = $4,
                stats_int = $5, stats_dex = $6, stats_cha = $7,
                stat_points = stat_points + $8,
                updated_at = $9
            WHERE id = $10
            """,
            new_xp,
            new_level,
            new_grade.value,
            new_xp_to_next,
            new_stats_int,
            new_stats_dex,
            new_stats_cha,
            stat_delta["unspent"],
            now,
            quest["assigned_to"],
        )

        # 2. Split payment: freelancer gets (100 - fee)%, platform gets fee%
        split = await wallet_service.split_payment(
            conn,
            client_id=quest["client_id"],
            freelancer_id=quest["assigned_to"],
            gross_amount=float(quest["budget"]),
            currency=quest["currency"],
            quest_id=quest_id,
        )

        # 3. Badge check — count confirmed quests for freelancer
        #    (status is already 'confirmed' for this quest after step 0)
        completed_count_row = await conn.fetchval(
            "SELECT COUNT(*) FROM quests WHERE assigned_to = $1 AND status = $2",
            quest["assigned_to"],
            QuestStatusEnum.confirmed.value,
        )
        quests_completed = int(completed_count_row or 0)  # already includes this one
        badge_event_data = {
            "quests_completed": quests_completed,
            "xp": new_xp,
            "level": new_level,
            "grade": new_grade.value,
            "earnings": float(split["freelancer_amount"]),
        }
        award_result = await badge_service.check_and_award(
            conn, quest["assigned_to"], "quest_completed", badge_event_data
        )

        # 4. Notify freelancer: quest confirmed
        await notification_service.create_notification(
            conn,
            user_id=quest["assigned_to"],
            title="Quest Confirmed!",
            message=(
                f"Your quest '{quest['title']}' has been confirmed. "
                f"You received {split['freelancer_amount']} {quest['currency']} "
                f"and {xp_reward} XP."
            ),
            event_type="quest_confirmed",
        )

        # 5. Notify freelancer: each newly earned badge
        for earned in award_result.newly_earned:
            await notification_service.create_notification(
                conn,
                user_id=quest["assigned_to"],
                title=f"Badge Earned: {earned.badge_name}",
                message=earned.badge_description,
                event_type="badge_earned",
            )

        # 6. Class XP progression (if freelancer has a class)
        class_result = await class_service.add_class_xp(
            conn,
            quest["assigned_to"],
            xp_reward,
            is_urgent=quest.get("is_urgent", False),
            required_portfolio=quest.get("required_portfolio", False),
        )

    logger.info(
        f"Quest {quest_id} confirmed. Freelancer {freelancer_row['username']}: "
        f"+{xp_reward} XP, +{split['freelancer_amount']} {quest['currency']} "
        f"(platform fee {split['platform_fee']} = {split['fee_percent']}%)"
    )

    return {
        "message": "Quest confirmed! Reward has been paid.",
        "xp_reward": xp_reward,
        "money_reward": split["freelancer_amount"],
        "platform_fee": split["platform_fee"],
        "fee_percent": split["fee_percent"],
        "level_up": level_up,
        "new_level": new_level,
        "new_grade": new_grade.value,
        "stat_delta": stat_delta,
        "freelancer_username": freelancer_row["username"],
        "badges_earned": [
            {"id": b.badge_id, "name": b.badge_name, "description": b.badge_description}
            for b in award_result.newly_earned
        ],
        "class_xp_gained": class_result.get("class_xp_gained", 0),
        "class_level_up": class_result.get("class_level_up", False),
    }


# ────────────────────────────────────────────
# Cancel quest
# ────────────────────────────────────────────

async def cancel_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> dict:
    """Cancel a quest. Only the client-owner can cancel."""
    quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise ValueError("Quest not found")

    if quest["client_id"] != current_user.id:
        raise PermissionError("Only client can cancel quest")

    if quest["status"] in [QuestStatusEnum.completed.value, QuestStatusEnum.confirmed.value, QuestStatusEnum.cancelled.value]:
        raise ValueError(f"Cannot cancel quest with status: {quest['status']}")

    now = datetime.now(timezone.utc)
    await conn.execute(
        "UPDATE quests SET status = $1, updated_at = $2 WHERE id = $3",
        QuestStatusEnum.cancelled.value,
        now,
        quest_id,
    )
    return {"message": "Quest cancelled successfully"}


# ────────────────────────────────────────────
# Get applications
# ────────────────────────────────────────────

async def get_quest_applications(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> dict:
    """Return applications for a quest. Only the quest owner can see them."""
    quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise ValueError("Quest not found")

    if quest["client_id"] != current_user.id:
        raise PermissionError("Only client can view applications")

    rows = await conn.fetch(
        "SELECT * FROM applications WHERE quest_id = $1 ORDER BY created_at DESC",
        quest_id,
    )

    applications = [
        QuestApplication(
            id=row["id"],
            quest_id=row["quest_id"],
            freelancer_id=row["freelancer_id"],
            freelancer_username=row["freelancer_username"],
            freelancer_grade=GradeEnum(row["freelancer_grade"]),
            cover_letter=row["cover_letter"],
            proposed_price=float(row["proposed_price"]) if row["proposed_price"] else None,
            created_at=row["created_at"],
        )
        for row in rows
    ]

    return {"applications": applications, "total": len(applications)}
