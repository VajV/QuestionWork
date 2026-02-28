/**
 * Header с навигацией
 * 
 * Показывает разные кнопки в зависимости от статуса авторизации:
 * - Не авторизован: кнопки "Войти" / "Регистрация"
 * - Авторизован: аватар, уровень, кнопка "Выйти"
 */

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import LevelBadge from "@/components/rpg/LevelBadge";

export default function Header() {
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();

  /**
   * Обработка выхода
   */
  const handleLogout = async () => {
    await logout();
    router.push("/");
  };

  return (
    <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          {/* Логотип */}
          <Link href="/" className="text-2xl font-bold">
            <span className="text-purple-400">Question</span>
            <span className="text-white">Work</span>
          </Link>

          {/* Навигация (центр) */}
          <nav className="hidden md:flex items-center gap-6">
            <Link href="/quests" className="text-gray-400 hover:text-white transition-colors">
              Квесты
            </Link>
            <Link href="/marketplace" className="text-gray-400 hover:text-white transition-colors">
              Биржа
            </Link>
          </nav>

          {/* Правая часть: авторизация или профиль */}
          <div className="flex items-center gap-4">
            {isAuthenticated && user ? (
              /* Авторизован: аватар + уровень + выход */
              <>
                {/* Инфо о пользователе */}
                <Link 
                  href="/profile" 
                  className="flex items-center gap-3 hover:bg-gray-800 rounded-lg px-3 py-2 transition-colors"
                >
                  {/* Аватар */}
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center text-sm font-bold">
                    {user.username[0].toUpperCase()}
                  </div>
                  
                  {/* Имя и уровень */}
                  <div className="hidden sm:block text-left">
                    <div className="text-sm font-medium text-white">
                      {user.username}
                    </div>
                    <div className="text-xs text-gray-400">
                      Lv.{user.level} {user.grade}
                    </div>
                  </div>
                </Link>

                {/* Кнопка выхода */}
                <button
                  onClick={handleLogout}
                  className="text-gray-400 hover:text-red-400 transition-colors text-sm"
                  title="Выйти"
                >
                  🚪 Выйти
                </button>
              </>
            ) : (
              /* Не авторизован: кнопки вход/регистрация */
              <>
                <Link
                  href="/auth/login"
                  className="text-gray-400 hover:text-white transition-colors text-sm"
                >
                  Войти
                </Link>
                <Link
                  href="/auth/register"
                  className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-lg shadow-purple-500/30"
                >
                  🚀 Регистрация
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
