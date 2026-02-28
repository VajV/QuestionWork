/**
 * QuestionWork API Client
 * Клиент для взаимодействия с FastAPI backend
 * 
 * Поддерживает автоматическую подстановку Bearer токена
 */

// Базовый URL API (можно вынести в .env.local)
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// ============================================
// TypeScript интерфейсы для API ответов
// ============================================

/**
 * Характеристики пользователя (RPG статы)
 */
export interface UserStats {
  int: number;      // Интеллект
  dex: number;      // Ловкость
  cha: number;      // Харизма
}

/**
 * Бейдж достижения
 */
export interface UserBadge {
  id: string;
  name: string;
  description: string;
  icon: string;
  earned_at: string;  // ISO 8601 дата
}

/**
 * Грейд пользователя (RPG система)
 */
export type UserGrade = 'novice' | 'junior' | 'middle' | 'senior';

/**
 * Профиль пользователя (полный ответ от API)
 */
export interface UserProfile {
  id: string;
  username: string;
  email: string | null;
  level: number;
  grade: UserGrade;
  xp: number;
  xp_to_next: number;
  stats: UserStats;
  badges: UserBadge[];
  bio: string | null;
  skills: string[];
  created_at: string;  // ISO 8601 дата
  updated_at: string;  // ISO 8601 дата
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

// ============================================
// Вспомогательные функции
// ============================================

/**
 * Получить токен из localStorage
 * Используется для автоматической подстановки в заголовки
 */
export function getAuthToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  return localStorage.getItem('questionwork_token');
}

/**
 * Обработка ошибок API
 */
function handleApiError(error: unknown): ApiError {
  if (error instanceof Response) {
    // HTTP ошибка от сервера
    return {
      status: error.status,
      message: `HTTP ${error.status}`,
      detail: error.statusText,
    };
  }
  
  if (error instanceof Error) {
    // Сетевая ошибка или другая ошибка
    return {
      status: 0,
      message: 'Network Error',
      detail: error.message,
    };
  }
  
  // Неизвестная ошибка
  return {
    status: 0,
    message: 'Unknown Error',
    detail: String(error),
  };
}

/**
 * Выполнение fetch запроса с обработкой ошибок и автоматической подстановкой токена
 * 
 * @param endpoint - URL endpoint относительно API_BASE_URL
 * @param options - Опции fetch
 * @param requireAuth - Требуется ли авторизация (добавляет Bearer токен)
 */
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
  requireAuth: boolean = false
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  // Получаем токен если требуется авторизация
  const token = requireAuth ? getAuthToken() : null;
  
  const defaultOptions: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  };
  
  const config = { ...defaultOptions, ...options };
  
  // Merge headers properly
  if (options?.headers) {
    config.headers = {
      ...defaultOptions.headers,
      ...options.headers,
    };
  }
  
  try {
    const response = await fetch(url, config);
    
    // Обработка 401 Unauthorized (токен невалиден)
    if (response.status === 401) {
      // Очищаем невалидный токен
      if (typeof window !== 'undefined') {
        localStorage.removeItem('questionwork_token');
        localStorage.removeItem('questionwork_user');
      }
      
      throw new Response('Unauthorized: Token invalid or expired', {
        status: 401,
        statusText: 'Unauthorized',
      });
    }
    
    if (!response.ok) {
      // Пытаемся получить детальную ошибку от сервера
      let errorDetail = response.statusText;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorData.message || response.statusText;
      } catch {
        // Не удалось распарсить JSON ошибки
      }
      
      throw new Response(`API Error: ${errorDetail}`, {
        status: response.status,
        statusText: errorDetail,
      });
    }
    
    // Если ответ пустой (204 No Content)
    if (response.status === 204) {
      return {} as T;
    }
    
    return await response.json();
  } catch (error) {
    // Пробрасываем ошибку дальше
    throw error;
  }
}

// ============================================
// API функции
// ============================================

/**
 * Получить профиль пользователя по ID
 * 
 * @param userId - Уникальный ID пользователя
 * @returns Профиль пользователя
 */
export async function getUserProfile(userId: string): Promise<UserProfile> {
  return fetchApi<UserProfile>(`/users/${userId}`);
}

/**
 * Получить только характеристики пользователя
 * 
 * @param userId - Уникальный ID пользователя
 * @returns Объект со статами (INT, DEX, CHA)
 */
export async function getUserStats(userId: string): Promise<UserStats> {
  return fetchApi<UserStats>(`/users/${userId}/stats`);
}

/**
 * Получить список всех пользователей
 * 
 * @param skip - Пропустить N пользователей (пагинация)
 * @param limit - Максимальное количество результатов
 * @param grade - Фильтр по грейду (опционально)
 * @returns Массив профилей пользователей
 */
export async function getAllUsers(
  skip: number = 0,
  limit: number = 10,
  grade?: UserGrade
): Promise<UserProfile[]> {
  const params = new URLSearchParams({
    skip: skip.toString(),
    limit: limit.toString(),
  });
  
  if (grade) {
    params.append('grade', grade);
  }
  
  return fetchApi<UserProfile[]>(`/users?${params.toString()}`);
}

/**
 * Зарегистрировать нового пользователя
 * 
 * @param data - Данные для регистрации
 * @returns Токен и профиль пользователя
 */
export async function register(data: RegisterData): Promise<TokenResponse> {
  // Не требуем auth для регистрации
  return fetchApi<TokenResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  }, false);
}

/**
 * Войти в систему
 * 
 * @param credentials - Логин и пароль
 * @returns Токен и профиль пользователя
 */
export async function login(credentials: LoginData): Promise<TokenResponse> {
  // Не требуем auth для логина
  return fetchApi<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  }, false);
}

/**
 * Выйти из системы
 * 
 * @returns Сообщение об успехе
 */
export async function logout(): Promise<{ message: string }> {
  // Требуем auth для logout
  return fetchApi<{ message: string }>('/auth/logout', {
    method: 'POST',
  }, true);
}

/**
 * Проверить работоспособность API
 * 
 * @returns Статус API
 */
export async function checkHealth(): Promise<{ status: string; message: string }> {
  // Health endpoint находится вне /api/v1
  const response = await fetch('http://localhost:8000/health');
  return await response.json();
}

/**
 * Получить текущий профиль авторизованного пользователя
 * 
 * @returns Профиль текущего пользователя
 */
export async function getCurrentUser(): Promise<UserProfile> {
  const token = getAuthToken();
  if (!token) {
    throw new Error('Not authenticated');
  }
  
  // Для получения текущего пользователя нужен отдельный endpoint
  // Пока используем заглушку - в будущем будет /users/me
  throw new Error('Endpoint /users/me not implemented yet');
}

// ============================================
// Экспорт для удобства
// ============================================

export default {
  getUserProfile,
  getUserStats,
  getAllUsers,
  register,
  login,
  logout,
  checkHealth,
  getCurrentUser,
  getAuthToken,
};
