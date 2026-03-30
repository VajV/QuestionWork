/**
 * AuthContext - Контекст аутентификации
 *
 * Управляет состоянием пользователя, токеном и функциями входа/выхода
 * Сохраняет только безопасный профиль пользователя в localStorage между перезагрузками
 */

"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import {
  login as apiLogin,
  register as apiRegister,
  logout as apiLogout,
  getSelfProfile,
  getApiErrorMessage,
  getApiErrorStatus,
  refreshSession,
  setAccessToken,
} from "@/lib/api";
import {
  clearAdminTotpError as clearStoredAdminTotpError,
  clearAdminTotpToken as clearStoredAdminTotpToken,
  getAdminTotpError,
  getAdminTotpToken,
  setAdminTotpToken as setStoredAdminTotpToken,
  subscribeAdminTotpState,
} from "@/lib/adminTotp";
import { registerLogoutHandler } from "@/lib/authEvents";
import type { UserProfile, LoginData, RegisterData } from "@/lib/api";

// ============================================
// Типы контекста
// ============================================

interface AuthContextType {
  // Состояние
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  adminTotpToken: string | null;
  adminTotpError: string | null;

  // Действия
  login: (
    credentials: LoginData,
  ) => Promise<{ success: boolean; error?: string }>;
  register: (
    data: RegisterData,
  ) => Promise<{ success: boolean; error?: string }>;
  setAdminTotpToken: (token: string) => void;
  clearAdminTotpToken: (error?: string) => void;
  clearAdminTotpError: () => void;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

// ============================================
// Константы
// ============================================

// const STORAGE_KEY_TOKEN = "questionwork_token";
const STORAGE_KEY_USER = "questionwork_user";

function clearStoredUser() {
  localStorage.removeItem(STORAGE_KEY_USER);
}

function readStoredUserHint(): Pick<UserProfile, "id" | "username"> | null {
  const raw = localStorage.getItem(STORAGE_KEY_USER);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<UserProfile>;
    if (!parsed?.id || !parsed?.username) {
      clearStoredUser();
      return null;
    }
    return { id: parsed.id, username: parsed.username };
  } catch {
    clearStoredUser();
    return null;
  }
}

/** Persist minimal user hint to localStorage for session resumption. */
function persistUser(user: UserProfile) {
  const hint = { id: user.id, username: user.username };
  localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(hint));
}

// ============================================
// Создание контекста
// ============================================

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ============================================
// Провайдер
// ============================================

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  // Состояния
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [adminTotpToken, setAdminTotpTokenState] = useState<string | null>(
    getAdminTotpToken(),
  );
  const [adminTotpError, setAdminTotpErrorState] = useState<string | null>(
    getAdminTotpError(),
  );

  const router = useRouter();

  /**
   * Инициализация при загрузке приложения
   * Восстанавливает токен и пользователя из localStorage
   */
  useEffect(() => {
    return subscribeAdminTotpState((state) => {
      setAdminTotpTokenState(state.token);
      setAdminTotpErrorState(state.error);
    });
  }, []);

  useEffect(() => {
    let isActive = true;
    let hardStopId: ReturnType<typeof setTimeout> | null = null;

    const initAuth = async () => {
      try {
        hardStopId = setTimeout(() => {
          if (isActive) {
            setLoading(false);
          }
        }, 7000);

        const storedUser = readStoredUserHint();
        if (!storedUser) {
          return;
        }

        const data = await refreshSession();
        if (!isActive) {
          return;
        }

        if (data?.access_token && data.user) {
          setToken(data.access_token);
          setUser(data.user);
          if (data.user.role !== "admin") {
            clearStoredAdminTotpToken();
          }
          // persist user profile for UI across reloads (strip email)
          persistUser(data.user);
        } else {
          // Refresh failed — clear stale user data so isAuthenticated stays false
          // and the UI doesn't show a logged-in state without a valid token.
          if (isActive) {
            clearStoredUser();
          }
        }
      } catch (_error) {
        if (isActive) {
          clearStoredUser();
        }
      } finally {
        if (hardStopId) {
          clearTimeout(hardStopId);
        }
        if (isActive) {
          setLoading(false);
        }
      }
    };

    initAuth();

    return () => {
      isActive = false;

      if (hardStopId) {
        clearTimeout(hardStopId);
      }
    };
  }, []);

  /**
   * Вход в систему
   *
   * @param credentials - Логин и пароль
   * @returns Объект с результатом операции
   */
  const login = useCallback(
    async (
      credentials: LoginData,
    ): Promise<{ success: boolean; error?: string }> => {
      try {
        clearStoredAdminTotpToken();
        const response = await apiLogin(credentials);

        // Save access token in memory and user profile in storage
        setAccessToken(response.access_token);
        setToken(response.access_token);
        setUser(response.user);
        persistUser(response.user);

        return { success: true };
      } catch (error) {
        const message = getApiErrorMessage(error, "Не удалось войти");
        const status = getApiErrorStatus(error);
        if (process.env.NODE_ENV !== "production" && (status === undefined || status === 0 || status >= 500)) {
          console.warn("Ошибка входа:", { status, message });
        }
        return { success: false, error: message };
      }
    },
    [],
  );

  /**
   * Регистрация нового пользователя
   *
   * @param data - Данные для регистрации
   * @returns Объект с результатом операции
   */
  const register = useCallback(
    async (
      data: RegisterData,
    ): Promise<{ success: boolean; error?: string }> => {
      try {
        clearStoredAdminTotpToken();
        const response = await apiRegister(data);

        // Save access token in memory and user profile in storage (auto-login)
        setAccessToken(response.access_token);
        setToken(response.access_token);
        setUser(response.user);
        persistUser(response.user);

        return { success: true };
      } catch (error) {
        const message = getApiErrorMessage(error, "Не удалось зарегистрироваться");
        const status = getApiErrorStatus(error);
        if (process.env.NODE_ENV !== "production" && (status === undefined || status === 0 || status >= 500)) {
          console.warn("Ошибка регистрации:", { status, message });
        }
        return {
          success: false,
          error: message,
        };
      }
    },
    [],
  );

  /**
   * Выход из системы
   * Очищает токен и данные пользователя
   */
  const logout = useCallback(async () => {
    try {
      // Пытаемся вызвать logout на сервере (опционально)
      await apiLogout().catch(() => {
        // Игнорируем ошибки сервера, всё равно очищаем локальные данные
      });
    } finally {
      // Всегда очищаем локальные данные
      setToken(null);
      setUser(null);
      setAccessToken(null);
      clearStoredAdminTotpToken();
      clearStoredUser();
    }
  }, []);

  const setAdminTotpToken = useCallback((nextToken: string) => {
    setStoredAdminTotpToken(nextToken);
  }, []);

  const clearAdminTotpToken = useCallback((error?: string) => {
    clearStoredAdminTotpToken(error ?? null);
  }, []);

  const clearAdminTotpError = useCallback(() => {
    clearStoredAdminTotpError();
  }, []);

  /**
   * Обновить данные пользователя
   * Используется для получения актуального уровня, опыта и т.д.
   */
  const refreshUser = useCallback(async () => {
    if (!user?.id) return;

    try {
      // P1-14 FIX: use authenticated /users/me so is_banned + email stay current
      const freshUser = await getSelfProfile();
      setUser((previousUser) => {
        if (!previousUser) {
          return previousUser;
        }
        const mergedUser: UserProfile = {
          ...previousUser,
          ...freshUser,
        };
        persistUser(mergedUser);
        return mergedUser;
      });
    } catch (error) {
      const message = getApiErrorMessage(error, "Не удалось обновить пользователя");
      const status = getApiErrorStatus(error);
      if (process.env.NODE_ENV !== "production" && (status === undefined || status === 0 || status >= 500)) {
        console.warn("Ошибка обновления пользователя:", { status, message });
      }
    }
  }, [user?.id]);

  // Вычисляем isAuthenticated на основе наличия токена и пользователя
  const isAuthenticated = !!token && !!user;

  // Register a forced-logout callback so api.ts can redirect on session expiry.
  // This runs once after logout is stable (useCallback with [] deps).
  useEffect(() => {
    registerLogoutHandler(() => {
      logout();
      router.push("/auth/login?expired=1");
    });
  }, [logout, router]);

  // Значение контекста
  const contextValue = useMemo<AuthContextType>(
    () => ({
      user,
      token,
      isAuthenticated,
      loading,
      adminTotpToken,
      adminTotpError,
      login,
      register,
      setAdminTotpToken,
      clearAdminTotpToken,
      clearAdminTotpError,
      logout,
      refreshUser,
    }),
    [
      user,
      token,
      isAuthenticated,
      loading,
      adminTotpToken,
      adminTotpError,
      login,
      register,
      setAdminTotpToken,
      clearAdminTotpToken,
      clearAdminTotpError,
      logout,
      refreshUser,
    ],
  );

  return (
    <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  );
}

// ============================================
// Хук для использования контекста
// ============================================

/**
 * Хук для доступа к контексту аутентификации
 *
 * @returns AuthContextType или undefined если используется вне AuthProvider
 *
 * @example
 * const { user, login, logout } = useAuth();
 */
export function useAuth() {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error("useAuth должен использоваться внутри AuthProvider");
  }

  return context;
}

// ============================================
// Экспорт по умолчанию
// ============================================

export default AuthContext;






