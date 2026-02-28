/**
 * AuthContext - Контекст аутентификации
 * 
 * Управляет состоянием пользователя, токеном и функциями входа/выхода
 * Сохраняет токен в localStorage для сохранения сессии между перезагрузками
 */

"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { login as apiLogin, register as apiRegister, logout as apiLogout, getUserProfile } from '@/lib/api';
import type { UserProfile, LoginData, RegisterData } from '@/lib/api';

// ============================================
// Типы контекста
// ============================================

interface AuthContextType {
  // Состояние
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  
  // Действия
  login: (credentials: LoginData) => Promise<{ success: boolean; error?: string }>;
  register: (data: RegisterData) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

// ============================================
// Константы
// ============================================

const STORAGE_KEY_TOKEN = 'questionwork_token';
const STORAGE_KEY_USER = 'questionwork_user';

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

  /**
   * Инициализация при загрузке приложения
   * Восстанавливает токен и пользователя из localStorage
   */
  useEffect(() => {
    const initAuth = async () => {
      try {
        // Восстанавливаем токен
        const storedToken = localStorage.getItem(STORAGE_KEY_TOKEN);
        const storedUser = localStorage.getItem(STORAGE_KEY_USER);
        
        if (storedToken && storedUser) {
          setToken(storedToken);
          const parsedUser = JSON.parse(storedUser);
          
          // Проверяем актуальность данных пользователя
          try {
            const freshUser = await getUserProfile(parsedUser.id);
            setUser(freshUser);
            localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(freshUser));
          } catch (error) {
            // Если не удалось обновить, используем сохранённые данные
            setUser(parsedUser);
          }
        }
      } catch (error) {
        console.error('Ошибка инициализации аутентификации:', error);
        // Очищаем невалидные данные
        localStorage.removeItem(STORAGE_KEY_TOKEN);
        localStorage.removeItem(STORAGE_KEY_USER);
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, []);

  /**
   * Вход в систему
   * 
   * @param credentials - Логин и пароль
   * @returns Объект с результатом операции
   */
  const login = useCallback(async (credentials: LoginData): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await apiLogin(credentials);
      
      // Сохраняем токен и пользователя
      setToken(response.access_token);
      setUser(response.user);
      localStorage.setItem(STORAGE_KEY_TOKEN, response.access_token);
      localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(response.user));
      
      return { success: true };
    } catch (error) {
      console.error('Ошибка входа:', error);
      
      let errorMessage = 'Не удалось войти';
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'detail' in error) {
        errorMessage = (error as any).detail || errorMessage;
      }
      
      return { success: false, error: errorMessage };
    }
  }, []);

  /**
   * Регистрация нового пользователя
   * 
   * @param data - Данные для регистрации
   * @returns Объект с результатом операции
   */
  const register = useCallback(async (data: RegisterData): Promise<{ success: boolean; error?: string }> => {
    try {
      const response = await apiRegister(data);
      
      // Сохраняем токен и пользователя (автоматический вход после регистрации)
      setToken(response.access_token);
      setUser(response.user);
      localStorage.setItem(STORAGE_KEY_TOKEN, response.access_token);
      localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(response.user));
      
      return { success: true };
    } catch (error) {
      console.error('Ошибка регистрации:', error);
      
      let errorMessage = 'Не удалось зарегистрироваться';
      if (error instanceof Error) {
        errorMessage = error.message;
      } else if (typeof error === 'object' && error !== null && 'detail' in error) {
        errorMessage = (error as any).detail || errorMessage;
      }
      
      return { success: false, error: errorMessage };
    }
  }, []);

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
      localStorage.removeItem(STORAGE_KEY_TOKEN);
      localStorage.removeItem(STORAGE_KEY_USER);
    }
  }, []);

  /**
   * Обновить данные пользователя
   * Используется для получения актуального уровня, опыта и т.д.
   */
  const refreshUser = useCallback(async () => {
    if (!user?.id) return;
    
    try {
      const freshUser = await getUserProfile(user.id);
      setUser(freshUser);
      localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(freshUser));
    } catch (error) {
      console.error('Ошибка обновления пользователя:', error);
    }
  }, [user?.id]);

  // Вычисляем isAuthenticated на основе наличия токена и пользователя
  const isAuthenticated = !!token && !!user;

  // Значение контекста
  const contextValue: AuthContextType = {
    user,
    token,
    isAuthenticated,
    loading,
    login,
    register,
    logout,
    refreshUser,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
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
    throw new Error('useAuth должен использоваться внутри AuthProvider');
  }
  
  return context;
}

// ============================================
// Экспорт по умолчанию
// ============================================

export default AuthContext;
