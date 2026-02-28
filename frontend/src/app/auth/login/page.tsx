/**
 * Страница входа в систему
 * 
 * Форма аутентификации с валидацией и обработкой ошибок
 */

"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated } = useAuth();
  
  // Состояния формы
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Если уже авторизован — редирект на профиль
  if (isAuthenticated) {
    router.push("/profile");
    return null;
  }

  /**
   * Обработка отправки формы
   */
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    // Простая валидация
    if (!username.trim() || !password.trim()) {
      setError("Заполните все поля");
      setLoading(false);
      return;
    }

    // Попытка входа
    const result = await login({ username: username.trim(), password });

    if (result.success) {
      // Успешный вход — редирект на профиль
      router.push("/profile");
    } else {
      // Ошибка — показываем сообщение
      setError(result.error || "Не удалось войти");
    }

    setLoading(false);
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 flex items-center justify-center px-4">
      <Card className="w-full max-w-md p-8">
        {/* Логотип */}
        <div className="text-center mb-8">
          <Link href="/" className="text-3xl font-bold">
            <span className="text-purple-400">Question</span>
            <span className="text-white">Work</span>
          </Link>
          <h1 className="text-2xl font-bold mt-4">Вход в систему</h1>
          <p className="text-gray-400 mt-2">
            Добро пожаловать обратно!
          </p>
        </div>

        {/* Сообщение об ошибке */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/30 border border-red-500/50 rounded-lg text-red-200 text-sm">
            ⚠️ {error}
          </div>
        )}

        {/* Форма входа */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Поле username */}
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-1">
              Имя пользователя
            </label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500"
              placeholder="novice_dev"
              autoComplete="username"
              disabled={loading}
            />
          </div>

          {/* Поле password */}
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-1">
              Пароль
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500"
              placeholder="••••••••"
              autoComplete="current-password"
              disabled={loading}
            />
          </div>

          {/* Кнопка входа */}
          <Button
            type="submit"
            variant="primary"
            className="w-full"
            disabled={loading}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Вход...
              </span>
            ) : (
              "🔑 Войти"
            )}
          </Button>
        </form>

        {/* Ссылка на регистрацию */}
        <div className="mt-6 text-center text-sm text-gray-400">
          Нет аккаунта?{" "}
          <Link href="/auth/register" className="text-purple-400 hover:text-purple-300 font-medium">
            Зарегистрироваться
          </Link>
        </div>

        {/* Демо-данные для тестирования */}
        <div className="mt-6 p-4 bg-gray-800/50 rounded-lg border border-gray-700">
          <p className="text-xs text-gray-500 mb-2">📝 Тестовые учётные данные:</p>
          <div className="text-xs text-gray-400 space-y-1 font-mono">
            <div>Username: <span className="text-purple-300">novice_dev</span></div>
            <div>Password: <span className="text-purple-300">password123</span></div>
          </div>
        </div>
      </Card>
    </main>
  );
}
