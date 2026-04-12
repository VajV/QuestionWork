from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AdminUserWalletResponse(BaseModel):
    id: str
    currency: str
    balance: Decimal
    updated_at: datetime


class AdminUserBadgeResponse(BaseModel):
    badge_id: str
    name: str
    description: str
    icon: str
    earned_at: datetime


class AdminClassProgressResponse(BaseModel):
    class_id: str
    class_xp: int
    class_level: int
    quests_completed: int
    consecutive_quests: int
    perk_points_total: int
    perk_points_spent: int
    perk_points_available: int
    bonus_perk_points: int
    rage_active_until: datetime | None = None
    burnout_until: datetime | None = None


class AdminUserPerkResponse(BaseModel):
    perk_id: str
    class_id: str
    unlocked_at: datetime


class AdminUserDetailResponse(BaseModel):
    id: str
    username: str
    email: str | None = None
    role: str
    level: int
    grade: str
    xp: int
    xp_to_next: int
    stat_points: int
    stats_int: int
    stats_dex: int
    stats_cha: int
    bio: str | None = None
    skills: list[str]
    character_class: str | None = None
    is_banned: bool
    banned_reason: str | None = None
    banned_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    wallets: list[AdminUserWalletResponse]
    badges_list: list[AdminUserBadgeResponse]
    class_progress: AdminClassProgressResponse | None = None
    perks: list[AdminUserPerkResponse]

    model_config = ConfigDict(extra="ignore")


class AdminQuestApplicationDetailResponse(BaseModel):
    id: str
    freelancer_id: str
    freelancer_username: str
    freelancer_grade: str
    cover_letter: str | None = None
    proposed_price: Decimal | None = None
    created_at: datetime

    model_config = ConfigDict(extra="ignore")


class AdminQuestDetailResponse(BaseModel):
    id: str
    client_id: str
    client_username: str
    title: str
    description: str
    required_grade: str
    skills: list[str]
    budget: Decimal
    currency: str
    xp_reward: int
    status: str
    assigned_to: str | None = None
    is_urgent: bool
    deadline: datetime | None = None
    required_portfolio: bool
    delivery_note: str | None = None
    delivery_url: str | None = None
    delivery_submitted_at: datetime | None = None
    revision_reason: str | None = None
    revision_requested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    applications: list[AdminQuestApplicationDetailResponse]

    model_config = ConfigDict(extra="ignore")


class AdminPlatformStatsResponse(BaseModel):
    total_users: int
    users_by_role: dict[str, int]
    banned_users: int
    total_quests: int
    quests_by_status: dict[str, int]
    total_transactions: int
    pending_withdrawals: int
    total_revenue: Decimal
    users_today: int
    quests_today: int


class AdminGuildSeasonRewardConfigResponse(BaseModel):
    id: str
    season_code: str
    family: str
    label: str
    accent: str
    treasury_bonus: Decimal
    guild_tokens_bonus: int = Field(ge=0)
    badge_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── List / paginated response wrappers ──────────────────────────────


class AdminUserSummary(BaseModel):
    id: str
    username: str
    email: str | None = None
    role: str
    grade: str
    level: int
    xp: int
    is_banned: bool
    banned_reason: str | None = None
    created_at: datetime

    model_config = ConfigDict(extra="ignore")


class AdminUsersListResponse(BaseModel):
    users: list[AdminUserSummary]
    total: int
    page: int
    page_size: int
    has_more: bool


class AdminTransactionSummary(BaseModel):
    id: str
    user_id: str
    type: str
    amount: Decimal
    currency: str
    status: str
    quest_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(extra="ignore")


class AdminTransactionsListResponse(BaseModel):
    transactions: list[AdminTransactionSummary]
    total: int
    page: int
    page_size: int
    has_more: bool


class AdminLogEntry(BaseModel):
    id: str
    admin_id: str
    action: str
    target_type: str
    target_id: str
    old_value: str | None = None
    new_value: str | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = ConfigDict(extra="ignore")


class AdminLogsListResponse(BaseModel):
    logs: list[AdminLogEntry]
    total: int
    page: int
    page_size: int


class AdminCommandLinkedJobSummary(BaseModel):
    id: str
    kind: str
    queue_name: str
    status: str
    attempt_count: int
    max_attempts: int
    queue_publish_attempts: int
    scheduled_for: datetime
    available_at: datetime
    enqueued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_error_code: str | None = None
    last_error: str | None = None

    model_config = ConfigDict(extra="ignore")


class AdminCommandStatusResponse(BaseModel):
    id: str
    command_kind: str
    status: str
    dedupe_key: str | None = None
    requested_by_user_id: str | None = None
    requested_by_admin_id: str | None = None
    request_ip: str | None = None
    request_user_agent: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    payload_json: dict | list | None = None
    result_json: dict | list | None = None
    error_code: str | None = None
    error_text: str | None = None
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    jobs: list[AdminCommandLinkedJobSummary]

    model_config = ConfigDict(extra="ignore")


class AdminJobAttemptResponse(BaseModel):
    id: str
    attempt_no: int
    worker_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    error_code: str | None = None
    error_text: str | None = None
    duration_ms: int | None = None
    external_ref: str | None = None
    created_at: datetime

    model_config = ConfigDict(extra="ignore")


class AdminJobCommandSummary(BaseModel):
    id: str
    command_kind: str
    status: str
    request_id: str | None = None
    trace_id: str | None = None
    requested_by_admin_id: str | None = None
    requested_by_user_id: str | None = None
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(extra="ignore")


class AdminJobStatusResponse(BaseModel):
    id: str
    kind: str
    queue_name: str
    status: str
    priority: int
    dedupe_key: str | None = None
    payload_json: dict | list | None = None
    scheduled_for: datetime
    available_at: datetime
    enqueued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    last_error_code: str | None = None
    last_error: str | None = None
    last_enqueue_error: str | None = None
    queue_publish_attempts: int
    attempt_count: int
    max_attempts: int
    lock_token: str | None = None
    locked_by: str | None = None
    trace_id: str | None = None
    request_id: str | None = None
    created_by_user_id: str | None = None
    created_by_admin_id: str | None = None
    command_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    created_at: datetime
    updated_at: datetime
    command: AdminJobCommandSummary | None = None
    attempts: list[AdminJobAttemptResponse]

    model_config = ConfigDict(extra="ignore")


class AdminOperationFeedEntry(BaseModel):
    command_id: str
    job_id: str | None = None
    action: str
    command_status: str
    job_kind: str | None = None
    job_status: str | None = None
    actor_admin_id: str | None = None
    actor_user_id: str | None = None
    queue_name: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(extra="ignore")


class AdminOperationsFeedResponse(BaseModel):
    items: list[AdminOperationFeedEntry]
    total: int
    page: int
    page_size: int
    has_more: bool


class AdminRuntimeHeartbeatEntry(BaseModel):
    id: str
    runtime_kind: str
    runtime_id: str
    hostname: str
    pid: int
    started_at: datetime
    last_seen_at: datetime
    meta_json: dict | list | None = None
    queue_name: str | None = None
    heartbeat_interval_seconds: int
    stale_after_seconds: int
    started_age_seconds: int
    seconds_since_last_seen: int
    is_stale: bool
    is_leader: bool | None = None
    lease_ttl_seconds: int | None = None
    lease_expires_in_seconds: int | None = None

    model_config = ConfigDict(extra="ignore")


class AdminRuntimeHeartbeatsResponse(BaseModel):
    generated_at: datetime
    active_only: bool
    total: int
    stale_total: int
    active_workers: int
    active_schedulers: int
    stale_workers: int
    stale_schedulers: int
    leader_runtime_id: str | None = None
    leader_count: int
    runtimes: list[AdminRuntimeHeartbeatEntry]


class AdminRuntimeHeartbeatPruneResponse(BaseModel):
    pruned_at: datetime
    runtime_kind: str | None = None
    stale_only: bool
    retention_seconds: int
    deleted_count: int


class AdminJobReplayRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class AdminJobReplayResponse(BaseModel):
    job_id: str
    previous_status: str
    status: str
    queue_name: str
    enqueued: bool
    message: str
    enqueue_error: str | None = None
