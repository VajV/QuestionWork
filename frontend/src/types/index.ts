/**
 * Shared TypeScript types for the QuestionWork frontend.
 *
 * Interfaces that are used across multiple pages/components live here
 * to avoid copy-paste duplication.
 */

import type { UserGrade, QuestStatus } from "@/lib/api";

export type MoneyWire = string;

// UI code should only consume normalized numeric money values.
// Decimal-like API wire values are converted in src/lib/api.ts.
export type MoneyAmount = number;

export type AdminLogValue =
  | string
  | number
  | boolean
  | null
  | AdminLogValue[]
  | { [key: string]: AdminLogValue };

/**
 * Filter state for the quest marketplace list.
 * Shared by QuestsPage and QuestFilters component.
 */
export interface QuestFilterState {
  grade?: UserGrade;
  status?: QuestStatus;
  skill?: string;
  minBudget?: number;
  maxBudget?: number;
}

export interface WalletBalanceItem {
  currency: string;
  balance: MoneyAmount;
}

export interface WalletBalanceResponse {
  user_id: string;
  balances: WalletBalanceItem[];
  total_earned: MoneyAmount;
}

export interface WalletTransaction {
  id: string;
  user_id: string;
  quest_id: string | null;
  amount: MoneyAmount;
  currency: string;
  type: string;
  status?: "pending" | "completed" | "rejected";
  created_at: string;
}

export type WalletStatementFormat = "pdf" | "csv";

export interface WalletTransactionsResponse {
  user_id: string;
  transactions: WalletTransaction[];
  limit: number;
  offset: number;
}

export interface WithdrawalResponse {
  transaction_id: string;
  amount: MoneyAmount;
  currency: string;
  status: string;
  new_balance: MoneyAmount;
}

// ─── Admin Panel Types ──────────────────────────────────────────────

/** Row returned by GET /admin/users */
export interface AdminUserRow {
  id: string;
  username: string;
  email: string | null;
  role: "client" | "freelancer" | "admin";
  grade: UserGrade;
  level: number;
  xp: number;
  is_banned: boolean;
  banned_reason: string | null;
  created_at: string;
}

export interface AdminUsersResponse {
  users: AdminUserRow[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

/** Row returned by GET /admin/transactions */
export interface AdminTransaction {
  id: string;
  user_id: string;
  type: string;
  amount: MoneyAmount;
  currency: string;
  status: "pending" | "completed" | "rejected";
  quest_id: string | null;
  created_at: string;
}

export interface AdminTransactionsResponse {
  transactions: AdminTransaction[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

/** Row returned by GET /admin/logs */
export interface AdminLogEntry {
  id: string;
  admin_id: string;
  action: string;
  target_type: string;
  target_id: string;
  old_value: AdminLogValue | null;
  new_value: AdminLogValue | null;
  ip_address: string | null;
  created_at: string;
}

export interface AdminLogsResponse {
  logs: AdminLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

/** Result from PATCH /admin/withdrawals/:id/approve */
export interface WithdrawalApproveResult {
  transaction_id: string;
  status: "completed";
  user_id: string;
  amount: MoneyAmount;
  currency: string;
}

/** Result from PATCH /admin/withdrawals/:id/reject */
export interface WithdrawalRejectResult {
  transaction_id: string;
  status: "rejected";
  user_id: string;
  amount: MoneyAmount;
  currency: string;
  reason: string;
  new_balance: MoneyAmount;
}

export interface AdminUserWallet {
  id: string;
  currency: string;
  balance: MoneyAmount;
  updated_at: string;
}

export interface AdminUserBadge {
  badge_id: string;
  name: string;
  description: string;
  icon: string;
  earned_at: string;
}

export interface AdminClassProgress {
  class_id: string;
  class_xp: number;
  class_level: number;
  quests_completed: number;
  consecutive_quests: number;
  perk_points_total: number;
  perk_points_spent: number;
  perk_points_available: number;
  bonus_perk_points: number;
  rage_active_until: string | null;
  burnout_until: string | null;
}

export interface AdminUserPerk {
  perk_id: string;
  class_id: string;
  unlocked_at: string;
}

// ─── God Mode Types ─────────────────────────────────────────────────

/** Full user detail from GET /admin/users/:id */
export interface AdminUserDetail {
  id: string;
  username: string;
  email: string | null;
  role: string;
  level: number;
  grade: string;
  xp: number;
  xp_to_next: number;
  stat_points: number;
  stats_int: number;
  stats_dex: number;
  stats_cha: number;
  bio: string | null;
  skills: string[];
  character_class: string | null;
  is_banned: boolean;
  banned_reason: string | null;
  banned_at: string | null;
  created_at: string;
  updated_at: string;
  wallets: AdminUserWallet[];
  badges_list: AdminUserBadge[];
  class_progress: AdminClassProgress | null;
  perks: AdminUserPerk[];
}

export interface AdminQuestApplicationDetail {
  id: string;
  freelancer_id: string;
  freelancer_username: string;
  freelancer_grade: string;
  cover_letter: string | null;
  proposed_price: MoneyAmount | null;
  created_at: string;
}

/** Full quest detail from GET /admin/quests/:id */
export interface AdminQuestDetail {
  id: string;
  client_id: string;
  client_username: string;
  title: string;
  description: string;
  required_grade: string;
  skills: string[];
  budget: MoneyAmount;
  currency: string;
  xp_reward: number;
  status: string;
  assigned_to: string | null;
  is_urgent: boolean;
  deadline: string | null;
  required_portfolio: boolean;
  delivery_note: string | null;
  delivery_url: string | null;
  delivery_submitted_at: string | null;
  revision_reason: string | null;
  revision_requested_at: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  applications: AdminQuestApplicationDetail[];
}

/** Platform stats from GET /admin/stats */
export interface AdminPlatformStats {
  total_users: number;
  users_by_role: Record<string, number>;
  banned_users: number;
  total_quests: number;
  quests_by_status: Record<string, number>;
  total_transactions: number;
  pending_withdrawals: number;
  total_revenue: MoneyAmount;
  users_today: number;
  quests_today: number;
}

/** Result from POST /admin/users/:id/grant-xp */
export interface AdminGrantXPResult {
  user_id: string;
  username: string;
  old_xp: number;
  new_xp: number;
  amount: number;
  old_level: number;
  new_level: number;
  old_grade: string;
  new_grade: string;
  level_up: boolean;
  levels_gained: number;
}

/** Result from POST /admin/users/:id/adjust-wallet */
export interface AdminAdjustWalletResult {
  user_id: string;
  username: string;
  old_balance: MoneyAmount;
  new_balance: MoneyAmount;
  amount: MoneyAmount;
  currency: string;
  reason: string;
}

/** Result from POST /admin/users/:id/ban */
export interface AdminBanResult {
  user_id: string;
  username: string;
  is_banned: boolean;
  reason: string;
  quests_cancelled: number;
}

/** Result from POST /admin/users/:id/unban */
export interface AdminUnbanResult {
  user_id: string;
  username: string;
  is_banned: boolean;
}

/** Result from POST /admin/notifications/broadcast */
export interface AdminBroadcastResult {
  total_recipients: number;
  sent: number;
  title: string;
}

// ─────────────────────────────────────
// Dispute resolution
// ─────────────────────────────────────

export type DisputeStatus = "open" | "responded" | "escalated" | "resolved" | "closed";
export type ResolutionType = "refund" | "partial" | "freelancer";

export interface Dispute {
  id: string;
  quest_id: string;
  initiator_id: string;
  respondent_id: string;
  reason: string;
  response_text?: string;
  status: DisputeStatus;
  resolution_type?: ResolutionType;
  partial_percent?: number;
  resolution_note?: string;
  moderator_id?: string;
  auto_escalate_at: string;
  created_at: string;
  responded_at?: string;
  escalated_at?: string;
  resolved_at?: string;
}

export interface DisputeListResponse {
  items: Dispute[];
  total: number;
}

// ─────────────────────────────────────
// Seasonal events
// ─────────────────────────────────────

export type EventStatus = "draft" | "active" | "ended" | "finalized";

export interface GameEvent {
  id: string;
  title: string;
  description: string;
  status: EventStatus;
  xp_multiplier: number;
  badge_reward_id: string | null;
  max_participants: number | null;
  participant_count: number;
  created_by: string;
  start_at: string;
  end_at: string;
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EventListResponse {
  items: GameEvent[];
  total: number;
  has_more: boolean;
}

export interface EventParticipant {
  id: string;
  event_id: string;
  user_id: string;
  username: string;
  score: number;
  joined_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  user_id: string;
  username: string;
  grade: string;
  score: number;
  xp_bonus: number;
  badge_awarded: boolean;
}

export interface EventLeaderboardResponse {
  event_id: string;
  entries: LeaderboardEntry[];
  total_participants: number;
}
