/**
 * QuestionWork API Client
 * Клиент для взаимодействия с FastAPI backend
 *
 * Поддерживает автоматическую подстановку Bearer токена
 */

// Базовый URL API (можно вынести в .env.local)
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// In-memory access token (do not persist access tokens in localStorage)
let ACCESS_TOKEN: string | null = null;

import { triggerLogout } from "@/lib/authEvents";
import type {
  AdminUsersResponse,
  AdminTransactionsResponse,
  AdminLogsResponse,
  WithdrawalApproveResult,
  WithdrawalRejectResult,
  AdminUserDetail,
  AdminQuestDetail,
  AdminPlatformStats,
  AdminGrantXPResult,
  AdminAdjustWalletResult,
  AdminBanResult,
  AdminUnbanResult,
  AdminBroadcastResult,
} from "@/types";

/** Set current access token in memory. Called by AuthContext after login/refresh. */
export function setAccessToken(token: string | null) {
  ACCESS_TOKEN = token;
}

/** Get current access token from memory. */
export function getAccessToken(): string | null {
  return ACCESS_TOKEN;
}

// ============================================
// TypeScript интерфейсы для API ответов
// ============================================

/**
 * Характеристики пользователя (RPG статы)
 */
export interface UserStats {
  int: number;
  dex: number;
  cha: number;
}

/**
 * Бейдж достижения
 */
export interface UserBadge {
  id: string;
  name: string;
  description: string;
  icon: string;
  earned_at: string;
}

/**
 * Грейд пользователя (RPG система)
 */
export type UserGrade = "novice" | "junior" | "middle" | "senior";

/**
 * Статус квеста
 */
export type QuestStatus = "open" | "in_progress" | "completed" | "confirmed" | "cancelled";

/**
 * Квест (заказ) на бирже
 */
export interface Quest {
  id: string;
  client_id: string;
  client_username?: string;
  title: string;
  description: string;
  required_grade: UserGrade;
  skills: string[];
  budget: number;
  currency: string;
  xp_reward: number;
  status: QuestStatus;
  applications: string[];
  assigned_to: string | null;
  is_urgent: boolean;
  deadline: string | null;
  required_portfolio: boolean;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

/**
 * Данные для создания квеста
 */
export interface QuestCreate {
  title: string;
  description: string;
  required_grade?: UserGrade;
  skills?: string[];
  budget: number;
  currency?: string;
  xp_reward?: number;
}

/**
 * Отклик на квест
 */
export interface QuestApplication {
  id: string;
  quest_id: string;
  freelancer_id: string;
  freelancer_username: string;
  freelancer_grade: UserGrade;
  cover_letter?: string;
  proposed_price?: number;
  created_at: string;
}

/**
 * Данные для создания отклика
 */
export interface QuestApplicationCreate {
  cover_letter?: string;
  proposed_price?: number;
}

/**
 * Профиль пользователя (полный ответ от API)
 */
export interface UserProfile {
  id: string;
  username: string;
  email: string | null;
  role: "client" | "freelancer" | "admin";
  level: number;
  grade: UserGrade;
  xp: number;
  xp_to_next: number;
  stats: UserStats;
  badges: UserBadge[];
  bio: string | null;
  skills: string[];
  character_class: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Ответ с токеном (после логина/регистрации)
 */
export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

/**
 * Данные для регистрации
 */
export interface RegisterData {
  username: string;
  email: string;
  password: string;
  role: "client" | "freelancer" | "admin";
}

/**
 * Данные для входа
 */
export interface LoginData {
  username: string;
  password: string;
}

/**
 * Ошибка API
 */
export interface ApiError {
  status: number;
  message: string;
  detail?: string;
}

/**
 * Ответ со списком квестов (пагинация)
 */
export interface QuestListResponse {
  quests: Quest[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// ============================================
// Вспомогательные функции
// ============================================

/**
 * Получить токен из localStorage
 */
// Deprecated: token is now kept in-memory. Use `getAccessToken()`.
export function getAuthToken(): string | null {
  return getAccessToken();
}

/**
 * Выполнение fetch запроса с обработкой ошибок и токеном
 */
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
  _requireAuth: boolean = false,
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  // Always include the bearer token if one is in memory.
  // requireAuth is only used to make the token mandatory (future use).
  const token = getAccessToken();

  const defaultOptions: RequestInit = {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  };

  const config = { ...defaultOptions, ...options };

  if (options?.headers) {
    config.headers = {
      ...defaultOptions.headers,
      ...options.headers,
    };
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);
    // Include credentials so httpOnly refresh cookie is sent on same-site flows
    const response = await fetch(url, { ...config, signal: controller.signal, credentials: "include" });
    clearTimeout(timeoutId);

    // If unauthorized, attempt to refresh using httpOnly refresh cookie.
    // Skip this interception for auth endpoints (login/register/refresh) —
    // a 401 there means bad credentials, not an expired token.
    const isAuthEndpoint = url.includes("/auth/login") || url.includes("/auth/register") || url.includes("/auth/refresh");
    if (response.status === 401 && !isAuthEndpoint) {
      // Try refresh endpoint once
      try {
        const refreshResp = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });

        if (refreshResp.ok) {
          const refreshed = await refreshResp.json();
          // server returns TokenResponse with access_token and user
          setAccessToken(refreshed.access_token);
          // retry original request once with new token
          const retryHeaders = { ...(config.headers as Record<string, string>), Authorization: `Bearer ${refreshed.access_token}` };
          const retryResp = await fetch(url, { ...config, headers: retryHeaders, credentials: "include" });
          if (!retryResp.ok) {
            let err = retryResp.statusText;
            try {
              const errorData = await retryResp.json();
              err = errorData.detail || errorData.message || err;
            } catch {}
            throw new Response(`API Error: ${err}`, { status: retryResp.status, statusText: err });
          }
          if (retryResp.status === 204) return {} as T;
          return await retryResp.json();
        }
      } catch (_err) {
        // fallthrough to clean-up below
      }

      // If refresh failed, clear in-memory token and stored user and surface 401.
      // Only trigger a forced logout+redirect if the user was previously authenticated
      // (had a token). Anonymous users hitting a protected endpoint just get an error.
      const hadToken = !!getAccessToken();
      setAccessToken(null);
      if (typeof window !== "undefined") {
        localStorage.removeItem("questionwork_user");
      }
      if (hadToken) {
        triggerLogout();
      }

      throw new Response("Сессия истекла. Пожалуйста, войдите снова.", {
        status: 401,
        statusText: "Unauthorized",
      });
    }

    if (!response.ok) {
      let errorDetail = response.statusText;
      try {
        const errorData = await response.json();
        errorDetail =
          errorData.detail || errorData.message || response.statusText;
      } catch {
        // Не удалось распарсить
      }

      throw new Response(`API Error: ${errorDetail}`, {
        status: response.status,
        statusText: errorDetail,
      });
    }

    if (response.status === 204) {
      return {} as T;
    }

    return await response.json();
  } catch (error) {
    throw error;
  }
}

// ============================================
// User API функции
// ============================================

export async function getUserProfile(userId: string): Promise<UserProfile> {
  return fetchApi<UserProfile>(`/users/${userId}`);
}

export async function getUserStats(userId: string): Promise<UserStats> {
  return fetchApi<UserStats>(`/users/${userId}/stats`);
}

export async function getAllUsers(
  skip: number = 0,
  limit: number = 10,
  grade?: UserGrade,
): Promise<UserProfile[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  });

  if (grade) {
    params.append("grade", grade);
  }

  return fetchApi<UserProfile[]>(`/users?${params.toString()}`);
}

export async function register(data: RegisterData): Promise<TokenResponse> {
  return fetchApi<TokenResponse>(
    "/auth/register",
    {
      method: "POST",
      body: JSON.stringify(data),
    },
    false,
  );
}

export async function login(credentials: LoginData): Promise<TokenResponse> {
  const resp = await fetchApi<TokenResponse>(
    "/auth/login",
    {
      method: "POST",
      body: JSON.stringify(credentials),
    },
    false,
  );
  // store access token in memory only; cookie holds refresh token (httpOnly)
  setAccessToken(resp.access_token);
  return resp;
}

export async function logout(): Promise<{ message: string }> {
  // call logout to clear refresh cookie server-side, then clear client state
  try {
    const result = await fetchApi<{ message: string }>(
      "/auth/logout",
      {
        method: "POST",
      },
      true,
    );
    setAccessToken(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("questionwork_user");
    }
    return result;
  } catch (err) {
    // ensure client-side cleanup on any error
    setAccessToken(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("questionwork_user");
    }
    throw err;
  }
}

export async function checkHealth(): Promise<{
  status: string;
  message: string;
}> {
  const baseUrl = API_BASE_URL.replace("/api/v1", "");
  const response = await fetch(`${baseUrl}/health`);
  return await response.json();
}

// ============================================
// Quest API функции
// ============================================

/**
 * Получить список квестов с фильтрацией
 */
export async function getQuests(
  page: number = 1,
  pageSize: number = 10,
  filters?: {
    status?: QuestStatus;
    grade?: UserGrade;
    skill?: string;
    minBudget?: number;
    maxBudget?: number;
  },
): Promise<QuestListResponse> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
  });

  if (filters) {
    if (filters.status) params.append("status_filter", filters.status);
    if (filters.grade) params.append("grade_filter", filters.grade);
    if (filters.skill) params.append("skill_filter", filters.skill);
    if (filters.minBudget !== undefined)
      params.append("min_budget", filters.minBudget.toString());
    if (filters.maxBudget !== undefined)
      params.append("max_budget", filters.maxBudget.toString());
  }

  return fetchApi<QuestListResponse>(`/quests?${params.toString()}`);
}

/**
 * Получить детали квеста по ID
 */
export async function getQuest(questId: string): Promise<Quest> {
  return fetchApi<Quest>(`/quests/${questId}`);
}

/**
 * Создать новый квест
 */
export async function createQuest(questData: QuestCreate): Promise<Quest> {
  return fetchApi<Quest>(
    "/quests/",
    {
      method: "POST",
      body: JSON.stringify(questData),
    },
    true,
  );
}

/**
 * Откликнуться на квест
 */
export async function applyToQuest(
  questId: string,
  applicationData: QuestApplicationCreate,
): Promise<{ message: string; application: QuestApplication }> {
  return fetchApi<{ message: string; application: QuestApplication }>(
    `/quests/${questId}/apply`,
    {
      method: "POST",
      body: JSON.stringify(applicationData),
    },
    true,
  );
}

/**
 * Назначить исполнителя на квест
 */
export async function assignQuest(
  questId: string,
  freelancerId: string,
): Promise<{ message: string; quest: Quest }> {
  return fetchApi<{ message: string; quest: Quest }>(
    `/quests/${questId}/assign?freelancer_id=${freelancerId}`,
    {
      method: "POST",
    },
    true,
  );
}

/**
 * Завершить квест (исполнитель)
 */
export async function completeQuest(
  questId: string,
): Promise<{ message: string; quest: Quest; xp_earned: number }> {
  return fetchApi<{ message: string; quest: Quest; xp_earned: number }>(
    `/quests/${questId}/complete`,
    {
      method: "POST",
    },
    true,
  );
}

/**
 * Подтвердить завершение квеста (клиент)
 */
export async function confirmQuest(questId: string): Promise<{
  message: string;
  quest: Quest;
  xp_reward: number;
  money_reward: number;
}> {
  return fetchApi<{
    message: string;
    quest: Quest;
    xp_reward: number;
    money_reward: number;
  }>(
    `/quests/${questId}/confirm`,
    {
      method: "POST",
    },
    true,
  );
}

/**
 * Отменить квест (клиент)
 */
export async function cancelQuest(
  questId: string,
): Promise<{ message: string; quest: Quest }> {
  return fetchApi<{ message: string; quest: Quest }>(
    `/quests/${questId}/cancel`,
    {
      method: "POST",
    },
    true,
  );
}

/**
 * Получить отклики на квест
 */
export async function getQuestApplications(
  questId: string,
): Promise<{ applications: QuestApplication[]; total: number }> {
  return fetchApi<{ applications: QuestApplication[]; total: number }>(
    `/quests/${questId}/applications`,
    {},
    true,
  );
}

// ============================================
// Wallet API
// ============================================

export interface WalletBalanceItem {
  currency: string;
  balance: number;
}

export interface WalletBalanceResponse {
  user_id: string;
  balances: WalletBalanceItem[];
  total_earned?: number;
}

export interface WalletTransaction {
  id: string;
  user_id: string;
  quest_id: string | null;
  amount: number;
  currency: string;
  type: string;
  status?: "pending" | "completed" | "rejected";
  created_at: string;
}

export interface WalletTransactionsResponse {
  user_id: string;
  transactions: WalletTransaction[];
  limit: number;
  offset: number;
}

export interface WithdrawalResponse {
  transaction_id: string;
  amount: number;
  currency: string;
  status: string;
  new_balance: number;
}

export async function getWalletBalance(): Promise<WalletBalanceResponse> {
  return fetchApi<WalletBalanceResponse>("/wallet/balance", undefined, true);
}

export async function getWalletTransactions(
  limit = 50,
  offset = 0,
): Promise<WalletTransactionsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return fetchApi<WalletTransactionsResponse>(
    `/wallet/transactions?${params}`,
    undefined,
    true,
  );
}

export async function requestWithdrawal(
  amount: number,
  currency = "RUB",
): Promise<WithdrawalResponse> {
  return fetchApi<WithdrawalResponse>(
    "/wallet/withdraw",
    {
      method: "POST",
      body: JSON.stringify({ amount, currency }),
    },
    true,
  );
}

// ============================================
// Reviews API
// ============================================

export interface Review {
  id: string;
  quest_id: string;
  reviewer_id: string;
  reviewer_username?: string | null;
  reviewee_id: string;
  rating: number;
  comment?: string | null;
  created_at: string;
  xp_bonus?: number;
}

export interface UserReviewsResponse {
  reviews: Review[];
  total: number;
  avg_rating: number | null;
  review_count: number;
}

export interface CreateReviewPayload {
  quest_id: string;
  reviewee_id: string;
  rating: number;
  comment?: string;
}

export async function createReview(payload: CreateReviewPayload): Promise<Review> {
  return fetchApi<Review>(
    "/reviews/",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    true,
  );
}

export async function getUserReviews(
  userId: string,
  limit = 20,
  offset = 0,
): Promise<UserReviewsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return fetchApi<UserReviewsResponse>(`/reviews/user/${userId}?${params}`, undefined, false);
}

// ============================================
// Quest Messages API
// ============================================

export interface QuestMessage {
  id: string;
  quest_id: string;
  author_id: string;
  author_username?: string | null;
  text: string;
  created_at: string;
}

export interface QuestMessageListResponse {
  messages: QuestMessage[];
  total: number;
}

export async function getQuestMessages(
  questId: string,
  limit = 50,
  before?: string,
): Promise<QuestMessageListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (before) params.set("before", before);
  return fetchApi<QuestMessageListResponse>(
    `/messages/${questId}?${params}`,
    undefined,
    true,
  );
}

export async function sendQuestMessage(
  questId: string,
  body: { text: string },
): Promise<QuestMessage> {
  return fetchApi<QuestMessage>(
    `/messages/${questId}`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    true,
  );
}

// ============================================
// Quest Templates API
// ============================================

export interface QuestTemplate {
  id: string;
  owner_id: string;
  name: string;
  title: string;
  description: string;
  required_grade: UserGrade;
  skills: string[];
  budget: number;
  currency: string;
  is_urgent: boolean;
  required_portfolio: boolean;
  created_at: string;
  updated_at: string;
}

export interface TemplateListResponse {
  templates: QuestTemplate[];
  total: number;
}

export interface CreateTemplatePayload {
  name: string;
  title: string;
  description?: string;
  required_grade?: string;
  skills?: string[];
  budget?: number;
  currency?: string;
  is_urgent?: boolean;
  required_portfolio?: boolean;
}

export async function getTemplates(
  limit = 50,
  offset = 0,
): Promise<TemplateListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return fetchApi<TemplateListResponse>(`/templates/?${params}`, undefined, true);
}

export async function createTemplate(
  payload: CreateTemplatePayload,
): Promise<QuestTemplate> {
  return fetchApi<QuestTemplate>(
    "/templates/",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    true,
  );
}

export async function deleteTemplate(templateId: string): Promise<void> {
  await fetchApi<void>(`/templates/${templateId}`, { method: "DELETE" }, true);
}

export async function createQuestFromTemplate(
  templateId: string,
  overrides?: {
    title?: string;
    description?: string;
    budget?: number;
    is_urgent?: boolean;
    deadline?: string;
  },
): Promise<Quest> {
  return fetchApi<Quest>(
    `/templates/${templateId}/create-quest`,
    {
      method: "POST",
      body: JSON.stringify(overrides ?? {}),
    },
    true,
  );
}

// ============================================
// Badges & Notifications
// ============================================

/**
 * Badge from the platform catalogue.
 */
export interface Badge {
  id: string;
  name: string;
  description: string;
  icon: string;
  criteria_type: string;
  criteria_value: number;
}

/**
 * Badge earned by a user.
 */
export interface UserBadgeEarned {
  id: string;
  user_id: string;
  badge_id: string;
  badge_name: string;
  badge_description: string;
  badge_icon: string;
  earned_at: string;
}

/**
 * In-app notification.
 */
export interface Notification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  event_type: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: Notification[];
  total: number;
  unread_count: number;
}

// ============================================
// Notification API functions
// ============================================

/**
 * Fetch notifications for the authenticated user.
 */
export async function getNotifications(
  limit = 50,
  offset = 0,
  unreadOnly = false,
): Promise<NotificationListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    unread_only: String(unreadOnly),
  });
  return fetchApi<NotificationListResponse>(
    `/notifications?${params.toString()}`,
    {},
    true,
  );
}

/**
 * Mark a single notification as read.
 */
export async function markNotificationRead(
  notificationId: string,
): Promise<{ id: string; is_read: boolean }> {
  return fetchApi<{ id: string; is_read: boolean }>(
    `/notifications/${notificationId}/read`,
    { method: "PATCH" },
    true,
  );
}

/**
 * Mark all notifications as read.
 */
export async function markAllNotificationsRead(): Promise<{
  marked_read: number;
}> {
  return fetchApi<{ marked_read: number }>(
    `/notifications/read-all`,
    { method: "POST" },
    true,
  );
}

// ============================================
// Badge API functions
// ============================================

/**
 * Fetch the full badge catalogue.
 */
export async function getBadgeCatalogue(): Promise<{ badges: Badge[] }> {
  return fetchApi<{ badges: Badge[] }>(`/badges/catalogue`, {}, false);
}

/**
 * Fetch badges earned by the authenticated user.
 */
export async function getMyBadges(): Promise<{
  user_id: string;
  badges: UserBadgeEarned[];
  total: number;
}> {
  return fetchApi<{ user_id: string; badges: UserBadgeEarned[]; total: number }>(
    `/badges/me`,
    {},
    true,
  );
}

/**
 * Fetch badges earned by any user (public).
 */
export async function getUserBadges(userId: string): Promise<{
  user_id: string;
  badges: UserBadgeEarned[];
  total: number;
}> {
  return fetchApi<{ user_id: string; badges: UserBadgeEarned[]; total: number }>(
    `/badges/${userId}`,
    {},
    false,
  );
}

// ============================================
// Character Class types
// ============================================

export interface ClassBonusInfo {
  key: string;
  label: string;
  value: number | boolean;
  is_weakness: boolean;
}

export interface CharacterClassInfo {
  class_id: string;
  name: string;
  name_ru: string;
  icon: string;
  color: string;
  description: string;
  description_ru: string;
  min_unlock_level: number;
  bonuses: ClassBonusInfo[];
  weaknesses: ClassBonusInfo[];
  perk_count: number;
  ability_count: number;
}

export interface UserClassInfo {
  class_id: string;
  name: string;
  name_ru: string;
  icon: string;
  color: string;
  class_level: number;
  class_xp: number;
  class_xp_to_next: number;
  quests_completed_as_class: number;
  consecutive_quests: number;
  is_trial: boolean;
  trial_expires_at: string | null;
  active_bonuses: ClassBonusInfo[];
  weaknesses: ClassBonusInfo[];
  is_burnout: boolean;
  burnout_until: string | null;
  // Phase 2
  perk_points_total: number;
  perk_points_spent: number;
  perk_points_available: number;
  unlocked_perks: string[];
  rage_active: boolean;
  rage_active_until: string | null;
}

export interface ClassListResponse {
  classes: CharacterClassInfo[];
  user_level: number;
  current_class: string | null;
}

export interface ClassSelectResponse {
  message: string;
  class_info: UserClassInfo;
}

// ============================================
// Class API functions
// ============================================

export async function getClasses(): Promise<ClassListResponse> {
  return fetchApi<ClassListResponse>(`/classes/`, {}, true);
}

export async function getMyClass(): Promise<UserClassInfo> {
  return fetchApi<UserClassInfo>(`/classes/me`, {}, true);
}

export async function selectClass(classId: string): Promise<ClassSelectResponse> {
  return fetchApi<ClassSelectResponse>(
    `/classes/select`,
    { method: "POST", body: JSON.stringify({ class_id: classId }) },
    true,
  );
}

export async function confirmClass(): Promise<ClassSelectResponse> {
  return fetchApi<ClassSelectResponse>(
    `/classes/confirm`,
    { method: "POST" },
    true,
  );
}

export async function resetClass(): Promise<{ message: string }> {
  return fetchApi<{ message: string }>(
    `/classes/reset`,
    { method: "POST" },
    true,
  );
}

// ============================================
// Phase 2: Perk & Ability types
// ============================================

export interface PerkInfo {
  perk_id: string;
  name: string;
  name_ru: string;
  description_ru: string;
  icon: string;
  tier: number;
  required_class_level: number;
  perk_point_cost: number;
  prerequisite_ids: string[];
  effects: Record<string, number | boolean>;
  is_unlocked: boolean;
  can_unlock: boolean;
  lock_reason: string | null;
}

export interface PerkTreeResponse {
  class_id: string;
  perks: PerkInfo[];
  perk_points_total: number;
  perk_points_spent: number;
  perk_points_available: number;
}

export interface PerkUnlockResponse {
  message: string;
  perk: PerkInfo;
  perk_points_available: number;
}

export interface AbilityInfo {
  ability_id: string;
  name: string;
  name_ru: string;
  description_ru: string;
  icon: string;
  required_class_level: number;
  cooldown_hours: number;
  duration_hours: number;
  effects: Record<string, number | boolean>;
  is_unlocked: boolean;
  is_active: boolean;
  active_until: string | null;
  is_on_cooldown: boolean;
  cooldown_until: string | null;
  times_used: number;
}

export interface AbilityActivateResponse {
  message: string;
  ability: AbilityInfo;
}

// ============================================
// Phase 2: Perk & Ability API functions
// ============================================

export async function getPerkTree(): Promise<PerkTreeResponse> {
  return fetchApi<PerkTreeResponse>(`/classes/perks`, {}, true);
}

export async function unlockPerk(perkId: string): Promise<PerkUnlockResponse> {
  return fetchApi<PerkUnlockResponse>(
    `/classes/perks/unlock`,
    { method: "POST", body: JSON.stringify({ perk_id: perkId }) },
    true,
  );
}

export async function getAbilities(): Promise<AbilityInfo[]> {
  return fetchApi<AbilityInfo[]>(`/classes/abilities`, {}, true);
}

export async function activateAbility(abilityId: string): Promise<AbilityActivateResponse> {
  return fetchApi<AbilityActivateResponse>(
    `/classes/abilities/activate`,
    { method: "POST", body: JSON.stringify({ ability_id: abilityId }) },
    true,
  );
}

// ============================================
// Admin API
// ============================================

/** GET /admin/users — paginated user list */
export async function adminGetUsers(
  page = 1,
  pageSize = 50,
  role?: string,
): Promise<AdminUsersResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (role) params.set("role", role);
  return fetchApi<AdminUsersResponse>(`/admin/users?${params}`, undefined, true);
}

/** GET /admin/transactions — filtered transaction list */
export async function adminGetTransactions(
  page = 1,
  pageSize = 50,
  filters?: { status?: string; type?: string; user_id?: string },
): Promise<AdminTransactionsResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (filters?.status) params.set("status", filters.status);
  if (filters?.type) params.set("type", filters.type);
  if (filters?.user_id) params.set("user_id", filters.user_id);
  return fetchApi<AdminTransactionsResponse>(`/admin/transactions?${params}`, undefined, true);
}

/** GET /admin/withdrawals/pending — pending withdrawal queue */
export async function adminGetPendingWithdrawals(
  page = 1,
  pageSize = 50,
): Promise<AdminTransactionsResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return fetchApi<AdminTransactionsResponse>(`/admin/withdrawals/pending?${params}`, undefined, true);
}

/** PATCH /admin/withdrawals/:id/approve */
export async function adminApproveWithdrawal(
  transactionId: string,
): Promise<WithdrawalApproveResult> {
  return fetchApi<WithdrawalApproveResult>(
    `/admin/withdrawals/${transactionId}/approve`,
    { method: "PATCH" },
    true,
  );
}

/** PATCH /admin/withdrawals/:id/reject */
export async function adminRejectWithdrawal(
  transactionId: string,
  reason: string,
): Promise<WithdrawalRejectResult> {
  return fetchApi<WithdrawalRejectResult>(
    `/admin/withdrawals/${transactionId}/reject`,
    { method: "PATCH", body: JSON.stringify({ reason }) },
    true,
  );
}

/** GET /admin/logs — audit log history */
export async function adminGetLogs(
  page = 1,
  pageSize = 50,
  adminId?: string,
): Promise<AdminLogsResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (adminId) params.set("admin_id", adminId);
  return fetchApi<AdminLogsResponse>(`/admin/logs?${params}`, undefined, true);
}

/** POST /admin/maintenance/cleanup-notifications */
export async function adminCleanupNotifications(): Promise<{
  deleted: number;
  message: string;
}> {
  return fetchApi(`/admin/maintenance/cleanup-notifications`, { method: "POST" }, true);
}


// ============================================
// Admin God Mode
// ============================================

/** GET /admin/stats — Platform-wide statistics */
export async function adminGetPlatformStats(): Promise<AdminPlatformStats> {
  return fetchApi<AdminPlatformStats>("/admin/stats", undefined, true);
}

/** GET /admin/users/:id — Full user detail */
export async function adminGetUserDetail(userId: string): Promise<AdminUserDetail> {
  return fetchApi<AdminUserDetail>(`/admin/users/${userId}`, undefined, true);
}

/** PATCH /admin/users/:id — Edit user fields */
export async function adminUpdateUser(userId: string, data: Record<string, unknown>): Promise<{ user_id: string; updated_fields: string[] }> {
  return fetchApi(`/admin/users/${userId}`, { method: "PATCH", body: JSON.stringify(data) }, true);
}

/** POST /admin/users/:id/ban */
export async function adminBanUser(userId: string, reason: string): Promise<AdminBanResult> {
  return fetchApi<AdminBanResult>(`/admin/users/${userId}/ban`, { method: "POST", body: JSON.stringify({ reason }) }, true);
}

/** POST /admin/users/:id/unban */
export async function adminUnbanUser(userId: string): Promise<AdminUnbanResult> {
  return fetchApi<AdminUnbanResult>(`/admin/users/${userId}/unban`, { method: "POST" }, true);
}

/** DELETE /admin/users/:id */
export async function adminDeleteUser(userId: string): Promise<{ user_id: string; username: string; deleted: boolean }> {
  return fetchApi(`/admin/users/${userId}`, { method: "DELETE" }, true);
}

/** POST /admin/users/:id/grant-xp */
export async function adminGrantXP(userId: string, amount: number, reason: string): Promise<AdminGrantXPResult> {
  return fetchApi<AdminGrantXPResult>(`/admin/users/${userId}/grant-xp`, { method: "POST", body: JSON.stringify({ amount, reason }) }, true);
}

/** POST /admin/users/:id/adjust-wallet */
export async function adminAdjustWallet(userId: string, amount: number, currency: string, reason: string): Promise<AdminAdjustWalletResult> {
  return fetchApi<AdminAdjustWalletResult>(`/admin/users/${userId}/adjust-wallet`, { method: "POST", body: JSON.stringify({ amount, currency, reason }) }, true);
}

/** POST /admin/users/:id/grant-badge */
export async function adminGrantBadge(userId: string, badgeId: string): Promise<{ user_id: string; badge_id: string; badge_name: string }> {
  return fetchApi(`/admin/users/${userId}/grant-badge`, { method: "POST", body: JSON.stringify({ badge_id: badgeId }) }, true);
}

/** DELETE /admin/users/:id/badges/:badgeId */
export async function adminRevokeBadge(userId: string, badgeId: string): Promise<{ user_id: string; badge_id: string; revoked: boolean }> {
  return fetchApi(`/admin/users/${userId}/badges/${badgeId}`, { method: "DELETE" }, true);
}

/** POST /admin/users/:id/change-class */
export async function adminChangeUserClass(userId: string, classId: string | null): Promise<{ user_id: string; old_class: string | null; new_class: string | null }> {
  return fetchApi(`/admin/users/${userId}/change-class`, { method: "POST", body: JSON.stringify({ class_id: classId }) }, true);
}

/** GET /admin/quests/:id — Full quest detail */
export async function adminGetQuestDetail(questId: string): Promise<AdminQuestDetail> {
  return fetchApi<AdminQuestDetail>(`/admin/quests/${questId}`, undefined, true);
}

/** PATCH /admin/quests/:id — Edit quest fields */
export async function adminUpdateQuest(questId: string, data: Record<string, unknown>): Promise<{ quest_id: string; updated_fields: string[] }> {
  return fetchApi(`/admin/quests/${questId}`, { method: "PATCH", body: JSON.stringify(data) }, true);
}

/** POST /admin/quests/:id/force-cancel */
export async function adminForceCancel(questId: string, reason: string): Promise<{ quest_id: string; old_status: string; new_status: string; reason: string }> {
  return fetchApi(`/admin/quests/${questId}/force-cancel`, { method: "POST", body: JSON.stringify({ reason }) }, true);
}

/** POST /admin/quests/:id/force-complete */
export async function adminForceComplete(questId: string, reason: string): Promise<{ quest_id: string; old_status: string; new_status: string; reason: string }> {
  return fetchApi(`/admin/quests/${questId}/force-complete`, { method: "POST", body: JSON.stringify({ reason }) }, true);
}

/** DELETE /admin/quests/:id */
export async function adminDeleteQuest(questId: string): Promise<{ quest_id: string; title: string; deleted: boolean }> {
  return fetchApi(`/admin/quests/${questId}`, { method: "DELETE" }, true);
}

/** POST /admin/notifications/broadcast */
export async function adminBroadcastNotification(
  userIds: string[], title: string, message: string, eventType?: string
): Promise<AdminBroadcastResult> {
  return fetchApi<AdminBroadcastResult>("/admin/notifications/broadcast", {
    method: "POST",
    body: JSON.stringify({ user_ids: userIds, title, message, event_type: eventType || "admin_broadcast" }),
  }, true);
}

// ============================================
// Экспорт по умолчанию
// ============================================

const api = {
  // User
  getUserProfile,
  getUserStats,
  getAllUsers,
  register,
  login,
  logout,
  checkHealth,
  // Quest
  getQuests,
  getQuest,
  createQuest,
  applyToQuest,
  assignQuest,
  completeQuest,
  confirmQuest,
  cancelQuest,
  getQuestApplications,
  getAuthToken,
  // Notifications
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  // Badges
  getBadgeCatalogue,
  getMyBadges,
  getUserBadges,
  // Classes
  getClasses,
  getMyClass,
  selectClass,
  confirmClass,
  resetClass,
  // Phase 2: Perks & Abilities
  getPerkTree,
  unlockPerk,
  getAbilities,
  activateAbility,
  // Admin
  adminGetUsers,
  adminGetTransactions,
  adminGetPendingWithdrawals,
  adminApproveWithdrawal,
  adminRejectWithdrawal,
  adminGetLogs,
  adminCleanupNotifications,
  // Admin God Mode
  adminGetPlatformStats,
  adminGetUserDetail,
  adminUpdateUser,
  adminBanUser,
  adminUnbanUser,
  adminDeleteUser,
  adminGrantXP,
  adminAdjustWallet,
  adminGrantBadge,
  adminRevokeBadge,
  adminChangeUserClass,
  adminGetQuestDetail,
  adminUpdateQuest,
  adminForceCancel,
  adminForceComplete,
  adminDeleteQuest,
  adminBroadcastNotification,
};

export default api;
