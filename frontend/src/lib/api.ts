/**
 * QuestionWork API Client
 * Клиент для взаимодействия с FastAPI backend
 *
 * Поддерживает автоматическую подстановку Bearer токена
 */

// Базовый URL API (можно вынести в .env.local)
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

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
export type QuestStatus = "open" | "in_progress" | "completed" | "cancelled";

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
  role: "client" | "freelancer";
  level: number;
  grade: UserGrade;
  xp: number;
  xp_to_next: number;
  stats: UserStats;
  badges: UserBadge[];
  bio: string | null;
  skills: string[];
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
  role: "client" | "freelancer";
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
export function getAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return localStorage.getItem("questionwork_token");
}

/**
 * Выполнение fetch запроса с обработкой ошибок и токеном
 */
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
  requireAuth: boolean = false,
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const token = requireAuth ? getAuthToken() : null;

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
    const response = await fetch(url, { ...config, signal: controller.signal });
    clearTimeout(timeoutId);

    if (response.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("questionwork_token");
        localStorage.removeItem("questionwork_user");
      }

      throw new Response("Unauthorized: Token invalid or expired", {
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
  return fetchApi<TokenResponse>(
    "/auth/login",
    {
      method: "POST",
      body: JSON.stringify(credentials),
    },
    false,
  );
}

export async function logout(): Promise<{ message: string }> {
  return fetchApi<{ message: string }>(
    "/auth/logout",
    {
      method: "POST",
    },
    true,
  );
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
};

export default api;
