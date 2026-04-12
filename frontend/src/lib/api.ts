/**
 * QuestionWork API Client
 * Клиент для взаимодействия с FastAPI backend
 *
 * Поддерживает автоматическую подстановку Bearer токена
 */

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function resolveApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();

  if (typeof window === "undefined") {
    return trimTrailingSlash(configured || "http://127.0.0.1:8001/api/v1");
  }

  const browserHost = window.location.hostname;
  const browserProtocol = window.location.protocol;
  const isBrowserLoopback = browserHost === "localhost" || browserHost === "127.0.0.1";

  if (!configured) {
    const resolvedHost = isBrowserLoopback ? "127.0.0.1" : browserHost;
    return `${browserProtocol}//${resolvedHost}:8001/api/v1`;
  }

  try {
    const url = new URL(configured);
    const isConfiguredLoopback = url.hostname === "localhost" || url.hostname === "127.0.0.1";

    if (isBrowserLoopback && isConfiguredLoopback) {
      // Always use 127.0.0.1 for loopback: on Windows, "localhost" resolves to
      // ::1 (IPv6) before 127.0.0.1 (IPv4), but uvicorn only binds IPv4.
      url.hostname = "127.0.0.1";
      return trimTrailingSlash(url.toString());
    }

    return trimTrailingSlash(url.toString());
  } catch {
    return trimTrailingSlash(configured);
  }
}

// Базовый URL API (можно вынести в .env.local)
const API_BASE_URL = resolveApiBaseUrl();

// In-memory access token (do not persist access tokens in localStorage)
let ACCESS_TOKEN: string | null = null;
export const STORAGE_KEY_USER = "questionwork_user";
const REFRESH_RESULT_TTL_MS = 3000;

import { triggerLogout } from "@/lib/authEvents";
import {
  clearAdminTotpToken,
  getAdminTotpToken,
  isAdminTotpErrorMessage,
} from "./adminTotp";
import type {
  AdminLogValue,
  AdminUsersResponse,
  AdminTransactionsResponse,
  AdminLogsResponse,
  AdminOperationsFeedResponse,
  AdminRuntimeHeartbeatsResponse,
  AdminJobStatusResponse,
  AdminJobReplayResponse,
  AdminQuestApplicationDetail,
  WithdrawalApproveResult,
  WithdrawalRejectResult,
  AdminUserDetail,
  AdminUserWallet,
  AdminQuestDetail,
  AdminPlatformStats,
  AdminGrantXPResult,
  AdminAdjustWalletResult,
  AdminBanResult,
  AdminUnbanResult,
  AdminBroadcastResult,
  WalletBalanceResponse,
  WalletTransactionsResponse,
  WalletStatementFormat,
  WithdrawalResponse,
  MoneyAmount,
  MoneyWire,
  Dispute,
  DisputeListResponse,
  GameEvent,
  EventListResponse,
  EventParticipant,
  EventLeaderboardResponse,
} from "@/types";

export type {
  WalletBalanceItem,
  WalletBalanceResponse,
  WalletStatementFormat,
  WalletTransaction,
  WalletTransactionsResponse,
  WithdrawalResponse,
} from "@/types";

export type {
  GameEvent,
  EventListResponse,
  EventParticipant,
  EventLeaderboardResponse,
} from "@/types";

/** Set current access token in memory. Called by AuthContext after login/refresh. */
export function setAccessToken(token: string | null) {
  ACCESS_TOKEN = token;
  if (!token) {
    lastRefreshResult = null;
    lastRefreshResolvedAt = 0;
  }
}

/** Get current access token from memory. */
export function getAccessToken(): string | null {
  return ACCESS_TOKEN;
}

// Deduplication: only one refresh request in flight at a time
let refreshPromise: Promise<TokenResponse | null> | null = null;
let lastRefreshResult: TokenResponse | null = null;
let lastRefreshResolvedAt = 0;

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
export type QuestStatus = "draft" | "open" | "assigned" | "in_progress" | "completed" | "revision_requested" | "confirmed" | "cancelled" | "disputed";

export type QuestType = "standard" | "training" | "raid";

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
  /**
   * Quest budget in platform currency.
   * Normalized from backend Decimal (string) to JS number via normalizeQuest().
   * Safe for display/arithmetic for amounts ≤ $10,000,000 with ≤ 2 decimal places.
   */
  budget: number;
  currency: string;
  xp_reward: number;
  status: QuestStatus;
  applications: string[];
  assigned_to: string | null;
  quest_type: QuestType;
  raid_max_members?: number | null;
  raid_current_members: number;
  chain_id?: string | null;
  chain_step_order?: number | null;
  is_urgent: boolean;
  deadline: string | null;
  required_portfolio: boolean;
  delivery_note?: string | null;
  delivery_url?: string | null;
  delivery_submitted_at?: string | null;
  revision_reason?: string | null;
  revision_requested_at?: string | null;
  platform_fee_percent?: number | null;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface QuestCompletionData {
  delivery_note?: string;
  delivery_url?: string;
}

export interface QuestRevisionRequestData {
  revision_reason: string;
}

/**
 * Данные для создания квеста
 */
export interface QuestCreate {
  title: string;
  description: string;
  required_grade?: UserGrade;
  skills?: string[];
  /**
   * Budget in platform currency, sent as number.
   * Backend Decimal field accepts numeric JSON; precision safe for amounts ≤ $10,000,000.
   */
  budget: number;
  currency?: string;
  xp_reward?: number;
  status?: "draft" | "open";
  is_urgent?: boolean;
  deadline?: string;
  required_portfolio?: boolean;
}

export interface QuestUpdate {
  title?: string;
  description?: string;
  required_grade?: UserGrade;
  skills?: string[];
  budget?: number;
  xp_reward?: number;
}

export interface QuestStatusHistoryEntry {
  id: string;
  quest_id: string;
  from_status: QuestStatus | null;
  to_status: QuestStatus;
  changed_by: string | null;
  changed_by_username: string | null;
  note: string | null;
  created_at: string;
}

export interface QuestStatusHistoryResponse {
  history: QuestStatusHistoryEntry[];
}

/**
 * PvE Training quest creation payload (admin only)
 */
export interface TrainingQuestCreate {
  title: string;
  description: string;
  required_grade?: UserGrade;
  skills?: string[];
  xp_reward?: number;
}

/**
 * Response from completing a training quest
 */
export interface TrainingQuestCompleteResponse {
  message: string;
  quest: Quest;
  xp_reward: number;
  daily_xp_earned: number;
  daily_xp_cap: number;
  level_up: boolean;
  new_level: number;
  new_grade: string;
  stat_delta: { int: number; dex: number; cha: number; unspent: number };
  badges_earned: { id: string; name: string; description: string }[];
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
  is_banned: boolean;
  banned_reason: string | null;
  level: number;
  grade: UserGrade;
  xp: number;
  xp_to_next: number;
  stat_points: number;
  stats: UserStats;
  badges: UserBadge[];
  bio: string | null;
  avatar_url?: string | null;
  skills: string[];
  availability_status?: string | null;
  portfolio_links?: string[];
  portfolio_summary?: string | null;
  onboarding_completed?: boolean;
  onboarding_completed_at?: string | null;
  profile_completeness_percent?: number;
  character_class: string | null;
  created_at: string;
  updated_at: string;
}

/** Derived RPG reputation stats — 4 explainable scores computed from user signals. */
export interface ReputationStats {
  /** Delivery rate: completion_rate × 0.70 + trust_score × 0.30 */
  reliability: number; // 0-100
  /** Quality of work: avg rating × 0.70 + grade progression × 0.30 */
  craft: number; // 0-100
  /** Experience depth: quest history × 0.50 + reviews × 0.30 + level × 0.20 */
  influence: number; // 0-100
  /** Persistence: trust score × 0.60 + profile completeness × 0.40 */
  resolve: number; // 0-100
}

/** Derived faction alignment — computed from user activity signals, no DB changes. */
export interface FactionAlignment {
  /** "vanguard" | "keepers" | "artisans" | "none" */
  faction_id: string;
  faction_name: string;
  /** Normalized 0-100 contribution weight */
  contribution_score: number;
  /** "recruit" | "soldier" | "champion" | "legend" */
  rank: string;
  alignment_note: string;
}

export interface PublicUserProfile {
  id: string;
  username: string;
  role: "client" | "freelancer" | "admin";
  level: number;
  grade: UserGrade;
  xp: number;
  xp_to_next: number;
  stat_points: number;
  stats: UserStats;
  badges: UserBadge[];
  bio: string | null;
  avatar_url?: string | null;
  skills: string[];
  character_class: string | null;
  created_at: string;
  updated_at: string;
  avg_rating?: number | null;
  review_count?: number;
  trust_score?: number | null;
  trust_score_updated_at?: string | null;
  confirmed_quest_count?: number;
  completion_rate?: number | null;
  typical_budget_band?: string | null;
  availability_status?: string | null;
  response_time_hint?: string | null;
  portfolio_links?: string[];
  portfolio_summary?: string | null;
  onboarding_completed?: boolean;
  onboarding_completed_at?: string | null;
  profile_completeness_percent?: number;
  reputation_stats?: ReputationStats | null;
  faction_alignment?: FactionAlignment | null;
}

export type TalentMarketMode = "all" | "solo" | "guild" | "top-guilds";
export type ItemCategory = "cosmetic" | "collectible" | "equipable";

export interface GuildBadge {
  id: string;
  name: string;
  slug: string;
  role: "leader" | "officer" | "member";
  member_count: number;
  rating: number;
  season_position: number | null;
}

export interface TalentMarketMember {
  id: string;
  username: string;
  level: number;
  grade: UserGrade;
  xp: number;
  xp_to_next: number;
  stats: UserStats;
  badges_count: number;
  skills: string[];
  avg_rating: number | null;
  review_count: number;
  trust_score?: number | null;
  typical_budget_band?: string | null;
  availability_status?: string | null;
  response_time_hint?: string | null;
  character_class: string | null;
  market_kind: "solo" | "guild";
  rank_score: number;
  rank_signals: string[];
  guild: GuildBadge | null;
}

export interface GuildCard {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  emblem: string;
  member_count: number;
  member_limit: number;
  total_xp: number;
  avg_rating: number | null;
  confirmed_quests: number;
  treasury_balance: MoneyAmount;
  guild_tokens: number;
  rating: number;
  season_position: number | null;
  top_skills: string[];
  leader_username: string | null;
}

export interface GuildPublicMember {
  id: string;
  username: string;
  level: number;
  grade: UserGrade;
  xp: number;
  xp_to_next: number;
  stats: UserStats;
  skills: string[];
  avg_rating: number | null;
  review_count: number;
  character_class: string | null;
  role: "leader" | "officer" | "member";
  contribution: number;
  joined_at: string;
}

export interface GuildActivityEntry {
  id: string;
  event_type:
    | "guild_created"
    | "member_joined"
    | "member_left"
    | "quest_confirmed"
    | "guild_xp_awarded"
    | "guild_tier_promoted"
    | "guild_milestone_unlocked";
  summary: string;
  actor_user_id: string | null;
  actor_username: string | null;
  quest_id: string | null;
  treasury_delta: MoneyAmount;
  guild_tokens_delta: number;
  contribution_delta: number;
  created_at: string;
}

export interface GuildRewardCard {
  id: string;
  card_code: string;
  name: string;
  rarity: "common" | "rare" | "epic" | "legendary";
  family: string;
  description: string;
  accent: string;
  item_category: ItemCategory;
  awarded_to_user_id: string | null;
  awarded_to_username: string | null;
  source_quest_id: string;
  dropped_at: string;
}

export interface UserArtifact {
  id: string;
  card_code: string;
  name: string;
  rarity: "common" | "rare" | "epic" | "legendary";
  family: string;
  description: string;
  accent: string;
  item_category: ItemCategory;
  is_equipped: boolean;
  equip_slot: "profile_artifact" | null;
  equipped_at: string | null;
  equipped_effect_summary: string | null;
  source_quest_id: string;
  dropped_at: string;
}

export interface ArtifactCabinet {
  cosmetics: UserArtifact[];
  collectibles: UserArtifact[];
  equipable: UserArtifact[];
  total: number;
}

export interface ArtifactEquipResponse {
  artifact: UserArtifact;
  cabinet: ArtifactCabinet;
  message: string;
}

// Plan 11 — Solo player card drops
export interface SoloCardDrop {
  id: string;
  card_code: string;
  name: string;
  rarity: "common" | "rare" | "epic" | "legendary";
  family: string;
  description: string;
  accent: string;
  item_category: ItemCategory;
  quest_id: string;
  dropped_at: string;
}

export interface PlayerCardCollection {
  drops: SoloCardDrop[];
  total: number;
  drop_rate_note: string;
}

export interface GuildSeasonalSet {
  family: string;
  label: string;
  accent: string;
  season_code: string;
  target_cards: number;
  collected_cards: number;
  missing_cards: number;
  progress_percent: number;
  completed: boolean;
  rarity: "common" | "rare" | "epic" | "legendary" | null;
  reward_label: string;
  reward_treasury_bonus: MoneyAmount;
  reward_guild_tokens_bonus: number;
  reward_badge_name: string;
  reward_claimed: boolean;
  reward_claimed_at: string | null;
}

export interface GuildLeaderboardEntry {
  rank: number;
  member: GuildPublicMember;
  trophy_count: number;
  family_label: string | null;
}

export interface GuildMilestone {
  milestone_code: string;
  label: string;
  description: string;
  threshold_xp: number;
  unlocked: boolean;
  unlocked_at: string | null;
  reward_description: string;
}

export interface GuildContributionSummary {
  user_id: string;
  username: string;
  contribution: number;
  quests_completed: number;
  role: "leader" | "officer" | "member";
  rank: number;
}

export interface GuildProgressionSnapshot {
  season_code: string;
  seasonal_xp: number;
  current_tier: "bronze" | "silver" | "gold" | "platinum";
  next_tier: "bronze" | "silver" | "gold" | "platinum" | null;
  next_tier_xp: number | null;
  xp_to_next_tier: number;
  progress_percent: number;
  xp_bonus_percent: number;
  tier_benefits: string[];
  season_rank: number | null;
  completed_sets: number;
  total_sets: number;
  claimed_rewards: number;
  leaderboard: GuildLeaderboardEntry[];
  milestones: GuildMilestone[];
  top_contributors: GuildContributionSummary[];
}

export interface GuildPublicBadge {
  id: string;
  badge_code: string;
  name: string;
  slug: string;
  accent: string;
  season_code: string | null;
  family: string | null;
  awarded_at: string;
}

export interface GuildDetailResponse {
  guild: GuildCard;
  members: GuildPublicMember[];
  activity: GuildActivityEntry[];
  trophies: GuildRewardCard[];
  seasonal_sets: GuildSeasonalSet[];
  badges: GuildPublicBadge[];
  progression_snapshot: GuildProgressionSnapshot;
  generated_at: string;
}

export interface TalentMarketSummary {
  total_freelancers: number;
  solo_freelancers: number;
  guild_freelancers: number;
  total_guilds: number;
  top_solo_xp: number;
  top_guild_rating: number;
}

export interface TalentMarketResponse {
  mode: TalentMarketMode;
  summary: TalentMarketSummary;
  members: TalentMarketMember[];
  guilds: GuildCard[];
  limit: number;
  offset: number;
  has_more: boolean;
  generated_at: string;
}

export interface TrustScoreBreakdownRaw {
  average_rating_5: number;
  accepted_quests: number;
  confirmed_quests: number;
  on_time_quests: number;
  grade: UserGrade;
}

export interface TrustScoreBreakdown {
  avg_rating: number;
  completion_rate: number;
  on_time_rate: number;
  level_bonus: number;
  raw: TrustScoreBreakdownRaw;
}

export interface TrustScoreResponse {
  user_id: string;
  trust_score: number | null;
  breakdown: TrustScoreBreakdown;
  updated_at: string | null;
}

export interface MatchBreakdown {
  skill_overlap: number;
  grade_fit: number;
  trust_score: number;
  availability: number;
  budget_fit: number;
}

export interface RecommendedFreelancerCard {
  id: string;
  username: string;
  level: number;
  grade: UserGrade;
  xp: number;
  xp_to_next: number;
  stats: UserStats;
  skills: string[];
  avg_rating: number | null;
  review_count: number;
  trust_score?: number | null;
  typical_budget_band?: string | null;
  availability_status?: string | null;
  response_time_hint?: string | null;
  character_class: string | null;
  avatar_url?: string | null;
}

export interface FreelancerRecommendation {
  freelancer: RecommendedFreelancerCard;
  match_score: number;
  match_breakdown: MatchBreakdown;
  matched_skills: string[];
}

export interface FreelancerRecommendationListResponse {
  quest_id: string;
  recommendations: FreelancerRecommendation[];
  generated_at: string;
}

export interface QuestRecommendation {
  quest: Quest;
  match_score: number;
  match_breakdown: MatchBreakdown;
  matched_skills: string[];
}

export interface QuestRecommendationListResponse {
  user_id: string;
  recommendations: QuestRecommendation[];
  generated_at: string;
}

export interface GuildCreatePayload {
  name: string;
  description?: string;
  emblem?: string;
}

export interface GuildActionResponse {
  guild_id: string;
  status: string;
  message: string;
}

export interface WorldMetricSnapshot {
  total_users: number;
  freelancer_count: number;
  client_count: number;
  open_quests: number;
  in_progress_quests: number;
  revision_requested_quests: number;
  urgent_quests: number;
  confirmed_quests_week: number;
  unread_notifications: number;
  total_reviews: number;
  avg_rating: number | null;
  earned_badges: number;
}

export interface WorldSeason {
  id: string;
  title: string;
  stage: string;
  progress_percent: number;
  completed_quests_week: number;
  target_quests_week: number;
  days_left: number;
  chapter?: string;
  stage_description?: string;
  next_unlock?: string;
}

export interface WorldRegion {
  id: string;
  name: string;
  /** "active" | "contested" | "dormant" | "hostile" */
  status: string;
  progress_percent: number;
  dominant_faction_id: string;
  activity_label: string;
}

export interface WorldLoreBeat {
  id: string;
  text: string;
  faction_id?: string | null;
  /** "narrative" | "warning" | "milestone" */
  beat_type: string;
}

export interface WorldFaction {
  id: string;
  name: string;
  focus: string;
  score: number;
  trend: string;
}

export interface WorldCommunity {
  headline: string;
  momentum: string;
  target_label: string;
  current_value: number;
  target_value: number;
}

export interface WorldTrendPoint {
  label: string;
  value: number;
}

export interface WorldTrendMetric {
  id: string;
  label: string;
  current_value: number;
  previous_value: number;
  delta_value: number;
  delta_percent: number;
  direction: string;
  points: WorldTrendPoint[];
}

export interface WorldMetaSnapshot {
  season: WorldSeason;
  factions: WorldFaction[];
  leading_faction_id: string;
  community: WorldCommunity;
  metrics: WorldMetricSnapshot;
  trends: WorldTrendMetric[];
  regions?: WorldRegion[];
  lore_beats?: WorldLoreBeat[];
  generated_at: string;
}

/**
 * Ответ с токеном (после логина/регистрации)
 */
export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface AdminTotpSetupResponse {
  secret: string;
  otpauth_uri: string;
}

export interface AdminTotpEnableResponse {
  ok: boolean;
  message: string;
}

export async function refreshSession(): Promise<TokenResponse | null> {
  const now = Date.now();
  if (!refreshPromise && now - lastRefreshResolvedAt < REFRESH_RESULT_TTL_MS) {
    return lastRefreshResult;
  }

  if (!refreshPromise) {
    refreshPromise = (async () => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      try {
        const MAX_RETRIES = 2;
        for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
          try {
            const refreshResp = await fetch(`${API_BASE_URL}/auth/refresh`, {
              method: "POST",
              credentials: "include",
              headers: { "Content-Type": "application/json" },
              signal: controller.signal,
            });

            // Retry on 429/503 (transient)
            if ((refreshResp.status === 429 || refreshResp.status === 503) && attempt < MAX_RETRIES) {
              await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
              continue;
            }

            if (!refreshResp.ok) {
              lastRefreshResult = null;
              lastRefreshResolvedAt = Date.now();
              return null;
            }

            const refreshed = (await refreshResp.json()) as TokenResponse;
            setAccessToken(refreshed.access_token);
            lastRefreshResult = refreshed;
            lastRefreshResolvedAt = Date.now();
            return refreshed;
          } catch (error) {
            if (isAbortError(error)) {
              lastRefreshResult = null;
              lastRefreshResolvedAt = Date.now();
              return null;
            }
            // Retry on network errors
            if (attempt < MAX_RETRIES) {
              await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)));
              continue;
            }
            lastRefreshResult = null;
            lastRefreshResolvedAt = Date.now();
            return null;
          }
        }
        lastRefreshResult = null;
        lastRefreshResolvedAt = Date.now();
        return null;
      } finally {
        clearTimeout(timeoutId);
        refreshPromise = null;
      }
    })();
  }

  return refreshPromise;
}

/**
 * Данные для регистрации
 */
export interface RegisterData {
  username: string;
  email: string;
  password: string;
  role: "client" | "freelancer";
}

/**
 * Данные для входа
 */
export interface LoginData {
  username: string;
  password: string;
}

export interface LeadCapturePayload {
  email: string;
  company_name: string;
  contact_name: string;
  use_case: string;
  budget_band?: string;
  message?: string;
  source: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_term?: string;
  utm_content?: string;
  ref?: string;
  landing_path?: string;
}

export interface LeadCaptureResponse {
  id: string;
  email: string;
  company_name: string;
  contact_name: string;
  use_case: string;
  budget_band?: string | null;
  message?: string | null;
  source: string;
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  utm_term?: string | null;
  utm_content?: string | null;
  ref?: string | null;
  landing_path?: string | null;
  status: string;
  last_contacted_at?: string | null;
  next_contact_at?: string | null;
  nurture_stage: string;
  converted_user_id?: string | null;
  created_at: string;
}

/**
 * Ошибка API
 */
export interface ApiError {
  status: number;
  message: string;
  detail?: string;
}

function buildApiError(status: number, detail: string): ApiError {
  return {
    status,
    message: detail,
    detail,
  };
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function hasStoredUserHint(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  try {
    return Boolean(localStorage.getItem(STORAGE_KEY_USER));
  } catch {
    return false;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    "message" in error &&
    typeof (error as ApiError).status === "number"
  );
}

export function getApiErrorStatus(error: unknown): number | undefined {
  if (!isApiError(error)) {
    return undefined;
  }
  return typeof error.status === "number" ? error.status : undefined;
}

export function getApiErrorMessage(error: unknown, fallback = "API Error"): string {
  if (isApiError(error)) {
    if (typeof error.detail === "string" && error.detail.trim()) {
      return error.detail;
    }
    if (typeof error.message === "string" && error.message.trim()) {
      return error.message;
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallback;
}

function buildCollectionEndpoint(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

function buildRequestHeaders(
  headers: HeadersInit | undefined,
  accessToken: string | null,
  adminTotpToken?: string | null,
  body?: BodyInit | null,
): Headers {
  const nextHeaders = new Headers(headers);

  const isMultipart = typeof FormData !== "undefined" && body instanceof FormData;

  if (isMultipart) {
    nextHeaders.delete("Content-Type");
  } else if (!nextHeaders.has("Content-Type")) {
    nextHeaders.set("Content-Type", "application/json");
  }

  if (accessToken) {
    nextHeaders.set("Authorization", `Bearer ${accessToken}`);
  }

  if (adminTotpToken) {
    nextHeaders.set("X-TOTP-Token", adminTotpToken);
  }

  // E2E testing: attach bypass header so login rate-limits are skipped
  const e2eSecret = typeof process !== "undefined" ? process.env.NEXT_PUBLIC_E2E_BYPASS_SECRET : undefined;
  if (e2eSecret) {
    nextHeaders.set("X-E2E-Bypass", e2eSecret);
  }

  return nextHeaders;
}

function isAdminEndpoint(endpoint: string): boolean {
  return endpoint.startsWith("/admin");
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

type DecimalLike = number | string | null | undefined;

// Money fields listed below arrive from the backend as Decimal-aware wire values
// and must be normalized here before they reach shared UI types/components:
// - quest/template budget
// - wallet balances and transactions
// - withdrawal and admin wallet responses
// - admin revenue and proposed_price fields
type MoneyValueInput = MoneyWire | number | null | undefined;

type QuestRaw = Omit<Quest, "budget"> & {
  budget: MoneyWire;
};

type QuestApplicationRaw = Omit<QuestApplication, "proposed_price"> & {
  proposed_price?: MoneyWire | null;
};

type QuestTemplateRaw = Omit<QuestTemplate, "budget"> & {
  budget: MoneyWire;
};

type QuestListResponseRaw = Omit<QuestListResponse, "quests"> & {
  quests: QuestRaw[];
};

type TemplateListResponseRaw = Omit<TemplateListResponse, "templates"> & {
  templates: QuestTemplateRaw[];
};

interface QuestWithMessageResponseRaw {
  message: string;
  quest: QuestRaw;
}

interface QuestApplicationWithMessageResponseRaw {
  message: string;
  application: QuestApplicationRaw;
}

interface QuestCompleteResponseRaw {
  message: string;
  quest: QuestRaw;
  xp_earned: number;
}

interface QuestConfirmResponseRaw {
  message: string;
  quest: QuestRaw;
  xp_reward: number;
  money_reward: MoneyWire;
}

interface WalletBalanceItemRaw {
  currency: string;
  balance: MoneyWire;
}

interface WalletBalanceResponseRaw {
  user_id: string;
  balances: WalletBalanceItemRaw[];
  total_earned: MoneyWire;
}

interface WalletTransactionRaw {
  id: string;
  user_id: string;
  quest_id: string | null;
  amount: MoneyWire;
  currency: string;
  type: string;
  status?: "pending" | "completed" | "rejected";
  created_at: string;
}

interface WalletTransactionsResponseRaw {
  user_id: string;
  transactions: WalletTransactionRaw[];
  limit: number;
  offset: number;
}

interface WithdrawalResponseRaw {
  transaction_id: string;
  amount: MoneyWire;
  currency: string;
  status: string;
  new_balance: MoneyWire;
}

interface AdminTransactionRaw {
  id: string;
  user_id: string;
  type: string;
  amount: MoneyWire;
  currency: string;
  status: "pending" | "completed" | "rejected";
  quest_id: string | null;
  created_at: string;
}

interface AdminTransactionsResponseRaw {
  transactions: AdminTransactionRaw[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

type AdminLogEntryRaw = Omit<AdminLogsResponse["logs"][number], "old_value" | "new_value"> & {
  old_value: unknown;
  new_value: unknown;
};

type AdminLogsResponseRaw = Omit<AdminLogsResponse, "logs"> & {
  logs: AdminLogEntryRaw[];
};

interface WithdrawalApproveResultRaw {
  transaction_id: string;
  status: "completed";
  user_id: string;
  amount: MoneyWire;
  currency: string;
}

interface WithdrawalRejectResultRaw {
  transaction_id: string;
  status: "rejected";
  user_id: string;
  amount: MoneyWire;
  currency: string;
  reason: string;
  new_balance: MoneyWire;
}

interface AdminPlatformStatsRaw {
  total_users: number;
  users_by_role: Record<string, number>;
  banned_users: number;
  total_quests: number;
  quests_by_status: Record<string, number>;
  total_transactions: number;
  pending_withdrawals: number;
  total_revenue: MoneyWire;
  users_today: number;
  quests_today: number;
}

interface AdminAdjustWalletResultRaw {
  user_id: string;
  username: string;
  old_balance: MoneyWire;
  new_balance: MoneyWire;
  amount: MoneyWire;
  currency: string;
  reason: string;
}

interface AdminUserWalletRaw {
  id: string;
  currency: string;
  balance: MoneyWire;
  updated_at: string;
}

type AdminUserDetailRaw = Omit<AdminUserDetail, "wallets"> & {
  wallets: AdminUserWalletRaw[];
};

interface AdminQuestApplicationRaw {
  id: string;
  freelancer_id: string;
  freelancer_username: string;
  freelancer_grade: string;
  cover_letter: string | null;
  proposed_price: MoneyWire | null;
  created_at: string;
}

type AdminQuestDetailRaw = Omit<AdminQuestDetail, "budget" | "applications"> & {
  budget: MoneyWire;
  applications: AdminQuestApplicationRaw[];
};

type GuildCardRaw = Omit<GuildCard, "treasury_balance"> & {
  treasury_balance: MoneyWire;
};

type GuildActivityEntryRaw = Omit<GuildActivityEntry, "treasury_delta"> & {
  treasury_delta: MoneyWire;
};

type GuildSeasonalSetRaw = Omit<GuildSeasonalSet, "reward_treasury_bonus"> & {
  reward_treasury_bonus: MoneyWire;
};

type GuildDetailResponseRaw = Omit<GuildDetailResponse, "guild" | "activity" | "seasonal_sets"> & {
  guild: GuildCardRaw;
  activity: GuildActivityEntryRaw[];
  seasonal_sets: GuildSeasonalSetRaw[];
};

type TalentMarketResponseRaw = Omit<TalentMarketResponse, "guilds"> & {
  guilds: GuildCardRaw[];
};

type QuestRecommendationRaw = Omit<QuestRecommendation, "quest"> & {
  quest: QuestRaw;
};

type QuestRecommendationListResponseRaw = Omit<QuestRecommendationListResponse, "recommendations"> & {
  recommendations: QuestRecommendationRaw[];
};

/**
 * Convert a MoneyWire string to a JS number for display/arithmetic.
 * Safe for amounts < 9,007,199,254,740,991 (Number.MAX_SAFE_INTEGER).
 * Platform guarantee: all money values ≤ $10,000,000 with at most 2 decimal places.
 * For amounts outside this range, use decimal.js.
 */
function toNumber(value: MoneyValueInput): number {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : 0;
  }

  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  return 0;
}

function toNullableNumber(value: DecimalLike): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  return toNumber(value);
}

function parseAdminLogValue(value: unknown): AdminLogValue | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value !== "string") {
    return value as AdminLogValue;
  }

  try {
    return JSON.parse(value) as AdminLogValue;
  } catch {
    return value;
  }
}

/**
 * Converts wire-format Quest (budget as MoneyWire string) to normalized Quest (budget as number).
 * Safe: all platform budgets are ≤ $10,000,000 with ≤ 2 decimal places.
 */
function normalizeQuest(quest: QuestRaw): Quest {
  return {
    ...quest,
    budget: toNumber(quest.budget),
  };
}

function normalizeQuestTemplate(template: QuestTemplateRaw): QuestTemplate {
  return {
    ...template,
    budget: toNumber(template.budget),
  };
}

function normalizeQuestListResponse(response: QuestListResponseRaw): QuestListResponse {
  return {
    ...response,
    quests: response.quests.map(normalizeQuest),
  };
}

function normalizeQuestWithMessageResponse(response: QuestWithMessageResponseRaw): { message: string; quest: Quest } {
  return {
    ...response,
    quest: normalizeQuest(response.quest),
  };
}

function normalizeQuestApplication(application: QuestApplicationRaw): QuestApplication {
  const proposedPrice = toNullableNumber(application.proposed_price);

  return {
    ...application,
    proposed_price: proposedPrice === null ? undefined : proposedPrice,
  };
}

function normalizeQuestApplicationWithMessageResponse(
  response: QuestApplicationWithMessageResponseRaw,
): { message: string; application: QuestApplication } {
  return {
    ...response,
    application: normalizeQuestApplication(response.application),
  };
}

function normalizeQuestCompleteResponse(
  response: QuestCompleteResponseRaw,
): { message: string; quest: Quest; xp_earned: number } {
  return {
    ...response,
    quest: normalizeQuest(response.quest),
  };
}

function normalizeTemplateListResponse(response: TemplateListResponseRaw): TemplateListResponse {
  return {
    ...response,
    templates: response.templates.map(normalizeQuestTemplate),
  };
}

function normalizeQuestConfirmResponse(
  response: QuestConfirmResponseRaw,
): { message: string; quest: Quest; xp_reward: number; money_reward: number } {
  return {
    ...response,
    quest: normalizeQuest(response.quest),
    money_reward: toNumber(response.money_reward),
  };
}

function normalizeWalletBalanceResponse(response: WalletBalanceResponseRaw): WalletBalanceResponse {
  return {
    ...response,
    balances: response.balances.map((balance) => ({
      ...balance,
      balance: toNumber(balance.balance),
    })),
    total_earned: toNumber(response.total_earned),
  };
}

function normalizeWalletTransactionsResponse(response: WalletTransactionsResponseRaw): WalletTransactionsResponse {
  return {
    ...response,
    transactions: response.transactions.map((transaction) => ({
      ...transaction,
      amount: toNumber(transaction.amount),
    })),
  };
}

function normalizeWithdrawalResponse(response: WithdrawalResponseRaw): WithdrawalResponse {
  return {
    ...response,
    amount: toNumber(response.amount),
    new_balance: toNumber(response.new_balance),
  };
}

function normalizeAdminTransactionsResponse(response: AdminTransactionsResponseRaw): AdminTransactionsResponse {
  return {
    ...response,
    transactions: response.transactions.map((transaction) => ({
      ...transaction,
      amount: toNumber(transaction.amount),
    })),
  };
}

function normalizeAdminLogsResponse(response: AdminLogsResponseRaw): AdminLogsResponse {
  return {
    ...response,
    logs: response.logs.map((log) => ({
      ...log,
      old_value: parseAdminLogValue(log.old_value),
      new_value: parseAdminLogValue(log.new_value),
    })),
  };
}

function normalizeWithdrawalApproveResult(response: WithdrawalApproveResultRaw): WithdrawalApproveResult {
  return {
    ...response,
    amount: toNumber(response.amount),
  };
}

function normalizeWithdrawalRejectResult(response: WithdrawalRejectResultRaw): WithdrawalRejectResult {
  return {
    ...response,
    amount: toNumber(response.amount),
    new_balance: toNumber(response.new_balance),
  };
}

function normalizeAdminPlatformStats(response: AdminPlatformStatsRaw): AdminPlatformStats {
  return {
    ...response,
    total_revenue: toNumber(response.total_revenue),
  };
}

function normalizeAdminAdjustWalletResult(response: AdminAdjustWalletResultRaw): AdminAdjustWalletResult {
  return {
    ...response,
    old_balance: toNumber(response.old_balance),
    new_balance: toNumber(response.new_balance),
    amount: toNumber(response.amount),
  };
}

function normalizeAdminUserDetail(response: AdminUserDetailRaw): AdminUserDetail {
  return {
    ...response,
    wallets: response.wallets.map((wallet: AdminUserWalletRaw): AdminUserWallet => ({
      ...wallet,
      balance: toNumber(wallet.balance),
    })),
  };
}

function normalizeAdminQuestDetail(response: AdminQuestDetailRaw): AdminQuestDetail {
  return {
    ...response,
    budget: toNumber(response.budget),
    applications: response.applications.map((application: AdminQuestApplicationRaw): AdminQuestApplicationDetail => ({
      ...application,
      proposed_price: toNullableNumber(application.proposed_price),
    })),
  };
}

function normalizeGuildCard(guild: GuildCardRaw): GuildCard {
  return {
    ...guild,
    treasury_balance: toNumber(guild.treasury_balance),
  };
}

function normalizeGuildActivityEntry(entry: GuildActivityEntryRaw): GuildActivityEntry {
  return {
    ...entry,
    treasury_delta: toNumber(entry.treasury_delta),
  };
}

function normalizeGuildSeasonalSet(seasonalSet: GuildSeasonalSetRaw): GuildSeasonalSet {
  return {
    ...seasonalSet,
    reward_treasury_bonus: toNumber(seasonalSet.reward_treasury_bonus),
  };
}

function normalizeTalentMarketResponse(response: TalentMarketResponseRaw): TalentMarketResponse {
  return {
    ...response,
    guilds: response.guilds.map(normalizeGuildCard),
  };
}

function normalizeQuestRecommendationResponse(
  response: QuestRecommendationListResponseRaw,
): QuestRecommendationListResponse {
  return {
    ...response,
    recommendations: response.recommendations.map((item) => ({
      ...item,
      quest: normalizeQuest(item.quest),
    })),
  };
}

function normalizeGuildDetailResponse(response: GuildDetailResponseRaw): GuildDetailResponse {
  return {
    ...response,
    guild: normalizeGuildCard(response.guild),
    activity: response.activity.map(normalizeGuildActivityEntry),
    seasonal_sets: response.seasonal_sets.map(normalizeGuildSeasonalSet),
  };
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
  return fetchApiWithRetry<T>(endpoint, options, _requireAuth, false);
}

async function fetchApiVoid(
  endpoint: string,
  options?: RequestInit,
  _requireAuth: boolean = false,
): Promise<void> {
  await fetchApiWithRetry<void>(endpoint, options, _requireAuth, true);
}

async function fetchApiBlob(
  endpoint: string,
  options?: RequestInit,
  _requireAuth: boolean = false,
): Promise<{ blob: Blob; filename: string | null }> {
  return fetchBlobWithRetry(endpoint, options, _requireAuth);
}

async function fetchApiWithRetry<T>(
  endpoint: string,
  options: RequestInit | undefined,
  _requireAuth: boolean,
  expectNoContent: boolean,
): Promise<T> {
  const MAX_RETRIES = 2;
  let lastError: unknown;

  // P0 FE-02 FIX: Only retry idempotent methods (GET, HEAD, OPTIONS)
  // POST/PATCH/DELETE must NOT be retried to avoid double-submit (withdrawals, payments, etc.)
  const method = (options?.method ?? "GET").toUpperCase();
  const isIdempotent = ["GET", "HEAD", "OPTIONS"].includes(method);

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await _fetchApiOnce<T>(endpoint, options, _requireAuth, expectNoContent);
    } catch (err) {
      lastError = err;
      if (!isIdempotent) throw err; // never retry non-idempotent
      const isRetryable =
        (err instanceof TypeError) || // network error
        (err && typeof err === "object" && "status" in err &&
          ((err as { status: number }).status === 429 || (err as { status: number }).status === 503));
      if (!isRetryable || attempt === MAX_RETRIES) throw err;
      const delay = Math.min(1000 * 2 ** attempt, 4000);
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  throw lastError;
}

async function fetchBlobWithRetry(
  endpoint: string,
  options: RequestInit | undefined,
  _requireAuth: boolean,
): Promise<{ blob: Blob; filename: string | null }> {
  const MAX_RETRIES = 2;
  let lastError: unknown;
  const method = (options?.method ?? "GET").toUpperCase();
  const isIdempotent = ["GET", "HEAD", "OPTIONS"].includes(method);

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await _fetchBlobOnce(endpoint, options, _requireAuth);
    } catch (err) {
      lastError = err;
      if (!isIdempotent) throw err;
      const isRetryable =
        (err instanceof TypeError) ||
        (err && typeof err === "object" && "status" in err &&
          ((err as { status: number }).status === 429 || (err as { status: number }).status === 503));
      if (!isRetryable || attempt === MAX_RETRIES) throw err;
      const delay = Math.min(1000 * 2 ** attempt, 4000);
      await new Promise((r) => setTimeout(r, delay));
    }
  }

  throw lastError;
}

export async function submitLeadCapture(payload: LeadCapturePayload): Promise<LeadCaptureResponse> {
  return fetchApi<LeadCaptureResponse>(
    "/leads/",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    false,
  );
}

async function _fetchApiOnce<T>(
  endpoint: string,
  options?: RequestInit,
  _requireAuth: boolean = false,
  expectNoContent: boolean = false,
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const token = getAccessToken();
  const adminEndpoint = isAdminEndpoint(endpoint);
  const config: RequestInit = {
    ...options,
    headers: buildRequestHeaders(
      options?.headers,
      token,
      adminEndpoint ? getAdminTotpToken() : null,
      options?.body,
    ),
  };

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
    const shouldTryRefresh = !isAuthEndpoint && (Boolean(token) || _requireAuth || hasStoredUserHint());
    if (response.status === 401 && shouldTryRefresh) {
      try {
        const refreshed = await refreshSession();
        const newToken = refreshed?.access_token;

        if (newToken) {
          const retryHeaders = buildRequestHeaders(
            config.headers,
            newToken,
            adminEndpoint ? getAdminTotpToken() : null,
          );
          const retryResp = await fetch(url, { ...config, headers: retryHeaders, credentials: "include" });
          if (!retryResp.ok) {
            let err = retryResp.statusText;
            try {
              const errorData = await retryResp.json();
              err = errorData.detail || errorData.message || err;
            } catch {}
            throw buildApiError(retryResp.status, err || "API Error");
          }
          if (expectNoContent) {
            if (retryResp.status !== 204) {
              throw buildApiError(500, "Expected 204 No Content response");
            }
            return undefined as T;
          }
          if (retryResp.status === 204) {
            throw buildApiError(500, "Expected JSON response but received 204 No Content");
          }
          return await retryResp.json();
        }
      } catch (_err) {
        if (_err && typeof _err === "object" && "status" in _err) throw _err;
        // fallthrough to clean-up below
      }

      // If refresh failed, clear in-memory token and stored user and surface 401.
      // Only trigger a forced logout+redirect if the user was previously authenticated
      // (had a token). Anonymous users hitting a protected endpoint just get an error.
      const hadToken = !!getAccessToken();
      setAccessToken(null);
      clearAdminTotpToken();
      if (typeof window !== "undefined") {
        localStorage.removeItem("questionwork_user");
      }
      if (hadToken) {
        triggerLogout();
      }

      throw buildApiError(401, "Сессия истекла. Пожалуйста, войдите снова.");
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

      if (adminEndpoint && response.status === 403 && isAdminTotpErrorMessage(errorDetail)) {
        clearAdminTotpToken(errorDetail || "Admin TOTP verification failed.");
      }

      throw buildApiError(response.status, errorDetail || "API Error");
    }

    if (expectNoContent) {
      if (response.status !== 204) {
        throw buildApiError(500, "Expected 204 No Content response");
      }
      return undefined as T;
    }

    if (response.status === 204) {
      throw buildApiError(500, "Expected JSON response but received 204 No Content");
    }

    return await response.json();
  } catch (error) {
    if (isAbortError(error)) {
      throw buildApiError(0, "Сервер не ответил вовремя. Проверьте, что backend запущен на 127.0.0.1:8001, и повторите попытку.");
    }
    throw error;
  }
}

function getFilenameFromDisposition(value: string | null): string | null {
  if (!value) {
    return null;
  }

  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const quotedMatch = value.match(/filename="?([^";]+)"?/i);
  return quotedMatch?.[1] ?? null;
}

async function _fetchBlobOnce(
  endpoint: string,
  options?: RequestInit,
  _requireAuth: boolean = false,
): Promise<{ blob: Blob; filename: string | null }> {
  const url = `${API_BASE_URL}${endpoint}`;
  const token = getAccessToken();
  const adminEndpoint = isAdminEndpoint(endpoint);
  const config: RequestInit = {
    ...options,
    headers: buildRequestHeaders(
      options?.headers,
      token,
      adminEndpoint ? getAdminTotpToken() : null,
      options?.body,
    ),
  };

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);
    const response = await fetch(url, { ...config, signal: controller.signal, credentials: "include" });
    clearTimeout(timeoutId);

    const isAuthEndpoint = url.includes("/auth/login") || url.includes("/auth/register") || url.includes("/auth/refresh");
    const shouldTryRefresh = !isAuthEndpoint && (Boolean(token) || _requireAuth || hasStoredUserHint());

    if (response.status === 401 && shouldTryRefresh) {
      try {
        const refreshed = await refreshSession();
        const newToken = refreshed?.access_token;

        if (newToken) {
          const retryHeaders = buildRequestHeaders(
            config.headers,
            newToken,
            adminEndpoint ? getAdminTotpToken() : null,
          );
          const retryResp = await fetch(url, { ...config, headers: retryHeaders, credentials: "include" });
          if (!retryResp.ok) {
            let err = retryResp.statusText;
            try {
              const errorData = await retryResp.json();
              err = errorData.detail || errorData.message || err;
            } catch {}
            throw buildApiError(retryResp.status, err || "API Error");
          }
          return {
            blob: await retryResp.blob(),
            filename: getFilenameFromDisposition(retryResp.headers.get("Content-Disposition")),
          };
        }
      } catch (_err) {
        if (_err && typeof _err === "object" && "status" in _err) throw _err;
      }

      const hadToken = !!getAccessToken();
      setAccessToken(null);
      clearAdminTotpToken();
      if (typeof window !== "undefined") {
        localStorage.removeItem("questionwork_user");
      }
      if (hadToken) {
        triggerLogout();
      }

      throw buildApiError(401, "Сессия истекла. Пожалуйста, войдите снова.");
    }

    if (!response.ok) {
      let errorDetail = response.statusText;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorData.message || response.statusText;
      } catch {}

      if (adminEndpoint && response.status === 403 && isAdminTotpErrorMessage(errorDetail)) {
        clearAdminTotpToken(errorDetail || "Admin TOTP verification failed.");
      }

      throw buildApiError(response.status, errorDetail || "API Error");
    }

    return {
      blob: await response.blob(),
      filename: getFilenameFromDisposition(response.headers.get("Content-Disposition")),
    };
  } catch (error) {
    if (isAbortError(error)) {
      throw buildApiError(0, "Сервер не ответил вовремя. Проверьте, что backend запущен на 127.0.0.1:8001, и повторите попытку.");
    }
    throw error;
  }
}

// ============================================
// User API функции
// ============================================

export async function getUserProfile(userId: string): Promise<PublicUserProfile> {
  return fetchApi<PublicUserProfile>(`/users/${userId}`);
}

export async function getUserArtifacts(): Promise<ArtifactCabinet> {
  return fetchApi<ArtifactCabinet>("/users/me/artifacts", {}, true);
}

export async function equipArtifact(artifactId: string): Promise<ArtifactEquipResponse> {
  return fetchApi<ArtifactEquipResponse>(`/users/me/artifacts/${artifactId}/equip`, { method: "POST" }, true);
}

export async function unequipArtifact(artifactId: string): Promise<ArtifactEquipResponse> {
  return fetchApi<ArtifactEquipResponse>(`/users/me/artifacts/${artifactId}/unequip`, { method: "POST" }, true);
}

export async function getPlayerCardDrops(): Promise<PlayerCardCollection> {
  return fetchApi<PlayerCardCollection>("/users/me/player-cards", {}, true);
}

export async function getUserTrustScore(userId: string): Promise<TrustScoreResponse> {
  return fetchApi<TrustScoreResponse>(`/users/${userId}/trust-score`);
}

export async function getRecommendedFreelancers(
  questId: string,
  limit: number = 10,
): Promise<FreelancerRecommendationListResponse> {
  return fetchApi<FreelancerRecommendationListResponse>(`/quests/${questId}/recommended-freelancers?limit=${limit}`);
}

export async function getRecommendedQuests(
  limit: number = 10,
): Promise<QuestRecommendationListResponse> {
  const response = await fetchApi<QuestRecommendationListResponseRaw>(`/users/me/recommended-quests?limit=${limit}`, undefined, true);
  return normalizeQuestRecommendationResponse(response);
}

/**
 * Fetch the authenticated user's own full profile.
 * P1-14 FIX: use this (not getUserProfile) in refreshUser so that is_banned
 * and other private fields are kept up-to-date in the auth context.
 */
export async function getSelfProfile(): Promise<UserProfile> {
  return fetchApi<UserProfile>("/users/me");
}

export interface ProfileUpdatePayload {
  bio?: string;
  skills?: string[];
  availability_status?: string;
  portfolio_summary?: string;
  portfolio_links?: string[];
}

export interface AvatarUploadResponse {
  avatar_url: string;
}

export async function updateMyProfile(payload: ProfileUpdatePayload): Promise<PublicUserProfile> {
  return fetchApi<PublicUserProfile>("/users/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  }, true);
}

export async function uploadMyAvatar(file: File): Promise<AvatarUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return fetchApi<AvatarUploadResponse>(
    "/users/me/avatar",
    {
      method: "POST",
      body: formData,
    },
    true,
  );
}

export async function completeOnboarding(): Promise<{ ok: boolean; badges_earned: UserBadgeEarned[] }> {
  return fetchApi<{ ok: boolean; badges_earned: UserBadgeEarned[] }>("/users/onboarding/complete", {
    method: "POST",
  }, true);
}

export async function getUserStats(userId: string): Promise<UserStats> {
  return fetchApi<UserStats>(`/users/${userId}/stats`);
}

export interface UsersListResponse {
  users: PublicUserProfile[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export async function getAllUsers(
  skip: number = 0,
  limit: number = 10,
  grade?: UserGrade,
  sortBy: "created_at" | "xp" | "level" | "username" = "created_at",
  sortOrder: "asc" | "desc" = "desc",
): Promise<UsersListResponse> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  if (grade) {
    params.append("grade", grade);
  }

  return fetchApi<UsersListResponse>(buildCollectionEndpoint("/users/", params));
}

export async function getWorldMeta(): Promise<WorldMetaSnapshot> {
  return fetchApi<WorldMetaSnapshot>("/meta/world");
}

export async function getTalentMarket(params?: {
  skip?: number;
  limit?: number;
  mode?: TalentMarketMode;
  grade?: UserGrade;
  search?: string;
  sortBy?: "xp" | "level" | "username" | "rating" | "trust";
}): Promise<TalentMarketResponse> {
  const query = new URLSearchParams({
    skip: String(params?.skip ?? 0),
    limit: String(params?.limit ?? 20),
    mode: params?.mode ?? "all",
    sort_by: params?.sortBy ?? "xp",
  });

  if (params?.grade) {
    query.append("grade", params.grade);
  }
  if (params?.search?.trim()) {
    query.append("search", params.search.trim());
  }

  const response = await fetchApi<TalentMarketResponseRaw>(buildCollectionEndpoint("/marketplace/talent", query));
  return normalizeTalentMarketResponse(response);
}

export async function getGuildProfile(guildSlug: string): Promise<GuildDetailResponse> {
  const response = await fetchApi<GuildDetailResponseRaw>(`/marketplace/guilds/${guildSlug}`);
  return normalizeGuildDetailResponse(response);
}

export async function createGuild(payload: GuildCreatePayload): Promise<GuildActionResponse> {
  return fetchApi<GuildActionResponse>(
    "/marketplace/guilds",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    true,
  );
}

export async function joinGuild(guildId: string): Promise<GuildActionResponse> {
  return fetchApi<GuildActionResponse>(`/marketplace/guilds/${guildId}/join`, { method: "POST" }, true);
}

export async function leaveGuild(guildId: string): Promise<GuildActionResponse> {
  return fetchApi<GuildActionResponse>(`/marketplace/guilds/${guildId}/leave`, { method: "POST" }, true);
}

// ── Shortlists ──────────────────────────────────────────────────

export interface ShortlistEntry {
  id: string;
  client_id: string;
  freelancer_id: string;
  created_at: string;
}

export interface ShortlistResponse {
  entries: ShortlistEntry[];
  total: number;
}

export async function addToShortlist(freelancerId: string): Promise<ShortlistEntry> {
  return fetchApi<ShortlistEntry>("/shortlists/", {
    method: "POST",
    body: JSON.stringify({ freelancer_id: freelancerId }),
  }, true);
}

export async function removeFromShortlist(freelancerId: string): Promise<void> {
  await fetchApi<void>(`/shortlists/${freelancerId}`, { method: "DELETE" }, true);
}

export async function getShortlist(limit = 50, offset = 0): Promise<ShortlistResponse> {
  return fetchApi<ShortlistResponse>(`/shortlists/?limit=${limit}&offset=${offset}`, undefined, true);
}

export async function getShortlistIds(): Promise<string[]> {
  return fetchApi<string[]>("/shortlists/ids", undefined, true);
}

export async function getShortlistCount(): Promise<{ count: number }> {
  return fetchApi<{ count: number }>("/shortlists/count", undefined, true);
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
    clearAdminTotpToken();
    if (typeof window !== "undefined") {
      localStorage.removeItem("questionwork_user");
    }
    return result;
  } catch (err) {
    // ensure client-side cleanup on any error
    setAccessToken(null);
    clearAdminTotpToken();
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
    userId?: string;
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
    if (filters.userId) params.append("user_id", filters.userId);
  }

  const response = await fetchApi<QuestListResponseRaw>(buildCollectionEndpoint("/quests/", params));
  return normalizeQuestListResponse(response);
}

/**
 * Получить детали квеста по ID
 */
export async function getQuest(questId: string): Promise<Quest> {
  const response = await fetchApi<QuestRaw>(`/quests/${questId}`);
  return normalizeQuest(response);
}

/**
 * Создать новый квест
 */
export async function createQuest(questData: QuestCreate): Promise<Quest> {
  const response = await fetchApi<QuestRaw>(
    "/quests/",
    {
      method: "POST",
      body: JSON.stringify(questData),
    },
    true,
  );
  return normalizeQuest(response);
}

export async function updateQuest(questId: string, questData: QuestUpdate): Promise<Quest> {
  const response = await fetchApi<QuestRaw>(
    `/quests/${questId}`,
    {
      method: "PATCH",
      body: JSON.stringify(questData),
    },
    true,
  );
  return normalizeQuest(response);
}

export async function publishQuest(questId: string): Promise<{ message: string; quest: Quest }> {
  const response = await fetchApi<QuestWithMessageResponseRaw>(
    `/quests/${questId}/publish`,
    {
      method: "POST",
    },
    true,
  );
  return normalizeQuestWithMessageResponse(response);
}

export async function getQuestHistory(questId: string): Promise<QuestStatusHistoryResponse> {
  return fetchApi<QuestStatusHistoryResponse>(`/quests/${questId}/history`);
}

/**
 * Откликнуться на квест
 */
export async function applyToQuest(
  questId: string,
  applicationData: QuestApplicationCreate,
): Promise<{ message: string; application: QuestApplication }> {
  const response = await fetchApi<QuestApplicationWithMessageResponseRaw>(
    `/quests/${questId}/apply`,
    {
      method: "POST",
      body: JSON.stringify(applicationData),
    },
    true,
  );
  return normalizeQuestApplicationWithMessageResponse(response);
}

/**
 * Назначить исполнителя на квест
 */
export async function assignQuest(
  questId: string,
  freelancerId: string,
): Promise<{ message: string; quest: Quest }> {
  const response = await fetchApi<QuestWithMessageResponseRaw>(
    `/quests/${questId}/assign`,
    {
      method: "POST",
      body: JSON.stringify({ freelancer_id: freelancerId }),
    },
    true,
  );
  return normalizeQuestWithMessageResponse(response);
}

export async function inviteFreelancerToQuest(
  questId: string,
  freelancerId: string,
): Promise<{ quest_id: string; freelancer_id: string; already_sent: boolean; message: string }> {
  return fetchApi(
    `/quests/${questId}/invite`,
    { method: "POST", body: JSON.stringify({ freelancer_id: freelancerId }) },
    true,
  );
}

/**
 * Начать квест (назначенный исполнитель)
 */
export async function startQuest(
  questId: string,
): Promise<{ message: string; quest: Quest }> {
  const response = await fetchApi<QuestWithMessageResponseRaw>(
    `/quests/${questId}/start`,
    {
      method: "POST",
    },
    true,
  );
  return normalizeQuestWithMessageResponse(response);
}

/**
 * Завершить квест (исполнитель)
 */
export async function completeQuest(
  questId: string,
  completionData?: QuestCompletionData,
): Promise<{ message: string; quest: Quest; xp_earned: number }> {
  const response = await fetchApi<QuestCompleteResponseRaw>(
    `/quests/${questId}/complete`,
    {
      method: "POST",
      body: completionData ? JSON.stringify(completionData) : undefined,
    },
    true,
  );
  return normalizeQuestCompleteResponse(response);
}

/**
 * Запросить доработки по завершённому квесту (клиент)
 */
export async function requestQuestRevision(
  questId: string,
  revisionData: QuestRevisionRequestData,
): Promise<{ message: string; quest: Quest }> {
  const response = await fetchApi<QuestWithMessageResponseRaw>(
    `/quests/${questId}/request-revision`,
    {
      method: "POST",
      body: JSON.stringify(revisionData),
    },
    true,
  );
  return normalizeQuestWithMessageResponse(response);
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
  const response = await fetchApi<QuestConfirmResponseRaw>(
    `/quests/${questId}/confirm`,
    {
      method: "POST",
    },
    true,
  );
  return normalizeQuestConfirmResponse(response);
}

/**
 * Отменить квест (клиент)
 */
export async function cancelQuest(
  questId: string,
): Promise<{ message: string; quest: Quest }> {
  const response = await fetchApi<QuestWithMessageResponseRaw>(
    `/quests/${questId}/cancel`,
    {
      method: "POST",
    },
    true,
  );
  return normalizeQuestWithMessageResponse(response);
}

/**
 * Получить отклики на квест
 */
export async function getQuestApplications(
  questId: string,
): Promise<{ applications: QuestApplication[]; total: number }> {
  const response = await fetchApi<{ applications: QuestApplicationRaw[]; total: number }>(
    `/quests/${questId}/applications`,
    {},
    true,
  );
  return {
    ...response,
    applications: response.applications.map(normalizeQuestApplication),
  };
}

// ============================================
// PvE Training Quest API
// ============================================

export async function getTrainingQuests(
  page = 1,
  pageSize = 10,
  grade?: string,
  skill?: string,
): Promise<QuestListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (grade) params.set("grade", grade);
  if (skill) params.set("skill", skill);
  const response = await fetchApi<QuestListResponseRaw>(
    `/quests/training/list?${params}`,
  );
  return normalizeQuestListResponse(response);
}

export async function createTrainingQuest(
  data: TrainingQuestCreate,
): Promise<Quest> {
  const response = await fetchApi<QuestRaw>(
    "/quests/training/create",
    { method: "POST", body: JSON.stringify(data) },
    true,
  );
  return normalizeQuest(response);
}

export async function acceptTrainingQuest(
  questId: string,
): Promise<Quest> {
  const response = await fetchApi<QuestRaw>(
    `/quests/training/${questId}/accept`,
    { method: "POST" },
    true,
  );
  return normalizeQuest(response);
}

export async function completeTrainingQuest(
  questId: string,
): Promise<TrainingQuestCompleteResponse> {
  const response = await fetchApi<TrainingQuestCompleteResponseRaw>(
    `/quests/training/${questId}/complete`,
    { method: "POST" },
    true,
  );
  return {
    ...response,
    quest: normalizeQuest(response.quest),
  };
}

type TrainingQuestCompleteResponseRaw = Omit<TrainingQuestCompleteResponse, "quest"> & { quest: QuestRaw };


/**
 * Raid role slots
 */
export const RAID_ROLE_SLOTS = ["leader", "developer", "designer", "tester", "analyst", "devops", "support", "any"] as const;
export type RaidRoleSlot = typeof RAID_ROLE_SLOTS[number];

/**
 * Raid participant entry
 */
export interface RaidParticipant {
  id: string;
  quest_id: string;
  user_id: string;
  username: string;
  role_slot: string;
  joined_at: string;
}

/**
 * Raid quest creation payload (client or admin)
 */
export interface RaidQuestCreate {
  title: string;
  description: string;
  required_grade?: UserGrade;
  skills?: string[];
  budget: number;
  currency?: string;
  xp_reward?: number;
  raid_max_members: number;
  role_slots?: string[];
}

/**
 * Raid join request
 */
export interface RaidJoinRequest {
  role_slot: string;
}

/**
 * Raid party state response
 */
export interface RaidPartyResponse {
  quest_id: string;
  max_members: number;
  current_members: number;
  open_slots: number;
  participants: RaidParticipant[];
  role_slots: string[];
}


// ============================================
// Co-op Raid Quest API
// ============================================

export async function getRaidQuests(
  page = 1,
  pageSize = 10,
  grade?: UserGrade,
  skill?: string,
): Promise<QuestListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (grade) params.set("grade", grade);
  if (skill) params.set("skill", skill);
  const response = await fetchApi<QuestListResponseRaw>(
    `/quests/raid/list?${params}`,
    undefined,
    false,
  );
  return normalizeQuestListResponse(response);
}

export async function createRaidQuest(data: RaidQuestCreate): Promise<Quest> {
  const raw = await fetchApi<QuestRaw>(
    "/quests/raid/create",
    { method: "POST", body: JSON.stringify(data) },
    true,
  );
  return normalizeQuest(raw);
}

export async function joinRaidQuest(questId: string, roleSlot: string): Promise<RaidPartyResponse> {
  return fetchApi<RaidPartyResponse>(
    `/quests/raid/${questId}/join`,
    { method: "POST", body: JSON.stringify({ role_slot: roleSlot }) },
    true,
  );
}

export async function leaveRaidQuest(questId: string): Promise<RaidPartyResponse> {
  return fetchApi<RaidPartyResponse>(
    `/quests/raid/${questId}/leave`,
    { method: "POST" },
    true,
  );
}

export async function getRaidParty(questId: string): Promise<RaidPartyResponse> {
  return fetchApi<RaidPartyResponse>(
    `/quests/raid/${questId}/party`,
    undefined,
    false,
  );
}

export async function startRaidQuest(questId: string): Promise<Quest> {
  const raw = await fetchApi<QuestRaw>(
    `/quests/raid/${questId}/start`,
    { method: "POST" },
    true,
  );
  return normalizeQuest(raw);
}

export async function completeRaidQuest(questId: string): Promise<{ message: string; quest: Quest; participants: RaidParticipant[] }> {
  const response = await fetchApi<{ message: string; quest: QuestRaw; participants: RaidParticipant[] }>(
    `/quests/raid/${questId}/complete`,
    { method: "POST" },
    true,
  );
  return {
    ...response,
    quest: normalizeQuest(response.quest),
  };
}

// ============================================
// Legendary Quest Chains API
// ============================================

export type ChainStatus = "not_started" | "in_progress" | "completed";

export interface QuestChain {
  id: string;
  title: string;
  description: string;
  total_steps: number;
  final_xp_bonus: number;
  final_badge_id?: string | null;
  created_at: string;
}

export interface ChainStep {
  id: string;
  chain_id: string;
  quest_id: string;
  step_order: number;
}

export interface UserChainProgress {
  id: string;
  chain_id: string;
  user_id: string;
  current_step: number;
  status: ChainStatus;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ChainDetailResponse {
  chain: QuestChain;
  steps: ChainStep[];
  quests: Quest[];
  user_progress?: UserChainProgress | null;
}

export interface ChainListResponse {
  chains: QuestChain[];
  total: number;
}

export interface QuestChainCreatePayload {
  title: string;
  description: string;
  quest_ids: string[];
  final_xp_bonus?: number;
  final_badge_id?: string;
}

export async function getQuestChains(page = 1, pageSize = 20): Promise<ChainListResponse> {
  return fetchApi<ChainListResponse>(
    `/quests/chains/list?page=${page}&page_size=${pageSize}`,
  );
}

export async function getChainDetail(chainId: string): Promise<ChainDetailResponse> {
  const raw = await fetchApi<{ chain: QuestChain; steps: ChainStep[]; quests: QuestRaw[]; user_progress?: UserChainProgress | null }>(
    `/quests/chains/${chainId}`,
    undefined,
    true,
  );
  return {
    ...raw,
    quests: raw.quests.map(normalizeQuest),
  };
}

export async function createQuestChain(payload: QuestChainCreatePayload): Promise<ChainDetailResponse> {
  const raw = await fetchApi<{ chain: QuestChain; steps: ChainStep[]; quests: QuestRaw[]; user_progress?: UserChainProgress | null }>(
    `/quests/chains/create`,
    { method: "POST", body: JSON.stringify(payload) },
    true,
  );
  return {
    ...raw,
    quests: raw.quests.map(normalizeQuest),
  };
}

export async function getMyChainProgress(): Promise<{ progress: UserChainProgress[] }> {
  return fetchApi<{ progress: UserChainProgress[] }>(
    `/quests/chains/my-progress`,
    undefined,
    true,
  );
}

// ============================================
// Wallet API
// ============================================

export async function getWalletBalance(): Promise<WalletBalanceResponse> {
  const response = await fetchApi<WalletBalanceResponseRaw>("/wallet/balance", undefined, true);
  return normalizeWalletBalanceResponse(response);
}

export async function getWalletTransactions(
  limit = 50,
  offset = 0,
): Promise<WalletTransactionsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const response = await fetchApi<WalletTransactionsResponseRaw>(
    `/wallet/transactions?${params}`,
    undefined,
    true,
  );
  return normalizeWalletTransactionsResponse(response);
}

export async function requestWithdrawal(
  amount: number,
  currency = "RUB",
): Promise<WithdrawalResponse> {
  const idempotency_key = crypto.randomUUID();
  const response = await fetchApi<WithdrawalResponseRaw>(
    "/wallet/withdraw",
    {
      method: "POST",
      body: JSON.stringify({ amount, currency, idempotency_key }),
    },
    true,
  );
  return normalizeWithdrawalResponse(response);
}

export async function downloadWalletReceipt(
  transactionId: string,
): Promise<{ blob: Blob; filename: string | null }> {
  return fetchApiBlob(`/wallet/transactions/${transactionId}/receipt`, undefined, true);
}

export async function downloadWalletStatement(
  dateFrom: string,
  dateTo: string,
  format: WalletStatementFormat = "pdf",
): Promise<{ blob: Blob; filename: string | null }> {
  const params = new URLSearchParams({
    from: dateFrom,
    to: dateTo,
    format,
  });
  return fetchApiBlob(`/wallet/statements?${params.toString()}`, undefined, true);
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

export interface ReviewCheckResponse {
  has_reviewed: boolean;
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

export async function getReviewStatus(questId: string): Promise<ReviewCheckResponse> {
  return fetchApi<ReviewCheckResponse>(`/reviews/check/${questId}`, undefined, true);
}

// ============================================
// Quest Messages API
// ============================================

export interface QuestMessage {
  id: string;
  quest_id: string;
  author_id: string | null;
  author_username?: string | null;
  text: string;
  created_at: string;
  message_type: "user" | "system";
}

export interface QuestMessageListResponse {
  messages: QuestMessage[];
  total: number;
  unread_count: number;
}

export interface QuestDialog {
  quest_id: string;
  quest_title: string;
  quest_status: QuestStatus;
  other_user_id?: string | null;
  other_username?: string | null;
  last_message_text?: string | null;
  last_message_type: "user" | "system";
  last_message_at?: string | null;
  unread_count: number;
}

export interface QuestDialogListResponse {
  dialogs: QuestDialog[];
  total: number;
}

export interface WebSocketTicketResponse {
  ticket: string;
  expires_in_seconds: number;
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

export async function createQuestChatWsTicket(
  questId: string,
): Promise<WebSocketTicketResponse> {
  return fetchApi<WebSocketTicketResponse>(
    `/messages/${questId}/ws-ticket`,
    { method: "POST" },
    true,
  );
}

export async function getQuestDialogs(
  limit = 50,
  offset = 0,
): Promise<QuestDialogListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return fetchApi<QuestDialogListResponse>(buildCollectionEndpoint("/messages/dialogs", params), undefined, true);
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
  const response = await fetchApi<TemplateListResponseRaw>(buildCollectionEndpoint("/templates/", params), undefined, true);
  return normalizeTemplateListResponse(response);
}

export async function createTemplate(
  payload: CreateTemplatePayload,
): Promise<QuestTemplate> {
  const response = await fetchApi<QuestTemplateRaw>(
    "/templates/",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    true,
  );
  return normalizeQuestTemplate(response);
}

export async function deleteTemplate(templateId: string): Promise<void> {
  await fetchApiVoid(`/templates/${templateId}`, { method: "DELETE" }, true);
}

export async function getTemplate(
  templateId: string,
): Promise<QuestTemplate> {
  const response = await fetchApi<QuestTemplateRaw>(
    `/templates/${templateId}`,
    undefined,
    true,
  );
  return normalizeQuestTemplate(response);
}

export interface UpdateTemplatePayload {
  name?: string;
  title?: string;
  description?: string;
  required_grade?: string;
  skills?: string[];
  budget?: number;
  currency?: string;
  is_urgent?: boolean;
  required_portfolio?: boolean;
}

export async function updateTemplate(
  templateId: string,
  payload: UpdateTemplatePayload,
): Promise<QuestTemplate> {
  const response = await fetchApi<QuestTemplateRaw>(
    `/templates/${templateId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
    true,
  );
  return normalizeQuestTemplate(response);
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
  const response = await fetchApi<QuestRaw>(
    `/templates/${templateId}/create-quest`,
    {
      method: "POST",
      body: JSON.stringify(overrides ?? {}),
    },
    true,
  );
  return normalizeQuest(response);
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
  return fetchApi<NotificationListResponse>(buildCollectionEndpoint("/notifications/", params), {}, true);
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

export async function createNotificationsWsTicket(): Promise<WebSocketTicketResponse> {
  return fetchApi<WebSocketTicketResponse>(
    "/notifications/ws-ticket",
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
  has_class: boolean;
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
  bonus_perk_points: number;
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
    `/classes/abilities/${encodeURIComponent(abilityId)}/activate`,
    { method: "POST" },
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
  search?: string,
): Promise<AdminUsersResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (role) params.set("role", role);
  if (search) params.set("search", search);
  return fetchApi<AdminUsersResponse>(buildCollectionEndpoint("/admin/users", params), undefined, true);
}

/** GET /admin/quests — admin quest listing with server-side search (P2-07) */
export async function adminGetQuests(
  page = 1,
  pageSize = 50,
  status?: string,
  search?: string,
): Promise<{ quests: Quest[]; total: number; page: number; page_size: number; has_more: boolean }> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (status) params.set("status", status);
  if (search) params.set("search", search);
  return fetchApi(buildCollectionEndpoint("/admin/quests", params), undefined, true);
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
  const response = await fetchApi<AdminTransactionsResponseRaw>(buildCollectionEndpoint("/admin/transactions", params), undefined, true);
  return normalizeAdminTransactionsResponse(response);
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
  const response = await fetchApi<AdminTransactionsResponseRaw>(buildCollectionEndpoint("/admin/withdrawals/pending", params), undefined, true);
  return normalizeAdminTransactionsResponse(response);
}

/** PATCH /admin/withdrawals/:id/approve */
export async function adminApproveWithdrawal(
  transactionId: string,
): Promise<WithdrawalApproveResult> {
  const response = await fetchApi<WithdrawalApproveResultRaw>(
    `/admin/withdrawals/${transactionId}/approve`,
    { method: "PATCH" },
    true,
  );
  return normalizeWithdrawalApproveResult(response);
}

/** PATCH /admin/withdrawals/:id/reject */
export async function adminRejectWithdrawal(
  transactionId: string,
  reason: string,
): Promise<WithdrawalRejectResult> {
  const response = await fetchApi<WithdrawalRejectResultRaw>(
    `/admin/withdrawals/${transactionId}/reject`,
    { method: "PATCH", body: JSON.stringify({ reason }) },
    true,
  );
  return normalizeWithdrawalRejectResult(response);
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
  const response = await fetchApi<AdminLogsResponseRaw>(buildCollectionEndpoint("/admin/logs", params), undefined, true);
  return normalizeAdminLogsResponse(response);
}

/** GET /admin/operations — trust-layer operations feed */
export async function adminGetOperations(
  page = 1,
  pageSize = 50,
  filters?: { status?: string; action?: string; actor?: string },
): Promise<AdminOperationsFeedResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (filters?.status) params.set("status", filters.status);
  if (filters?.action) params.set("action", filters.action);
  if (filters?.actor) params.set("actor", filters.actor);
  return fetchApi<AdminOperationsFeedResponse>(buildCollectionEndpoint("/admin/operations", params), undefined, true);
}

/** GET /admin/runtime/heartbeats — worker/scheduler runtime status */
export async function adminGetRuntimeHeartbeats(options?: {
  runtimeKind?: string;
  limit?: number;
  activeOnly?: boolean;
}): Promise<AdminRuntimeHeartbeatsResponse> {
  const params = new URLSearchParams();
  if (options?.runtimeKind) params.set("runtime_kind", options.runtimeKind);
  if (options?.limit) params.set("limit", String(options.limit));
  if (typeof options?.activeOnly === "boolean") params.set("active_only", String(options.activeOnly));
  return fetchApi<AdminRuntimeHeartbeatsResponse>(buildCollectionEndpoint("/admin/runtime/heartbeats", params), undefined, true);
}

/** GET /admin/jobs/:id — trust-layer job detail */
export async function adminGetJobStatus(jobId: string): Promise<AdminJobStatusResponse> {
  return fetchApi<AdminJobStatusResponse>(`/admin/jobs/${jobId}`, undefined, true);
}

/** POST /admin/jobs/:id/requeue — manually replay failed or dead-letter job */
export async function adminRequeueJob(jobId: string, reason?: string): Promise<AdminJobReplayResponse> {
  return fetchApi<AdminJobReplayResponse>(
    `/admin/jobs/${jobId}/requeue`,
    { method: "POST", body: JSON.stringify({ reason: reason?.trim() || null }) },
    true,
  );
}

/** POST /admin/maintenance/cleanup-notifications */
export async function adminCleanupNotifications(): Promise<{
  deleted: number;
  message: string;
}> {
  return fetchApi(`/admin/maintenance/cleanup-notifications`, { method: "POST" }, true);
}

export async function adminSetupTotp(): Promise<AdminTotpSetupResponse> {
  return fetchApi<AdminTotpSetupResponse>("/admin/auth/totp/setup", { method: "POST" }, true);
}

export async function adminEnableTotp(token: string): Promise<AdminTotpEnableResponse> {
  return fetchApi<AdminTotpEnableResponse>(
    "/admin/auth/totp/enable",
    {
      method: "POST",
      body: JSON.stringify({ token }),
    },
    true,
  );
}


// ============================================
// Admin God Mode
// ============================================

/** GET /admin/stats — Platform-wide statistics */
export async function adminGetPlatformStats(): Promise<AdminPlatformStats> {
  const response = await fetchApi<AdminPlatformStatsRaw>("/admin/stats", undefined, true);
  return normalizeAdminPlatformStats(response);
}

/** GET /admin/users/:id — Full user detail */
export async function adminGetUserDetail(userId: string): Promise<AdminUserDetail> {
  const response = await fetchApi<AdminUserDetailRaw>(`/admin/users/${userId}`, undefined, true);
  return normalizeAdminUserDetail(response);
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

/** POST /admin/users/:id/grant-perk-points */
export async function adminGrantPerkPoints(
  userId: string,
  amount: number,
  reason: string,
): Promise<{
  user_id: string;
  class_id: string;
  granted: number;
  old_bonus_perk_points: number;
  new_bonus_perk_points: number;
  perk_points_total: number;
  perk_points_available: number;
}> {
  return fetchApi(`/admin/users/${userId}/grant-perk-points`, { method: "POST", body: JSON.stringify({ amount, reason }) }, true);
}

/** POST /admin/users/:id/adjust-wallet */
export async function adminAdjustWallet(userId: string, amount: number, currency: string, reason: string): Promise<AdminAdjustWalletResult> {
  const response = await fetchApi<AdminAdjustWalletResultRaw>(`/admin/users/${userId}/adjust-wallet`, { method: "POST", body: JSON.stringify({ amount, currency, reason }) }, true);
  return normalizeAdminAdjustWalletResult(response);
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
  const response = await fetchApi<AdminQuestDetailRaw>(`/admin/quests/${questId}`, undefined, true);
  return normalizeAdminQuestDetail(response);
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

// ── Analytics & Growth KPIs ─────────────────────────────────────────────────

export interface FunnelKPIs {
  landing_views: number;
  register_started: number;
  clients_registered: number;
  clients_with_quests: number;
  quests_created: number;
  applications_submitted: number;
  hires: number;
  confirmed_completions: number;
  clients_with_repeat_hire: number;
}

/** GET /analytics/funnel-kpis (admin only) */
export async function adminGetFunnelKPIs(): Promise<FunnelKPIs> {
  return fetchApi<FunnelKPIs>("/analytics/funnel-kpis", {}, true);
}

// ============================================
// Notification Preferences
// ============================================

export interface NotificationPreferences {
  transactional_enabled: boolean;
  growth_enabled: boolean;
  digest_enabled: boolean;
}

export async function getNotificationPreferences(): Promise<NotificationPreferences> {
  return fetchApi<NotificationPreferences>("/notifications/preferences", {}, true);
}

export async function updateNotificationPreferences(
  prefs: NotificationPreferences
): Promise<NotificationPreferences> {
  return fetchApi<NotificationPreferences>(
    "/notifications/preferences",
    { method: "PUT", body: JSON.stringify(prefs) },
    true
  );
}

// ============================================
// Saved Searches
// ============================================

export interface SavedSearch {
  id: string;
  user_id: string;
  name?: string;
  search_type: "talent" | "quest";
  filters_json: Record<string, unknown>;
  alert_enabled: boolean;
  last_alerted_at?: string;
  created_at?: string;
}

export interface SavedSearchCreate {
  name?: string;
  search_type: "talent" | "quest";
  filters_json: Record<string, unknown>;
  alert_enabled?: boolean;
}

export interface SavedSearchListResponse {
  items: SavedSearch[];
  total: number;
}

export async function getSavedSearches(): Promise<SavedSearchListResponse> {
  return fetchApi<SavedSearchListResponse>("/saved-searches/", {}, true);
}

export async function createSavedSearch(
  data: SavedSearchCreate
): Promise<SavedSearch> {
  return fetchApi<SavedSearch>(
    "/saved-searches/",
    { method: "POST", body: JSON.stringify(data) },
    true
  );
}

export async function deleteSavedSearch(id: string): Promise<void> {
  return fetchApi<void>(`/saved-searches/${id}`, { method: "DELETE" }, true);
}


// ─────────────────────────────────────
// Disputes
// ─────────────────────────────────────

export async function openDispute(quest_id: string, reason: string): Promise<Dispute> {
  return fetchApi<Dispute>(
    "/disputes",
    { method: "POST", body: JSON.stringify({ quest_id, reason }) },
    true
  );
}

export async function listMyDisputes(
  limit = 50,
  offset = 0
): Promise<DisputeListResponse> {
  return fetchApi<DisputeListResponse>(
    `/disputes?limit=${limit}&offset=${offset}`,
    {},
    true
  );
}

export async function getDispute(id: string): Promise<Dispute> {
  return fetchApi<Dispute>(`/disputes/${id}`, {}, true);
}

export async function respondDispute(
  id: string,
  response_text: string
): Promise<Dispute> {
  return fetchApi<Dispute>(
    `/disputes/${id}/respond`,
    { method: "PATCH", body: JSON.stringify({ response_text }) },
    true
  );
}

export async function escalateDispute(id: string): Promise<Dispute> {
  return fetchApi<Dispute>(
    `/disputes/${id}/escalate`,
    { method: "POST" },
    true
  );
}

export async function adminListDisputes(
  status?: string,
  limit = 50,
  offset = 0
): Promise<DisputeListResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (status) params.set("status", status);
  return fetchApi<DisputeListResponse>(`/admin/disputes?${params}`, {}, true);
}

export async function adminResolveDispute(
  id: string,
  resolution_type: string,
  resolution_note: string,
  partial_percent?: number
): Promise<Dispute> {
  return fetchApi<Dispute>(
    `/disputes/${id}/resolve`,
    {
      method: "PATCH",
      body: JSON.stringify({ resolution_type, resolution_note, partial_percent }),
    },
    true
  );
}


// ─────────────────────────────────────
// Events
// ─────────────────────────────────────

export async function getEvents(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<EventListResponse> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return fetchApi<EventListResponse>(`/events${query ? `?${query}` : ""}`);
}

export async function getEvent(eventId: string): Promise<GameEvent> {
  return fetchApi<GameEvent>(`/events/${eventId}`);
}

export async function getEventLeaderboard(
  eventId: string,
  params?: { limit?: number; offset?: number }
): Promise<EventLeaderboardResponse> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return fetchApi<EventLeaderboardResponse>(
    `/events/${eventId}/leaderboard${query ? `?${query}` : ""}`
  );
}

export async function joinEvent(eventId: string): Promise<EventParticipant> {
  return fetchApi<EventParticipant>(`/events/${eventId}/join`, { method: "POST" }, true);
}

export async function submitEventScore(
  eventId: string,
  scoreDelta: number
): Promise<EventParticipant> {
  return fetchApi<EventParticipant>(
    `/events/${eventId}/score`,
    { method: "POST", body: JSON.stringify({ score_delta: scoreDelta }) },
    true
  );
}

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
  startQuest,
  completeQuest,
  requestQuestRevision,
  confirmQuest,
  cancelQuest,
  getQuestApplications,
  getReviewStatus,
  getQuestDialogs,
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
  adminGetOperations,
  adminGetRuntimeHeartbeats,
  adminGetJobStatus,
  adminRequeueJob,
  adminCleanupNotifications,
  adminSetupTotp,
  adminEnableTotp,
  // Admin God Mode
  adminGetPlatformStats,
  adminGetUserDetail,
  adminUpdateUser,
  adminBanUser,
  adminUnbanUser,
  adminDeleteUser,
  adminGrantXP,
  adminGrantPerkPoints,
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
  // Disputes
  openDispute,
  listMyDisputes,
  getDispute,
  respondDispute,
  escalateDispute,
  adminListDisputes,
  adminResolveDispute,
  // Events
  getEvents,
  getEvent,
  getEventLeaderboard,
  joinEvent,
  submitEventScore,
  // Learning
  fetchLearningVoiceIntro,
  fetchLearningChat,
};

export default api;

// ── Learning Voice ───────────────────────────────────────────────

export type LearningSection = "human-languages" | "llm-ai" | "programming";

/**
 * POST /learning/voice-intro
 * Returns the raw audio blob (audio/mpeg) from the TTS streaming endpoint.
 * Rate-limited to 5 req/min per IP server-side.
 */
export async function fetchLearningVoiceIntro(section: LearningSection): Promise<Blob> {
  const { blob } = await fetchApiBlob(
    "/learning/voice-intro",
    {
      method: "POST",
      body: JSON.stringify({ section }),
    },
    false,
  );
  return blob;
}

// ── Learning Chat types ───────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface LearningChatResult {
  audioBlob: Blob;
  text: string;
}

/**
 * POST /learning/chat
 * Interactive chat with the learning AI.
 * Returns audio blob + the AI text via X-Response-Text header.
 * Rate-limited to 20 req/min per IP server-side.
 */
export async function fetchLearningChat(
  section: LearningSection,
  history: ChatMessage[],
  message: string,
): Promise<LearningChatResult> {
  const url = `${API_BASE_URL}/learning/chat`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ section, history, message }),
      signal: controller.signal,
      credentials: "include",
    });
    clearTimeout(timeoutId);
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const data = await response.json();
        detail = data.detail || data.message || detail;
      } catch { /* ignore parse error */ }
      throw buildApiError(response.status, detail);
    }
    const rawText = response.headers.get("X-Response-Text") ?? "";
    const text = rawText ? decodeURIComponent(rawText) : "";
    const audioBlob = await response.blob();
    return { audioBlob, text };
  } catch (error) {
    clearTimeout(timeoutId);
    if (isAbortError(error)) {
      throw buildApiError(0, "Сервер не ответил вовремя. Проверьте, что backend запущен.");
    }
    throw error;
  }
}

// ============================================
// Counter-offer API
// ============================================

export interface CounterOfferPayload {
  counter_price: number;
  message?: string;
}

export interface CounterOfferResponse {
  application_id: string;
  counter_offer_price: number | null;
  counter_offer_status: "pending" | "accepted" | "declined" | null;
  counter_offer_message: string | null;
  counter_offered_at: string | null;
  counter_responded_at: string | null;
}

/** Client sends a counter-offer on a freelancer's application. */
export async function sendCounterOffer(
  questId: string,
  applicationId: string,
  payload: CounterOfferPayload,
): Promise<CounterOfferResponse> {
  return fetchApi<CounterOfferResponse>(
    `/quests/${questId}/applications/${applicationId}/counter-offer`,
    { method: "POST", body: JSON.stringify(payload) },
    true,
  );
}

/** Freelancer accepts or declines a counter-offer. */
export async function respondToCounterOffer(
  questId: string,
  applicationId: string,
  accept: boolean,
): Promise<CounterOfferResponse> {
  return fetchApi<CounterOfferResponse>(
    `/quests/${questId}/applications/${applicationId}/counter-offer/respond`,
    { method: "POST", body: JSON.stringify({ accept }) },
    true,
  );
}

// ============================================
// Milestone API
// ============================================

export interface Milestone {
  id: string;
  quest_id: string;
  title: string;
  description: string | null;
  amount: number;
  currency: string;
  sort_order: number;
  status: "draft" | "active" | "completed" | "cancelled";
  due_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface MilestoneCreate {
  title: string;
  amount: number;
  description?: string;
  sort_order?: number;
  due_at?: string;
  currency?: string;
}

export async function getMilestones(questId: string): Promise<Milestone[]> {
  return fetchApi<Milestone[]>(`/quests/${questId}/milestones`, {}, true);
}

export async function createMilestone(questId: string, payload: MilestoneCreate): Promise<Milestone> {
  return fetchApi<Milestone>(
    `/quests/${questId}/milestones`,
    { method: "POST", body: JSON.stringify(payload) },
    true,
  );
}

export async function activateMilestone(questId: string, milestoneId: string): Promise<Milestone> {
  return fetchApi<Milestone>(
    `/quests/${questId}/milestones/${milestoneId}/activate`,
    { method: "POST" },
    true,
  );
}

export async function completeMilestone(questId: string, milestoneId: string): Promise<Milestone> {
  return fetchApi<Milestone>(
    `/quests/${questId}/milestones/${milestoneId}/complete`,
    { method: "POST" },
    true,
  );
}

export async function deleteMilestone(questId: string, milestoneId: string): Promise<void> {
  return fetchApiVoid(
    `/quests/${questId}/milestones/${milestoneId}`,
    { method: "DELETE" },
    true,
  );
}

// ============================================
// Weekly Challenges API
// ============================================

export interface WeeklyChallenge {
  id: string;
  challenge_type: string;
  title: string;
  description: string;
  target_value: number;
  xp_reward: number;
  week_start: string;
  current_value: number;
  completed: boolean;
  completed_at: string | null;
  reward_granted: boolean;
}

export async function getWeeklyChallenges(): Promise<WeeklyChallenge[]> {
  return fetchApi<WeeklyChallenge[]>("/challenges/weekly", {}, true);
}

// ============================================
// Referral API
// ============================================

export interface ReferralInfo {
  code: string | null;
  total_referred: number;
  rewarded_count: number;
}

export async function getMyReferralInfo(): Promise<ReferralInfo> {
  return fetchApi<ReferralInfo>("/referrals/me", {}, true);
}

export async function generateReferralCode(): Promise<ReferralInfo> {
  return fetchApi<ReferralInfo>("/referrals/generate", { method: "POST" }, true);
}

export async function applyReferralCode(code: string): Promise<{ referrer_id: string; applied: boolean }> {
  return fetchApi<{ referrer_id: string; applied: boolean }>(
    "/referrals/apply",
    { method: "POST", body: JSON.stringify({ code }) },
    true,
  );
}
