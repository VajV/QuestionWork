"""
Quest business-logic service.

Extracts logic from endpoint handlers into testable, reusable functions.
All multi-table mutations are wrapped in explicit DB transactions.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple

import asyncpg

from app.core.otel_utils import db_span
from app.core.rewards import (
    allocate_stat_points,
    calculate_quest_rewards,
    calculate_training_xp_reward,
    calculate_xp_reward,
    calculate_xp_to_next,
    check_level_up,
    get_grade_level,
    TRAINING_BUDGET,
    TRAINING_DAILY_XP_CAP,
    TRAINING_MAX_XP,
    TRAINING_MIN_XP,
)
from app.core.classes import should_block_quest, get_class_config, BonusType, calculate_class_xp_multiplier
from app.models.quest import (
    Quest,
    QuestApplication,
    QuestApplicationCreate,
    QuestCompletionCreate,
    QuestCreate,
    QuestListResponse,
    QuestRevisionRequest,
    QuestStatusHistoryEntry,
    QuestUpdate,
    QuestStatusEnum,
    TrainingQuestCreate,
    RaidParticipant,
    RaidQuestCreate,
    RaidPartyResponse,
    ChainStatusEnum,
    QuestChain,
    ChainStep,
    UserChainProgress,
    QuestChainCreate,
    ChainDetailResponse,
    ChainListResponse,
)
from app.services import wallet_service, badge_service, notification_service, class_service, message_service, guild_economy_service, trust_score_service
from app.services.quest_helpers import record_quest_status_history as _record_status_history
from app.models.user import GradeEnum, UserProfile, row_to_user_profile

logger = logging.getLogger(__name__)

# Default number of active quest slots per freelancer; class bonuses can increase this
BASE_QUEST_SLOTS = 3
STAT_CAP = 100
# Maximum active quests a client can have open/assigned/in_progress at once
MAX_CLIENT_ACTIVE_QUESTS = 20
DEADLINE_PENALTY_BASE_RATE = 0.15
DEADLINE_PENALTY_DAILY_STEP_RATE = 0.05
DEADLINE_PENALTY_MAX_RATE = 0.50
CANCEL_XP_PENALTY_RATE = 0.20


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
        budget=row["budget"],
        currency=row["currency"],
        xp_reward=row["xp_reward"],
        status=QuestStatusEnum(row["status"]),
        applications=applications if applications is not None else [],
        assigned_to=row["assigned_to"],
        quest_type=row.get("quest_type", "standard"),
        raid_max_members=row.get("raid_max_members"),
        raid_current_members=row.get("raid_current_members", 0),
        chain_id=row.get("chain_id"),
        chain_step_order=row.get("chain_step_order"),
        is_urgent=row.get("is_urgent", False),
        deadline=row.get("deadline"),
        required_portfolio=row.get("required_portfolio", False),
        delivery_note=row.get("delivery_note"),
        delivery_url=row.get("delivery_url"),
        delivery_submitted_at=row.get("delivery_submitted_at"),
        revision_reason=row.get("revision_reason"),
        revision_requested_at=row.get("revision_requested_at"),
        platform_fee_percent=row.get("platform_fee_percent"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
    )


def row_to_history_entry(row) -> QuestStatusHistoryEntry:
    return QuestStatusHistoryEntry(
        id=row["id"],
        quest_id=row["quest_id"],
        from_status=QuestStatusEnum(row["from_status"]) if row.get("from_status") else None,
        to_status=QuestStatusEnum(row["to_status"]),
        changed_by=row.get("changed_by"),
        changed_by_username=row.get("changed_by_username"),
        note=row.get("note"),
        created_at=row["created_at"],
    )


async def _fetch_quest_applications(conn: asyncpg.Connection, quest_id: str) -> list[str]:
    """Return list of freelancer_ids who applied to a quest."""
    rows = await conn.fetch(
        "SELECT freelancer_id FROM applications WHERE quest_id = $1", quest_id
    )
    return [r["freelancer_id"] for r in rows]


# _record_status_history is imported from app.services.quest_helpers


def _calculate_deadline_penalty_rate(
    deadline: Optional[datetime],
    delivered_at: Optional[datetime],
) -> float:
    if not deadline or not delivered_at or delivered_at <= deadline:
        return 0.0

    overdue_seconds = (delivered_at - deadline).total_seconds()
    overdue_days = int(overdue_seconds // 86400)
    penalty_rate = DEADLINE_PENALTY_BASE_RATE + (overdue_days * DEADLINE_PENALTY_DAILY_STEP_RATE)
    return min(DEADLINE_PENALTY_MAX_RATE, penalty_rate)


def _apply_xp_penalty(xp_amount: int, penalty_rate: float) -> int:
    if xp_amount <= 0 or penalty_rate <= 0:
        return max(0, xp_amount)
    safe_penalty = min(1.0, max(0.0, penalty_rate))
    return max(1, int(xp_amount * (1.0 - safe_penalty)))


def _calculate_cancel_xp_penalty(xp_reward: int) -> int:
    if xp_reward <= 0:
        return 0
    return max(1, int(xp_reward * CANCEL_XP_PENALTY_RATE))


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
    min_budget: Optional[Decimal] = None,
    max_budget: Optional[Decimal] = None,
    user_id: Optional[str] = None,
    current_user: Optional[UserProfile] = None,
) -> QuestListResponse:
    """List quests with optional filters and pagination."""
    query = "SELECT * FROM quests WHERE 1=1"
    args: list = []
    arg_idx = 1

    allow_owner_drafts = bool(
        user_id
        and current_user
        and (current_user.role == "admin" or current_user.id == user_id)
    )

    if not allow_owner_drafts and status_filter != QuestStatusEnum.draft:
        query += " AND status <> 'draft'"

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
    if user_id:
        query += f" AND (client_id = ${arg_idx} OR assigned_to = ${arg_idx})"
        args.append(user_id)
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


async def get_quest_by_id(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: Optional[UserProfile] = None,
) -> Optional[Quest]:
    """Fetch a single quest by ID, including applications list."""
    row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not row:
        return None
    if row["status"] == QuestStatusEnum.draft.value:
        is_owner = current_user and current_user.id == row["client_id"]
        is_admin = current_user and current_user.role == "admin"
        if not (is_owner or is_admin):
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
    initial_status = QuestStatusEnum(quest_data.status)

    from app.core.config import settings as _settings
    fee_snapshot = Decimal(_settings.PLATFORM_FEE_PERCENT)

    async with conn.transaction():
        # P1-1 FIX: Enforce active quest limit per client
        active_client_quests = await conn.fetchval(
            "SELECT COUNT(*) FROM quests WHERE client_id = $1 AND status IN ('open', 'assigned', 'in_progress', 'completed', 'revision_requested')",
            current_user.id,
        )
        if active_client_quests >= MAX_CLIENT_ACTIVE_QUESTS:
            raise ValueError(f"Превышен лимит активных квестов ({MAX_CLIENT_ACTIVE_QUESTS}). Завершите или отмените существующие.")

        await conn.execute(
            """
            INSERT INTO quests (
                id, client_id, client_username, title, description, required_grade,
                skills, budget, currency, xp_reward, status,
                is_urgent, deadline, required_portfolio,
                platform_fee_percent,
                created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
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
            initial_status.value,
            quest_data.is_urgent,
            quest_data.deadline,
            quest_data.required_portfolio,
            fee_snapshot,
            now,
            now,
        )
        await _record_status_history(
            conn,
            quest_id,
            None,
            initial_status.value,
            changed_by=current_user.id,
            note="Quest created",
            created_at=now,
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
        status=initial_status,
        applications=[],
        assigned_to=None,
        is_urgent=quest_data.is_urgent,
        deadline=quest_data.deadline,
        required_portfolio=quest_data.required_portfolio,
        delivery_note=None,
        delivery_url=None,
        delivery_submitted_at=None,
        revision_reason=None,
        revision_requested_at=None,
        platform_fee_percent=fee_snapshot,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )


async def update_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    quest_data: QuestUpdate,
    current_user: UserProfile,
) -> Quest:
    """Update a draft/open quest owned by the client or admin."""
    updates = {k: v for k, v in quest_data.model_dump().items() if v is not None}
    if not updates:
        raise ValueError("No fields to update")

    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT id, client_id, status, assigned_to FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")
        if current_user.role != "admin" and quest["client_id"] != current_user.id:
            raise PermissionError("Only quest owner can update quest")
        if quest["status"] not in (QuestStatusEnum.draft.value, QuestStatusEnum.open.value):
            raise ValueError("Only draft or open quest can be edited")
        if quest["assigned_to"]:
            raise ValueError("Cannot edit quest after freelancer assignment")

        field_map = {
            "title": "title",
            "description": "description",
            "required_grade": "required_grade",
            "skills": "skills",
            "budget": "budget",
            "xp_reward": "xp_reward",
        }
        set_parts = []
        values = []
        idx = 1
        for key, column in field_map.items():
            if key in updates:
                value = updates[key]
                if key == "required_grade":
                    value = value.value
                if key == "skills":
                    value = json.dumps(value)
                set_parts.append(f"{column} = ${idx}")
                values.append(value)
                idx += 1

        set_parts.append(f"updated_at = ${idx}")
        values.append(datetime.now(timezone.utc))
        idx += 1
        values.append(quest_id)

        await conn.execute(
            f"UPDATE quests SET {', '.join(set_parts)} WHERE id = ${idx}",
            *values,
        )
        updated_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)

    apps = await _fetch_quest_applications(conn, quest_id)
    return row_to_quest(updated_row, apps)


async def publish_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> Quest:
    """Publish a draft quest to the public board."""
    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT id, client_id, status FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")
        if current_user.role != "admin" and quest["client_id"] != current_user.id:
            raise PermissionError("Only quest owner can publish quest")
        if quest["status"] != QuestStatusEnum.draft.value:
            raise ValueError("Only draft quest can be published")

        now = datetime.now(timezone.utc)
        await conn.execute(
            "UPDATE quests SET status = $1, updated_at = $2 WHERE id = $3",
            QuestStatusEnum.open.value,
            now,
            quest_id,
        )
        await _record_status_history(
            conn,
            quest_id,
            QuestStatusEnum.draft.value,
            QuestStatusEnum.open.value,
            changed_by=current_user.id,
            note="Quest published to marketplace",
            created_at=now,
        )
        updated_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)

    apps = await _fetch_quest_applications(conn, quest_id)
    return row_to_quest(updated_row, apps)


async def get_quest_status_history(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: Optional[UserProfile] = None,
) -> list[QuestStatusHistoryEntry]:
    """Return quest status history timeline."""
    quest = await conn.fetchrow("SELECT id, client_id, assigned_to, status FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise ValueError("Quest not found")

    is_participant = current_user and current_user.id in {
        quest["client_id"],
        quest["assigned_to"],
    }
    is_admin = current_user and current_user.role == "admin"
    if not (is_participant or is_admin):
        raise PermissionError("Only quest participants or admins can view quest history")

    rows = await conn.fetch(
        """
        SELECT h.id, h.quest_id, h.from_status, h.to_status, h.changed_by,
               u.username AS changed_by_username, h.note, h.created_at
        FROM quest_status_history h
        LEFT JOIN users u ON u.id = h.changed_by
        WHERE h.quest_id = $1
        ORDER BY h.created_at ASC
        """,
        quest_id,
    )
    return [row_to_history_entry(row) for row in rows]


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
    if current_user.is_banned:
        raise PermissionError("Banned users cannot apply to quests")

    application_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Wrap read + validation + write in a single transaction to prevent TOCTOU races
    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT id, status, client_id, required_grade, required_portfolio, is_urgent FROM quests WHERE id = $1 FOR SHARE", quest_id
        )
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
        required_portfolio = bool(quest.get("required_portfolio", False))
        is_urgent = bool(quest.get("is_urgent", False))
        if should_block_quest(
            current_user.character_class,
            required_portfolio=required_portfolio,
            is_urgent=is_urgent
        ):
            raise ValueError("Ваш класс не позволяет брать этот квест (ограничение по портфолио или срочности)")

        # R-04: Enforce quest slot limit
        active_count = await conn.fetchval(
            "SELECT COUNT(*) FROM quests WHERE assigned_to = $1 AND status IN ('assigned', 'in_progress')",
            current_user.id,
        )
        max_slots = BASE_QUEST_SLOTS
        if current_user.character_class:
            cfg = get_class_config(current_user.character_class)
            if cfg:
                max_slots += int(cfg.passive_bonuses.get(BonusType.extra_quest_slot, 0))
        if active_count >= max_slots:
            raise ValueError(f"Quest slot limit reached ({max_slots}). Complete active quests first.")

        # P2 Q-03 FIX: Catch UniqueViolationError from idx_applications_quest_freelancer
        # as a final safety net against TOCTOU race on concurrent apply calls.
        try:
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
        except asyncpg.UniqueViolationError:
            raise ValueError("You have already applied to this quest")

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
            "SELECT id, client_id, status, budget, currency, title FROM quests WHERE id = $1 FOR UPDATE", quest_id
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

        # R-04: Enforce quest slot limit for the freelancer being assigned
        active_count = await conn.fetchval(
            "SELECT COUNT(*) FROM quests WHERE assigned_to = $1 AND status IN ('assigned', 'in_progress')",
            freelancer_id,
        )
        freelancer_row_slot = await conn.fetchrow(
            "SELECT username, character_class, is_banned FROM users WHERE id = $1",
            freelancer_id,
        )
        if not freelancer_row_slot:
            raise ValueError("Freelancer not found")
        if freelancer_row_slot.get("is_banned"):
            raise PermissionError("Banned users cannot be assigned to quests")

        max_slots = BASE_QUEST_SLOTS
        if freelancer_row_slot.get("character_class"):
            cfg = get_class_config(freelancer_row_slot["character_class"])
            if cfg:
                max_slots += int(cfg.passive_bonuses.get(BonusType.extra_quest_slot, 0))
        if active_count >= max_slots:
            raise ValueError(f"Freelancer has reached quest slot limit ({max_slots})")

        # Reset consecutive quest streak if stale (>24h gap)
        await class_service.reset_consecutive_if_stale(conn, freelancer_id)

        now = datetime.now(timezone.utc)

        # P0-1 FIX: Escrow — hold the quest budget from client's wallet
        await wallet_service.hold(
            conn,
            user_id=current_user.id,
            amount=quest["budget"],
            currency=quest["currency"],
            quest_id=quest_id,
        )

        await conn.execute(
            "UPDATE quests SET assigned_to = $1, status = $2, updated_at = $3 WHERE id = $4",
            freelancer_id,
            QuestStatusEnum.assigned.value,
            now,
            quest_id,
        )
        await _record_status_history(
            conn,
            quest_id,
            quest["status"],
            QuestStatusEnum.assigned.value,
            changed_by=current_user.id,
            note="Freelancer assigned",
            created_at=now,
        )
        await message_service.create_system_message(
            conn,
            quest_id,
            f"Исполнитель {freelancer_row_slot.get('username') or 'фрилансер'} назначен на контракт.",
        )
        await notification_service.create_notification(
            conn,
            user_id=freelancer_id,
            title="Вы назначены на квест!",
            message=f"Вам назначен квест: {quest['title']}",
            event_type="quest_assigned",
        )

        updated_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
        apps = await _fetch_quest_applications(conn, quest_id)
    return row_to_quest(updated_row, apps)


# ────────────────────────────────────────────
# Start assigned quest (freelancer)
# ────────────────────────────────────────────

async def start_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> Quest:
    """Assigned freelancer starts the quest. Returns updated Quest."""
    if current_user.is_banned:
        raise PermissionError("Banned users cannot start quests")

    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT id, status, assigned_to FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")

        if quest["status"] != QuestStatusEnum.assigned.value:
            raise ValueError("Can only start quest that is assigned")

        if quest["assigned_to"] != current_user.id:
            raise PermissionError("Only assigned freelancer can start quest")

        now = datetime.now(timezone.utc)
        await conn.execute(
            "UPDATE quests SET status = $1, updated_at = $2 WHERE id = $3",
            QuestStatusEnum.in_progress.value,
            now,
            quest_id,
        )
        await _record_status_history(
            conn,
            quest_id,
            quest["status"],
            QuestStatusEnum.in_progress.value,
            changed_by=current_user.id,
            note="Work started",
            created_at=now,
        )
        await message_service.create_system_message(
            conn,
            quest_id,
            f"Исполнитель {current_user.username} начал работу по контракту.",
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
    completion_data: Optional[QuestCompletionCreate],
    current_user: UserProfile,
) -> Tuple[Quest, int]:
    """Freelancer marks a quest as completed. Returns (quest, xp_reward)."""
    if current_user.is_banned:
        raise PermissionError("Banned users cannot complete quests")

    async with conn.transaction():
        # Lock quest to prevent concurrent status changes
        quest = await conn.fetchrow(
            "SELECT id, status, assigned_to FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")

        if quest["status"] not in (
            QuestStatusEnum.in_progress.value,
            QuestStatusEnum.revision_requested.value,
        ):
            raise ValueError("Can only complete quest that is in progress or requested for revision")

        if quest["assigned_to"] != current_user.id:
            raise PermissionError("Only assigned freelancer can complete quest")

        now = datetime.now(timezone.utc)
        delivery_note = completion_data.delivery_note if completion_data else None
        delivery_url = str(completion_data.delivery_url) if completion_data and completion_data.delivery_url else None
        await conn.execute(
            """
            UPDATE quests
            SET status = $1,
                completed_at = $2,
                delivery_note = $3,
                delivery_url = $4,
                delivery_submitted_at = $2,
                revision_reason = NULL,
                revision_requested_at = NULL,
                updated_at = $5
            WHERE id = $6
            """,
            QuestStatusEnum.completed.value,
            now,
            delivery_note,
            delivery_url,
            now,
            quest_id,
        )
        await _record_status_history(
            conn,
            quest_id,
            quest["status"],
            QuestStatusEnum.completed.value,
            changed_by=current_user.id,
            note="Result submitted for review",
            created_at=now,
        )
        await message_service.create_system_message(
            conn,
            quest_id,
            f"Исполнитель {current_user.username} сдал результат на проверку клиенту.",
        )

        updated_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
        apps = await _fetch_quest_applications(conn, quest_id)
    return row_to_quest(updated_row, apps), quest["xp_reward"]


# ────────────────────────────────────────────
# Request revision (client)
# ────────────────────────────────────────────

async def request_quest_revision(
    conn: asyncpg.Connection,
    quest_id: str,
    revision_data: QuestRevisionRequest,
    current_user: UserProfile,
) -> Quest:
    """Client requests revisions for a completed quest. Returns updated Quest."""
    MAX_REVISIONS = 3  # P1 Q-04: limit revision loop

    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT id, client_id, status, revision_count FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")

        if quest["client_id"] != current_user.id:
            raise PermissionError("Only client can request revision")

        if quest["status"] != QuestStatusEnum.completed.value:
            raise ValueError("Can only request revision for completed quest")

        # P1 Q-04: enforce revision count limit
        revision_count = quest.get("revision_count") or 0
        if revision_count >= MAX_REVISIONS:
            raise ValueError(f"Maximum revisions ({MAX_REVISIONS}) exceeded. Please confirm or escalate to support.")

        now = datetime.now(timezone.utc)
        await conn.execute(
            """
            UPDATE quests
            SET status = $1,
                revision_reason = $2,
                revision_requested_at = $3,
                revision_count = COALESCE(revision_count, 0) + 1,
                updated_at = $3
            WHERE id = $4
            """,
            QuestStatusEnum.revision_requested.value,
            revision_data.revision_reason.strip(),
            now,
            quest_id,
        )
        await _record_status_history(
            conn,
            quest_id,
            quest["status"],
            QuestStatusEnum.revision_requested.value,
            changed_by=current_user.id,
            note="Revision requested by client",
            created_at=now,
        )
        await message_service.create_system_message(
            conn,
            quest_id,
            "Клиент отправил контракт на доработку. Проверьте замечания и повторно сдайте результат.",
        )

        updated_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
        apps = await _fetch_quest_applications(conn, quest_id)
    return row_to_quest(updated_row, apps)


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
    # ── Single atomic transaction: lock, validate, calculate, mutate ────────
    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")

        if quest["client_id"] != current_user.id:
            raise PermissionError("Only client can confirm completion")

        if quest["status"] != QuestStatusEnum.completed.value:
            raise ValueError("Quest has not been marked as completed by freelancer")

        freelancer_row = await conn.fetchrow(
            """
            SELECT id, username, grade, xp, level, stat_points, stats_int, stats_dex, stats_cha, character_class
            FROM users
            WHERE id = $1 FOR UPDATE
            """,
            quest["assigned_to"],
        )
        if not freelancer_row:
            raise ValueError(f"Freelancer not found: {quest['assigned_to']}")

        # ── Use the stored XP reward so the amount matches what was shown
        # at quest creation / completion time, regardless of grade changes.
        freelancer_grade = GradeEnum(freelancer_row["grade"])

        xp_reward = quest["xp_reward"]
        if not xp_reward or xp_reward <= 0:
            # Fallback for legacy quests that may not have stored xp_reward
            quest_grade = GradeEnum(quest["required_grade"])
            xp_reward = calculate_quest_rewards(
                budget=quest["budget"],
                quest_grade=quest_grade,
                user_grade=freelancer_grade,
            )

        # R-05 & Phase 2: Apply class-specific XP multi/penalty & burnout
        is_burnout = await class_service.check_burnout(conn, quest["assigned_to"])
        original_xp_reward = xp_reward

        deadline_penalty_rate = _calculate_deadline_penalty_rate(
            quest.get("deadline"),
            quest.get("delivery_submitted_at") or quest.get("completed_at"),
        )

        if freelancer_row.get("character_class"):
            xp_multiplier = calculate_class_xp_multiplier(
                class_id=freelancer_row["character_class"],
                is_urgent=quest.get("is_urgent", False),
                is_burnout=is_burnout,
                is_high_budget=Decimal(str(quest.get("budget", 0))) >= 1000,
                is_ontime=deadline_penalty_rate == 0
            )
            xp_reward = max(1, int(xp_reward * xp_multiplier))

        # Apply active ability XP modifier to global XP
        ability_effects = await class_service.get_active_ability_effects(conn, quest["assigned_to"])
        deadline_penalty_reduce = ability_effects.get("deadline_penalty_reduce", 0)
        if (
            deadline_penalty_rate > 0
            and isinstance(deadline_penalty_reduce, (int, float))
            and deadline_penalty_reduce > 0
        ):
            deadline_penalty_rate *= max(0.0, 1.0 - min(1.0, float(deadline_penalty_reduce)))
        if deadline_penalty_rate > 0:
            xp_reward = _apply_xp_penalty(xp_reward, deadline_penalty_rate)

        ability_xp_bonus = ability_effects.get("xp_all_bonus", 0)
        if ability_xp_bonus and isinstance(ability_xp_bonus, (int, float)) and ability_xp_bonus > 0:
            xp_reward = int(xp_reward * (1.0 + ability_xp_bonus))
        # Burnout immunity from abilities overrides the penalty
        if is_burnout and ability_effects.get("burnout_immune") and xp_reward < original_xp_reward:
            xp_reward = original_xp_reward

        old_level = freelancer_row["level"]
        new_xp = freelancer_row["xp"] + xp_reward
        level_up, new_grade, new_level, promoted_through = check_level_up(new_xp, freelancer_grade)
        new_xp_to_next = calculate_xp_to_next(new_xp, new_grade)

        # Stat growth on level-up
        levels_gained = max(0, new_level - old_level)
        stat_delta = allocate_stat_points(levels_gained) if levels_gained > 0 else {"int": 0, "dex": 0, "cha": 0, "unspent": 0}
        # R-06: Cap stats at 100
        new_stats_int = min(STAT_CAP, freelancer_row["stats_int"] + stat_delta["int"])
        new_stats_dex = min(STAT_CAP, freelancer_row["stats_dex"] + stat_delta["dex"])
        new_stats_cha = min(STAT_CAP, freelancer_row["stats_cha"] + stat_delta["cha"])
        new_stat_points = freelancer_row.get("stat_points", 0) + stat_delta["unspent"]

        now = datetime.now(timezone.utc)

        # 0. Flip status to 'confirmed' (CAS guard against double-payment)
        updated = await conn.fetchval(
            "UPDATE quests SET status = $1, updated_at = $2 WHERE id = $3 AND status = $4 RETURNING id",
            QuestStatusEnum.confirmed.value,
            now,
            quest_id,
            QuestStatusEnum.completed.value,
        )
        if not updated:
            raise ValueError("Quest was already confirmed or status changed concurrently")
        await _record_status_history(
            conn,
            quest_id,
            quest["status"],
            QuestStatusEnum.confirmed.value,
            changed_by=current_user.id,
            note="Quest confirmed and paid",
            created_at=now,
        )

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
        #    Use the fee snapshot from quest creation (H-03) if available
        urgent_payout_bonus = ability_effects.get("urgent_payout_bonus", 0)
        client_surcharge_amount = Decimal("0")
        if (
            quest.get("is_urgent", False)
            and isinstance(urgent_payout_bonus, (int, float))
            and urgent_payout_bonus > 0
        ):
            client_surcharge_amount = wallet_service.quantize_money(
                Decimal(str(quest["budget"])) * Decimal(str(urgent_payout_bonus))
            )

        from app.core.config import settings as _settings

        try:
            # Use stored fee or fall back to settings default (raid quests store 0)
            fee_snapshot = quest.get("platform_fee_percent")
            if fee_snapshot is None or Decimal(str(fee_snapshot)) <= 0:
                fee_snapshot = Decimal(_settings.PLATFORM_FEE_PERCENT)
            split = await wallet_service.split_payment(
                conn,
                client_id=quest["client_id"],
                freelancer_id=quest["assigned_to"],
                gross_amount=quest["budget"],
                currency=quest["currency"],
                quest_id=quest_id,
                fee_percent=fee_snapshot,
                client_surcharge_amount=client_surcharge_amount,
            )
        except wallet_service.InsufficientFundsError as exc:
            raise wallet_service.InsufficientFundsError(
                "Quest confirmation requires an active escrow hold or enough client balance for a direct debit"
            ) from exc

        guild_economy_result = await guild_economy_service.apply_quest_completion_rewards(
            conn,
            quest_id=quest_id,
            freelancer_id=quest["assigned_to"],
            gross_amount=quest["budget"],
            platform_fee=split["platform_fee"],
            xp_reward=xp_reward,
            is_urgent=bool(quest.get("is_urgent", False)),
            confirmed_at=now,
            source="client_confirm",
        )
        if guild_economy_result is None:
            await guild_economy_service.award_solo_artifact_drop(
                conn,
                quest_id=quest_id,
                freelancer_id=quest["assigned_to"],
                gross_amount=quest["budget"],
                platform_fee=split["platform_fee"],
                xp_reward=xp_reward,
                is_urgent=bool(quest.get("is_urgent", False)),
                confirmed_at=now,
            )

        # 3. Badge check — count confirmed quests for freelancer
        completed_count_row = await conn.fetchval(
            "SELECT COUNT(*) FROM quests WHERE assigned_to = $1 AND status = $2",
            quest["assigned_to"],
            QuestStatusEnum.confirmed.value,
        )
        quests_completed = int(completed_count_row or 0)
        badge_event_data = {
            "quests_completed": quests_completed,
            "xp": new_xp,
            "level": new_level,
            "grade": new_grade.value,
            "earnings": split["freelancer_amount"],
        }
        award_result = await badge_service.check_and_award(
            conn, quest["assigned_to"], "quest_completed", badge_event_data
        )

        # 3b. Advance legendary quest chain progress (if quest belongs to a chain)
        chain_progress = await advance_chain_progress(conn, quest_id, quest["assigned_to"])

        # 4. Send notifications inside the main transaction
        await notification_service.create_notification(
            conn,
            user_id=quest["assigned_to"],
            title="Quest Confirmed!",
            message=(
                f"Your quest '{quest['title']}' has been confirmed. "
                f"You received {split['freelancer_amount']} {quest['currency']} "
                f"and {xp_reward} XP."
                + (
                    f" Срочный бонус сверх бюджета: {split.get('client_surcharge_amount', Decimal('0'))} {quest['currency']}."
                    if split.get("client_surcharge_amount", Decimal("0")) > 0
                    else ""
                )
            ),
            event_type="quest_confirmed",
        )
        await message_service.create_system_message(
            conn,
            quest_id,
            "Контракт закрыт и подтверждён клиентом.",
        )
        await notification_service.create_notification(
            conn,
            user_id=quest["client_id"],
            title="Оплата подтверждена",
            message=f"Квест \"{quest['title']}\" завершён и оплачен",
            event_type="quest_payment_confirmed",
        )
        for earned in award_result.newly_earned:
            await notification_service.create_notification(
                conn,
                user_id=quest["assigned_to"],
                title=f"Badge Earned: {earned.badge_name}",
                message=earned.badge_description,
                event_type="badge_earned",
            )

        # 5. Class XP progression (if freelancer has a class)
        class_result = await class_service.add_class_xp(
            conn,
            quest["assigned_to"],
            xp_reward,
            is_urgent=quest.get("is_urgent", False),
            required_portfolio=quest.get("required_portfolio", False),
        )
        await trust_score_service.refresh_trust_score(conn, quest["assigned_to"])

    logger.info(
        f"Quest {quest_id} confirmed. Freelancer {freelancer_row['username']}: "
        f"+{xp_reward} XP, +{split['freelancer_amount']} {quest['currency']} "
        f"(platform fee {split['platform_fee']} = {split['fee_percent']}%)"
    )

    updated_quest = await conn.fetchrow(
        "SELECT * FROM quests WHERE id = $1",
        quest_id,
    )
    return {
        "message": "Quest confirmed! Reward has been paid.",
        "quest": row_to_quest(updated_quest, []),
        "xp_reward": xp_reward,
        "money_reward": split["freelancer_amount"],
        "client_surcharge_amount": split.get("client_surcharge_amount", Decimal("0")),
        "platform_fee": split["platform_fee"],
        "fee_percent": split["fee_percent"],
        "deadline_penalty_rate": deadline_penalty_rate,
        "guild_economy": None if not guild_economy_result else {
            "guild_id": guild_economy_result["guild_id"],
            "guild_name": guild_economy_result["guild_name"],
            "treasury_delta": wallet_service.quantize_money(guild_economy_result["treasury_delta"]),
            "guild_tokens_delta": guild_economy_result["guild_tokens_delta"],
            "contribution_delta": guild_economy_result["contribution_delta"],
            "card_drop": guild_economy_result["card_drop"],
        },
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
        "chain_progress": chain_progress.model_dump() if chain_progress else None,
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
    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT id, client_id, status, assigned_to, title, currency FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")

        if quest["client_id"] != current_user.id:
            raise PermissionError("Only client can cancel quest")

        if quest["status"] not in [
            QuestStatusEnum.draft.value,
            QuestStatusEnum.open.value,
            QuestStatusEnum.revision_requested.value,
        ]:
            raise ValueError(f"Cannot unilaterally cancel quest in status: {quest['status']}. Please open a dispute or contact support.")

        now = datetime.now(timezone.utc)

        await conn.execute(
            "UPDATE quests SET status = $1, updated_at = $2 WHERE id = $3",
            QuestStatusEnum.cancelled.value,
            now,
            quest_id,
        )

        # P0-1 FIX: Refund escrow hold if funds were held for this quest
        await wallet_service.refund_hold(
            conn,
            user_id=quest["client_id"],
            quest_id=quest_id,
            currency=quest["currency"],
        )

        await _record_status_history(
            conn,
            quest_id,
            quest["status"],
            QuestStatusEnum.cancelled.value,
            changed_by=current_user.id,
            note="Quest cancelled",
            created_at=now,
        )

        # Notify assigned freelancer about cancellation
        if quest["assigned_to"]:
            await notification_service.create_notification(
                conn,
                user_id=quest["assigned_to"],
                title="Квест отменён",
                message=f"Клиент отменил квест «{quest['title']}».",
                event_type="quest_cancelled",
            )

    return {
        "message": "Quest cancelled successfully",
        "freelancer_xp_penalty": 0,
        "freelancer_xp_protected": False,
    }


# ────────────────────────────────────────────
# Get applications
# ────────────────────────────────────────────

async def get_quest_applications(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> dict:
    """Return applications for a quest. Only the quest owner can see them."""
    quest = await conn.fetchrow(
            "SELECT id, client_id, status FROM quests WHERE id = $1", quest_id
        )
    if not quest:
        raise ValueError("Quest not found")

    if quest["client_id"] != current_user.id and current_user.role != "admin":
        raise PermissionError("Only client or admin can view applications")

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
            proposed_price=row["proposed_price"] if row["proposed_price"] else None,
            created_at=row["created_at"],
        )
        for row in rows
    ]

    return {"applications": applications, "total": len(applications)}


# ────────────────────────────────────────────
# PvE Training Quests
# ────────────────────────────────────────────

SYSTEM_CLIENT_ID = "system"
SYSTEM_CLIENT_USERNAME = "Гильдия Мастеров"


async def _get_training_xp_earned_today(conn: asyncpg.Connection, user_id: str) -> int:
    """Sum of training XP a user earned today (UTC)."""
    row = await conn.fetchval(
        """
        SELECT COALESCE(SUM(xp_reward), 0)
        FROM quests
        WHERE assigned_to = $1
          AND quest_type = 'training'
          AND status = 'confirmed'
          AND completed_at >= (CURRENT_DATE AT TIME ZONE 'UTC')
        """,
        user_id,
    )
    return int(row or 0)


async def list_training_quests(
    conn: asyncpg.Connection,
    *,
    page: int = 1,
    page_size: int = 10,
    grade_filter: Optional[GradeEnum] = None,
    skill_filter: Optional[str] = None,
) -> QuestListResponse:
    """List available training quests (open, quest_type=training)."""
    query = "SELECT * FROM quests WHERE quest_type = 'training' AND status = 'open'"
    args: list = []
    arg_idx = 1

    if grade_filter:
        query += f" AND required_grade = ${arg_idx}"
        args.append(grade_filter.value)
        arg_idx += 1
    if skill_filter:
        query += f" AND skills::jsonb @> ${arg_idx}::jsonb"
        args.append(json.dumps([skill_filter]))
        arg_idx += 1

    count_query = f"SELECT COUNT(*) FROM ({query}) as cq"
    total = await conn.fetchval(count_query, *args)

    query += f" ORDER BY created_at DESC LIMIT ${arg_idx} OFFSET ${arg_idx + 1}"
    args.extend([page_size, (page - 1) * page_size])
    rows = await conn.fetch(query, *args)

    quests = [row_to_quest(row) for row in rows]
    safe_total = int(total or 0)
    return QuestListResponse(
        quests=quests,
        total=safe_total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < safe_total,
    )


async def create_training_quest(
    conn: asyncpg.Connection,
    data: TrainingQuestCreate,
    current_user: UserProfile,
) -> Quest:
    """Create a PvE training quest (admin-only). No escrow, zero budget."""
    if current_user.role != "admin":
        raise PermissionError("Only admins can create training quests")

    xp_reward = calculate_training_xp_reward(
        base_xp=data.xp_reward,
        quest_grade=data.required_grade,
        user_grade=GradeEnum.novice,
    )

    quest_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO quests (
                id, client_id, client_username, title, description, required_grade,
                skills, budget, currency, xp_reward, status,
                quest_type, is_urgent, deadline, required_portfolio,
                platform_fee_percent, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
            """,
            quest_id,
            SYSTEM_CLIENT_ID,
            SYSTEM_CLIENT_USERNAME,
            data.title,
            data.description,
            data.required_grade.value,
            json.dumps(data.skills),
            TRAINING_BUDGET,
            "RUB",
            xp_reward,
            QuestStatusEnum.open.value,
            "training",
            False,
            None,
            False,
            Decimal("0"),
            now,
            now,
        )
        await _record_status_history(
            conn, quest_id, None, QuestStatusEnum.open.value,
            changed_by=current_user.id,
            note="Training quest created",
            created_at=now,
        )

    return Quest(
        id=quest_id,
        client_id=SYSTEM_CLIENT_ID,
        client_username=SYSTEM_CLIENT_USERNAME,
        title=data.title,
        description=data.description,
        required_grade=data.required_grade,
        skills=data.skills,
        budget=TRAINING_BUDGET,
        currency="RUB",
        xp_reward=xp_reward,
        status=QuestStatusEnum.open,
        applications=[],
        assigned_to=None,
        quest_type="training",
        is_urgent=False,
        deadline=None,
        required_portfolio=False,
        platform_fee_percent=Decimal("0"),
        created_at=now,
        updated_at=now,
        completed_at=None,
    )


async def accept_training_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> Quest:
    """Freelancer accepts a training quest — auto-assign and auto-start.

    Skips application phase and escrow. Moves straight to in_progress.
    """
    if current_user.is_banned:
        raise PermissionError("Banned users cannot accept training quests")

    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")
        if quest.get("quest_type", "standard") != "training":
            raise ValueError("This is not a training quest")
        if quest["status"] != QuestStatusEnum.open.value:
            raise ValueError("Training quest is not available")

        # Grade check
        quest_grade = GradeEnum(quest["required_grade"])
        if get_grade_level(GradeEnum(current_user.grade)) < get_grade_level(quest_grade):
            raise ValueError(
                f"Your grade ({current_user.grade}) is lower than required ({quest_grade.value})"
            )

        # Daily XP cap check — reject if already at cap
        earned_today = await _get_training_xp_earned_today(conn, current_user.id)
        if earned_today >= TRAINING_DAILY_XP_CAP:
            raise ValueError(
                f"Daily training XP cap reached ({TRAINING_DAILY_XP_CAP} XP). Try again tomorrow."
            )

        now = datetime.now(timezone.utc)
        # Auto-assign + auto-start (skip application phase, no escrow)
        await conn.execute(
            "UPDATE quests SET assigned_to = $1, status = $2, updated_at = $3 WHERE id = $4",
            current_user.id,
            QuestStatusEnum.in_progress.value,
            now,
            quest_id,
        )
        await _record_status_history(
            conn, quest_id, quest["status"], QuestStatusEnum.in_progress.value,
            changed_by=current_user.id,
            note="Training quest accepted and started",
            created_at=now,
        )

        updated_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    return row_to_quest(updated_row)


async def complete_training_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> dict:
    """Freelancer completes a training quest — auto-confirm, grant capped XP.

    No escrow release, no wallet payment, no client review.
    """
    if current_user.is_banned:
        raise PermissionError("Banned users cannot complete training quests")

    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")
        if quest.get("quest_type", "standard") != "training":
            raise ValueError("This is not a training quest")
        if quest["status"] != QuestStatusEnum.in_progress.value:
            raise ValueError("Training quest is not in progress")
        if quest["assigned_to"] != current_user.id:
            raise PermissionError("Only the assigned freelancer can complete this quest")

        # Daily XP cap — clamp reward if needed
        earned_today = await _get_training_xp_earned_today(conn, current_user.id)
        remaining_cap = max(0, TRAINING_DAILY_XP_CAP - earned_today)
        raw_xp = calculate_training_xp_reward(
            base_xp=quest["xp_reward"],
            quest_grade=GradeEnum(quest["required_grade"]),
            user_grade=GradeEnum(current_user.grade),
        )
        xp_reward = min(raw_xp, remaining_cap)

        if xp_reward <= 0:
            raise ValueError(
                f"Daily training XP cap reached ({TRAINING_DAILY_XP_CAP} XP). No XP will be awarded."
            )

        freelancer_row = await conn.fetchrow(
            """
            SELECT id, username, grade, xp, level, stat_points, stats_int, stats_dex, stats_cha
            FROM users
            WHERE id = $1 FOR UPDATE
            """,
            current_user.id,
        )
        if not freelancer_row:
            raise ValueError("Freelancer not found")

        freelancer_grade = GradeEnum(freelancer_row["grade"])
        old_level = freelancer_row["level"]
        new_xp = freelancer_row["xp"] + xp_reward
        level_up, new_grade, new_level, promoted_through = check_level_up(new_xp, freelancer_grade)
        new_xp_to_next = calculate_xp_to_next(new_xp, new_grade)

        levels_gained = max(0, new_level - old_level)
        stat_delta = allocate_stat_points(levels_gained) if levels_gained > 0 else {"int": 0, "dex": 0, "cha": 0, "unspent": 0}
        new_stats_int = min(STAT_CAP, freelancer_row["stats_int"] + stat_delta["int"])
        new_stats_dex = min(STAT_CAP, freelancer_row["stats_dex"] + stat_delta["dex"])
        new_stats_cha = min(STAT_CAP, freelancer_row["stats_cha"] + stat_delta["cha"])

        now = datetime.now(timezone.utc)

        # Auto-confirm: completed → confirmed in one step
        updated = await conn.fetchval(
            "UPDATE quests SET status = $1, completed_at = $2, updated_at = $2 WHERE id = $3 AND status = $4 RETURNING id",
            QuestStatusEnum.confirmed.value,
            now,
            quest_id,
            QuestStatusEnum.in_progress.value,
        )
        if not updated:
            raise ValueError("Quest status changed concurrently")

        await _record_status_history(
            conn, quest_id, QuestStatusEnum.in_progress.value, QuestStatusEnum.confirmed.value,
            changed_by=current_user.id,
            note=f"Training quest completed. +{xp_reward} XP",
            created_at=now,
        )

        # Grant XP and stats
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
            current_user.id,
        )

        # Badge check
        completed_count_row = await conn.fetchval(
            "SELECT COUNT(*) FROM quests WHERE assigned_to = $1 AND status = $2",
            current_user.id,
            QuestStatusEnum.confirmed.value,
        )
        badge_event_data = {
            "quests_completed": int(completed_count_row or 0),
            "xp": new_xp,
            "level": new_level,
            "grade": new_grade.value,
            "earnings": Decimal("0"),
        }
        award_result = await badge_service.check_and_award(
            conn, current_user.id, "quest_completed", badge_event_data
        )

        # Notification inside main transaction
        try:
            await notification_service.create_notification(
                conn,
                user_id=current_user.id,
                title="Тренировка завершена!",
                message=f"Вы выполнили тренировочный квест «{quest['title']}» и получили {xp_reward} XP.",
                event_type="training_quest_completed",
            )
        except Exception:
            logger.warning("Training quest notification failed", exc_info=True)

    updated_quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    return {
        "message": "Training quest completed!",
        "quest": row_to_quest(updated_quest, []),
        "xp_reward": xp_reward,
        "daily_xp_earned": earned_today + xp_reward,
        "daily_xp_cap": TRAINING_DAILY_XP_CAP,
        "level_up": level_up,
        "new_level": new_level,
        "new_grade": new_grade.value,
        "stat_delta": stat_delta,
        "badges_earned": [
            {"id": b.badge_id, "name": b.badge_name, "description": b.badge_description}
            for b in award_result.newly_earned
        ],
    }


# ────────────────────────────────────────────
# Co-op Raid Quests
# ────────────────────────────────────────────

RAID_MIN_MEMBERS = 2
RAID_MAX_MEMBERS = 8


def _row_to_participant(row) -> RaidParticipant:
    """Convert an asyncpg Record to a RaidParticipant model."""
    return RaidParticipant(
        id=row["id"],
        quest_id=row["quest_id"],
        user_id=row["user_id"],
        username=row["username"],
        role_slot=row["role_slot"],
        joined_at=row["joined_at"],
    )


async def list_raid_quests(
    conn: asyncpg.Connection,
    *,
    page: int = 1,
    page_size: int = 10,
    grade_filter: Optional[GradeEnum] = None,
    skill_filter: Optional[str] = None,
) -> QuestListResponse:
    """List available raid quests (open, quest_type=raid)."""
    query = "SELECT * FROM quests WHERE quest_type = 'raid' AND status = 'open'"
    args: list = []
    arg_idx = 1

    if grade_filter:
        query += f" AND required_grade = ${arg_idx}"
        args.append(grade_filter.value)
        arg_idx += 1
    if skill_filter:
        query += f" AND skills::jsonb @> ${arg_idx}::jsonb"
        args.append(json.dumps([skill_filter]))
        arg_idx += 1

    count_query = f"SELECT COUNT(*) FROM ({query}) as cq"
    total = await conn.fetchval(count_query, *args)

    query += f" ORDER BY created_at DESC LIMIT ${arg_idx} OFFSET ${arg_idx + 1}"
    args.extend([page_size, (page - 1) * page_size])
    rows = await conn.fetch(query, *args)

    quests = [row_to_quest(row) for row in rows]
    safe_total = int(total or 0)
    return QuestListResponse(
        quests=quests,
        total=safe_total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < safe_total,
    )


async def create_raid_quest(
    conn: asyncpg.Connection,
    data: RaidQuestCreate,
    current_user: UserProfile,
) -> Quest:
    """Client creates a co-op raid quest with multiple participant slots."""
    if current_user.role not in ("client", "admin"):
        raise PermissionError("Only clients or admins can create raid quests")

    xp_reward = data.xp_reward or calculate_xp_reward(data.budget, data.required_grade)
    quest_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Validate role_slots count vs max_members
    if data.role_slots and len(data.role_slots) > data.raid_max_members:
        raise ValueError("role_slots count cannot exceed raid_max_members")

    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO quests (
                id, client_id, client_username, title, description, required_grade,
                skills, budget, currency, xp_reward, status,
                quest_type, is_urgent, deadline, required_portfolio,
                platform_fee_percent, raid_max_members, raid_current_members,
                created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
            """,
            quest_id,
            current_user.id,
            current_user.username,
            data.title,
            data.description,
            data.required_grade.value,
            json.dumps(data.skills),
            data.budget,
            data.currency,
            xp_reward,
            QuestStatusEnum.open.value,
            "raid",
            False,  # is_urgent
            None,   # deadline
            False,  # required_portfolio
            Decimal("0"),  # platform_fee_percent (set at confirmation)
            data.raid_max_members,
            0,  # raid_current_members starts at 0
            now,
            now,
        )
        await _record_status_history(
            conn, quest_id, None, QuestStatusEnum.open.value,
            changed_by=current_user.id,
            note=f"Raid quest created (max {data.raid_max_members} members)",
            created_at=now,
        )

    created_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    return row_to_quest(created_row)


async def join_raid_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    role_slot: str,
    current_user: UserProfile,
) -> RaidPartyResponse:
    """Freelancer joins a raid quest in a specific role slot."""
    if current_user.is_banned:
        raise PermissionError("Banned users cannot join raids")

    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")
        if quest.get("quest_type", "standard") != "raid":
            raise ValueError("This is not a raid quest")
        if quest["status"] != QuestStatusEnum.open.value:
            raise ValueError("Raid quest is not accepting members")

        # Grade check
        quest_grade = GradeEnum(quest["required_grade"])
        if get_grade_level(GradeEnum(current_user.grade)) < get_grade_level(quest_grade):
            raise ValueError(
                f"Your grade ({current_user.grade}) is lower than required ({quest_grade.value})"
            )

        # Check capacity
        raid_max = quest["raid_max_members"]
        raid_current = quest["raid_current_members"]
        if raid_current >= raid_max:
            raise ValueError("Raid party is full")

        # Check duplicate
        existing = await conn.fetchrow(
            "SELECT id FROM raid_participants WHERE quest_id = $1 AND user_id = $2",
            quest_id, current_user.id,
        )
        if existing:
            raise ValueError("You have already joined this raid")

        # Check role_slot conflict (if role is not "any")
        if role_slot != "any":
            role_taken = await conn.fetchrow(
                "SELECT id FROM raid_participants WHERE quest_id = $1 AND role_slot = $2",
                quest_id, role_slot,
            )
            if role_taken:
                raise ValueError(f"Role slot '{role_slot}' is already taken")

        participant_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        await conn.execute(
            """
            INSERT INTO raid_participants (id, quest_id, user_id, username, role_slot, joined_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            participant_id, quest_id, current_user.id, current_user.username,
            role_slot, now,
        )

        new_count = raid_current + 1
        await conn.execute(
            "UPDATE quests SET raid_current_members = $1, updated_at = $2 WHERE id = $3",
            new_count, now, quest_id,
        )

    return await get_raid_party(conn, quest_id)


async def leave_raid_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> RaidPartyResponse:
    """Freelancer leaves a raid quest before it starts."""
    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")
        if quest.get("quest_type", "standard") != "raid":
            raise ValueError("This is not a raid quest")
        if quest["status"] != QuestStatusEnum.open.value:
            raise ValueError("Cannot leave a raid that has already started")

        deleted = await conn.fetchval(
            "DELETE FROM raid_participants WHERE quest_id = $1 AND user_id = $2 RETURNING id",
            quest_id, current_user.id,
        )
        if not deleted:
            raise ValueError("You are not a member of this raid")

        now = datetime.now(timezone.utc)
        new_count = max(0, quest["raid_current_members"] - 1)
        await conn.execute(
            "UPDATE quests SET raid_current_members = $1, updated_at = $2 WHERE id = $3",
            new_count, now, quest_id,
        )

    return await get_raid_party(conn, quest_id)


async def start_raid_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> Quest:
    """Client or admin starts the raid (moves to in_progress).

    At least 2 participants must be present.
    """
    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")
        if quest.get("quest_type", "standard") != "raid":
            raise ValueError("This is not a raid quest")
        if quest["status"] != QuestStatusEnum.open.value:
            raise ValueError("Raid quest is not in open state")

        # Only quest owner or admin can start
        if current_user.role != "admin" and quest["client_id"] != current_user.id:
            raise PermissionError("Only the quest owner or admin can start a raid")

        if quest["raid_current_members"] < RAID_MIN_MEMBERS:
            raise ValueError(
                f"Need at least {RAID_MIN_MEMBERS} members to start a raid "
                f"(currently {quest['raid_current_members']})"
            )

        now = datetime.now(timezone.utc)
        await conn.execute(
            "UPDATE quests SET status = $1, updated_at = $2 WHERE id = $3",
            QuestStatusEnum.in_progress.value, now, quest_id,
        )
        await _record_status_history(
            conn, quest_id, QuestStatusEnum.open.value, QuestStatusEnum.in_progress.value,
            changed_by=current_user.id,
            note=f"Raid started with {quest['raid_current_members']}/{quest['raid_max_members']} members",
            created_at=now,
        )

    updated_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    return row_to_quest(updated_row)


async def complete_raid_quest(
    conn: asyncpg.Connection,
    quest_id: str,
    current_user: UserProfile,
) -> dict:
    """Mark a raid quest as completed. Any raid member can trigger this.

    Moves from in_progress → completed. Client still needs to confirm.
    """
    async with conn.transaction():
        quest = await conn.fetchrow(
            "SELECT * FROM quests WHERE id = $1 FOR UPDATE", quest_id
        )
        if not quest:
            raise ValueError("Quest not found")
        if quest.get("quest_type", "standard") != "raid":
            raise ValueError("This is not a raid quest")
        if quest["status"] != QuestStatusEnum.in_progress.value:
            raise ValueError("Raid quest is not in progress")

        # Must be a raid member
        is_member = await conn.fetchval(
            "SELECT id FROM raid_participants WHERE quest_id = $1 AND user_id = $2",
            quest_id, current_user.id,
        )
        if not is_member:
            raise PermissionError("Only raid members can complete a raid quest")

        now = datetime.now(timezone.utc)
        await conn.execute(
            "UPDATE quests SET status = $1, completed_at = $2, updated_at = $2 WHERE id = $3",
            QuestStatusEnum.completed.value, now, quest_id,
        )
        await _record_status_history(
            conn, quest_id, QuestStatusEnum.in_progress.value, QuestStatusEnum.completed.value,
            changed_by=current_user.id,
            note=f"Raid completed by member {current_user.username}",
            created_at=now,
        )

    participants = await conn.fetch(
        "SELECT * FROM raid_participants WHERE quest_id = $1", quest_id
    )
    updated_quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    return {
        "message": "Raid quest completed — awaiting client confirmation",
        "quest": row_to_quest(updated_quest),
        "participants": [_row_to_participant(p) for p in participants],
    }


async def get_raid_party(
    conn: asyncpg.Connection,
    quest_id: str,
) -> RaidPartyResponse:
    """Get current raid party state."""
    quest = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", quest_id)
    if not quest:
        raise ValueError("Quest not found")
    if quest.get("quest_type", "standard") != "raid":
        raise ValueError("This is not a raid quest")

    participants_rows = await conn.fetch(
        "SELECT * FROM raid_participants WHERE quest_id = $1 ORDER BY joined_at", quest_id
    )
    participants = [_row_to_participant(r) for r in participants_rows]
    max_members = quest["raid_max_members"] or 0
    current = quest["raid_current_members"] or 0

    # Extract role_slots from current participants
    role_slots = [p.role_slot for p in participants]

    return RaidPartyResponse(
        quest_id=quest_id,
        max_members=max_members,
        current_members=current,
        open_slots=max(0, max_members - current),
        participants=participants,
        role_slots=role_slots,
    )


# ────────────────────────────────────────────
# Legendary Quest Chains
# ────────────────────────────────────────────

def _row_to_chain(row) -> QuestChain:
    return QuestChain(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        total_steps=row["total_steps"],
        final_xp_bonus=row["final_xp_bonus"],
        final_badge_id=row.get("final_badge_id"),
        created_at=row["created_at"],
    )


def _row_to_chain_step(row) -> ChainStep:
    return ChainStep(
        id=row["id"],
        chain_id=row["chain_id"],
        quest_id=row["quest_id"],
        step_order=row["step_order"],
    )


def _row_to_progress(row) -> UserChainProgress:
    return UserChainProgress(
        id=row["id"],
        chain_id=row["chain_id"],
        user_id=row["user_id"],
        current_step=row["current_step"],
        status=ChainStatusEnum(row["status"]),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
    )


async def list_quest_chains(
    conn: asyncpg.Connection,
    *,
    page: int = 1,
    page_size: int = 20,
) -> ChainListResponse:
    """List all quest chains with pagination."""
    offset = (page - 1) * page_size
    rows = await conn.fetch(
        """
        SELECT id, title, description, total_steps, final_xp_bonus, final_badge_id, created_at
        FROM quest_chains
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        """,
        page_size, offset,
    )
    total_row = await conn.fetchrow("SELECT count(*) AS cnt FROM quest_chains")
    total = total_row["cnt"] if total_row else 0
    return ChainListResponse(
        chains=[_row_to_chain(r) for r in rows],
        total=total,
    )


async def get_chain_detail(
    conn: asyncpg.Connection,
    chain_id: str,
    user_id: str | None = None,
) -> ChainDetailResponse:
    """Return full chain info with steps, quests in order, and optional user progress."""
    chain_row = await conn.fetchrow(
        "SELECT id, title, description, total_steps, final_xp_bonus, final_badge_id, created_at FROM quest_chains WHERE id = $1",
        chain_id,
    )
    if not chain_row:
        raise ValueError("Chain not found")

    step_rows = await conn.fetch(
        "SELECT * FROM chain_steps WHERE chain_id = $1 ORDER BY step_order", chain_id,
    )
    steps = [_row_to_chain_step(r) for r in step_rows]

    quests: list[Quest] = []
    for s in steps:
        q_row = await conn.fetchrow("SELECT * FROM quests WHERE id = $1", s.quest_id)
        if q_row:
            quests.append(row_to_quest(q_row))

    progress = None
    if user_id:
        p_row = await conn.fetchrow(
            "SELECT * FROM user_chain_progress WHERE chain_id = $1 AND user_id = $2",
            chain_id, user_id,
        )
        if p_row:
            progress = _row_to_progress(p_row)

    return ChainDetailResponse(
        chain=_row_to_chain(chain_row),
        steps=steps,
        quests=quests,
        user_progress=progress,
    )


async def create_quest_chain(
    conn: asyncpg.Connection,
    data: QuestChainCreate,
    admin_user: UserProfile,
) -> ChainDetailResponse:
    """Create a legendary quest chain (admin only)."""
    if admin_user.role != "admin":
        raise PermissionError("Only admins can create quest chains")

    # Validate all quest IDs exist
    for qid in data.quest_ids:
        q = await conn.fetchrow("SELECT id FROM quests WHERE id = $1", qid)
        if not q:
            raise ValueError(f"Quest {qid} not found")

    chain_id = f"chain_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    async with conn.transaction():
        await conn.execute(
            """INSERT INTO quest_chains (id, title, description, total_steps, final_xp_bonus, final_badge_id, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            chain_id, data.title, data.description, len(data.quest_ids),
            data.final_xp_bonus, data.final_badge_id, now,
        )

        steps: list[ChainStep] = []
        for idx, qid in enumerate(data.quest_ids, start=1):
            step_id = f"cs_{uuid.uuid4().hex[:12]}"
            await conn.execute(
                "INSERT INTO chain_steps (id, chain_id, quest_id, step_order) VALUES ($1, $2, $3, $4)",
                step_id, chain_id, qid, idx,
            )
            steps.append(ChainStep(id=step_id, chain_id=chain_id, quest_id=qid, step_order=idx))
            # Tag the quest with chain metadata
            await conn.execute(
                "UPDATE quests SET chain_id = $1, chain_step_order = $2 WHERE id = $3",
                chain_id, idx, qid,
            )

    return await get_chain_detail(conn, chain_id)


async def advance_chain_progress(
    conn: asyncpg.Connection,
    quest_id: str,
    user_id: str,
) -> UserChainProgress | None:
    """Called after a quest is confirmed/completed. Advances chain progress if quest belongs to a chain.

    Returns the updated progress or None if quest is not in a chain.
    """
    step_row = await conn.fetchrow(
        "SELECT chain_id, step_order FROM chain_steps WHERE quest_id = $1", quest_id,
    )
    if not step_row:
        return None  # quest is not part of any chain

    chain_id = step_row.get("chain_id")
    step_order = step_row.get("step_order")
    if not chain_id or step_order is None:
        return None

    chain_row = await conn.fetchrow(
        "SELECT id, title, description, total_steps, final_xp_bonus, final_badge_id, created_at FROM quest_chains WHERE id = $1",
        chain_id,
    )
    if not chain_row:
        return None

    async with conn.transaction():
        # Get or create progress row
        progress = await conn.fetchrow(
            "SELECT * FROM user_chain_progress WHERE chain_id = $1 AND user_id = $2 FOR UPDATE",
            chain_id, user_id,
        )
        now = datetime.now(timezone.utc)

        if not progress:
            prog_id = f"ucp_{uuid.uuid4().hex[:12]}"
            await conn.execute(
                """INSERT INTO user_chain_progress (id, chain_id, user_id, current_step, status, started_at)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                prog_id, chain_id, user_id, step_order, "in_progress", now,
            )
            progress = await conn.fetchrow(
                "SELECT * FROM user_chain_progress WHERE id = $1", prog_id,
            )
        else:
            # Only advance if this step is the next expected one
            if step_order > progress["current_step"]:
                new_step = step_order
                new_status = "in_progress"
                completed_at = None

                if new_step >= chain_row["total_steps"]:
                    new_status = "completed"
                    completed_at = now
                    # Award final chain rewards
                    await _award_chain_final_rewards(
                        conn, chain_row, user_id,
                    )

                await conn.execute(
                    """UPDATE user_chain_progress
                       SET current_step = $1, status = $2, completed_at = $3
                       WHERE chain_id = $4 AND user_id = $5""",
                    new_step, new_status, completed_at, chain_id, user_id,
                )
                progress = await conn.fetchrow(
                    "SELECT * FROM user_chain_progress WHERE chain_id = $1 AND user_id = $2",
                    chain_id, user_id,
                )

    return _row_to_progress(progress) if progress else None


async def _award_chain_final_rewards(
    conn: asyncpg.Connection,
    chain_row,
    user_id: str,
) -> None:
    """Grant final XP bonus and badge when a chain is fully completed."""
    xp_bonus = chain_row["final_xp_bonus"] or 0
    badge_id = chain_row.get("final_badge_id")

    if xp_bonus > 0:
        user_row = await conn.fetchrow("SELECT * FROM users WHERE id = $1 FOR UPDATE", user_id)
        if user_row:
            new_xp = user_row["xp"] + xp_bonus
            current_grade = GradeEnum(user_row["grade"])
            level_up, new_grade, new_level, _promoted = check_level_up(new_xp, current_grade)
            new_xp_to_next = calculate_xp_to_next(new_xp, new_grade)
            await conn.execute(
                "UPDATE users SET xp = $1, level = $2, grade = $3, xp_to_next = $4 WHERE id = $5",
                new_xp, new_level, new_grade.value, new_xp_to_next, user_id,
            )
            logger.info(f"Chain final XP bonus: user={user_id}, xp_bonus={xp_bonus}, chain={chain_row['id']}")

    if badge_id:
        # Award the badge directly
        ub_id = f"ub_{uuid.uuid4().hex[:12]}"
        now_ts = datetime.now(timezone.utc)
        await conn.execute(
            """INSERT INTO user_badges (id, user_id, badge_id, earned_at)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (user_id, badge_id) DO NOTHING""",
            ub_id, user_id, badge_id, now_ts,
        )
        logger.info(f"Chain final badge: user={user_id}, badge={badge_id}, chain={chain_row['id']}")


async def get_user_chain_progress_list(
    conn: asyncpg.Connection,
    user_id: str,
) -> list[UserChainProgress]:
    """Get all chain progress entries for a user."""
    rows = await conn.fetch(
        "SELECT * FROM user_chain_progress WHERE user_id = $1 ORDER BY started_at DESC",
        user_id,
    )
    return [_row_to_progress(r) for r in rows]
