/**
 * Shared TypeScript types for the QuestionWork frontend.
 *
 * Interfaces that are used across multiple pages/components live here
 * to avoid copy-paste duplication.
 */

import type { UserGrade, QuestStatus } from "@/lib/api";

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
  amount: number;
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
  old_value: string | null;
  new_value: string | null;
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
  amount: number;
  currency: string;
}

/** Result from PATCH /admin/withdrawals/:id/reject */
export interface WithdrawalRejectResult {
  transaction_id: string;
  status: "rejected";
  user_id: string;
  amount: number;
  currency: string;
  reason: string;
  new_balance: number;
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
  skills: string;
  character_class: string | null;
  is_banned: boolean;
  banned_reason: string | null;
  banned_at: string | null;
  created_at: string;
  updated_at: string;
  wallets: { id: string; currency: string; balance: number; updated_at: string }[];
  badges_list: { badge_id: string; name: string; description: string; icon: string; earned_at: string }[];
  class_progress: {
    class_id: string;
    class_xp: number;
    class_level: number;
    quests_completed: number;
    consecutive_quests: number;
    perk_points_spent: number;
    rage_active_until: string | null;
    burnout_until: string | null;
  } | null;
  perks: { perk_id: string; class_id: string; unlocked_at: string }[];
}

/** Full quest detail from GET /admin/quests/:id */
export interface AdminQuestDetail {
  id: string;
  client_id: string;
  client_username: string;
  title: string;
  description: string;
  required_grade: string;
  skills: string;
  budget: number;
  currency: string;
  xp_reward: number;
  status: string;
  assigned_to: string | null;
  is_urgent: boolean;
  deadline: string | null;
  required_portfolio: boolean;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  applications: {
    id: string;
    freelancer_id: string;
    freelancer_username: string;
    freelancer_grade: string;
    cover_letter: string | null;
    proposed_price: number | null;
    created_at: string;
  }[];
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
  total_revenue: number;
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
  old_balance: number;
  new_balance: number;
  amount: number;
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
