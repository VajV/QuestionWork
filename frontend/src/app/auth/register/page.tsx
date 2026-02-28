/**
 * Страница регистрации нового пользователя
 * 
 * Форма с валидацией пароля и проверкой совпадения
 */

"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function RegisterPage() {
  const router = useRouter();
  const { register, isAuthenticated } = useAuth();
  
  // Состояния формы
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Если уже авторизован — редирект на профиль
  if (isAuthenticated) {
    router.push("/profile");
    return null;
  }

  /**
   * Валидация username
   * Разрешены: буквы, цифры, подчёркивания, дефисы
   * Длина: 3-50 символов
   */
  const validateUsername = (name: string): string | null => {
    if (name.length < 3) {
      return "Имя пользователя должно содержать минимум 3 символа";
    }
    if (name.length > 50) {
      return "Имя пользователя должно содержать максимум 50 символов";
    }
    // Разрешаем буквы (латиница), цифры, подчёркивания и дефисы
    const validPattern = /^[a-zA-Z0-9_-]+$/;
    if (!validPattern.test(name)) {
      return "Имя может содержать только буквы, цифры, подчёркивания (_) и дефисы (-)";
    }
    return null;
  };

  /**
   * Валидация пароля
   */
  const validatePassword = (pwd: string): string | null => {
    if (pwd.length < 8) {
      return "Пароль должен содержать минимум 8 символов";
    }
    if (!/[a-zA-Z]/.test(pwd)) {
      return "Пароль должен содержать хотя бы одну букву";
    }
    if (!/[0-9]/.test(pwd)) {
      return "Пароль должен содержать хотя бы одну цифру";
    }
    return null;
  };

  /**
   * Обработка отправки формы
   */
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Валидация всех полей
    if (!username.trim() || !email.trim() || !password.trim()) {
      setError("Заполните все обязательные поля");
      return;
    }

    // Валидация email (простая)
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setError("Введите корректный email адрес");
      return;
    }

    // Валидация username
    const usernameError = validateUsername(username.trim());
    if (usernameError) {
      setError(usernameError);
      return;
    }

    // Валидация пароля
    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    // Проверка совпадения паролей
    if (password !== confirmPassword) {
      setError("Пароли не совпадают");
      return;
    }

    setLoading(true);

    try {
      // Попытка регистрации
      const result = await register({
        username: username.trim(),
        email: email.trim(),
        password,
      });

      if (result.success) {
        // Успешная регистрация — редирект на профиль
        // Даём время на сохранение токена
        setTimeout(() => {
          router.push("/profile");
        }, 100);
      } else {
        // Ошибка — показываем сообщение
        setError(result.error || "Не удалось зарегистрироваться");
      }
    } catch (err) {
      console.error("Registration error:", err);
      setError("Произошла ошибка при регистрации");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 flex items-center justify-center px-4 py-8">
      <Card className="w-full max-w-md p-8">
        {/* Логотип */}
        <div className="text-center mb-8">
          <Link href="/" className="text-3xl font-bold">
            <span className="text-purple-400">Question</span>
            <span className="text-white">Work</span>
          </Link>
          <h1 className="text-2xl font-bold mt-4">Создать аккаунт</h1>
          <p className="text-gray-400 mt-2">
            Начните свой путь в IT-фрилансе
          </p>
        </div>

        {/* Сообщение об ошибке */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/30 border border-red-500/50 rounded-lg text-red-200 text-sm">
            ⚠️ {error}
          </div>
        )}

        {/* Форма регистрации */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Поле username */}
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-1">
              Имя пользователя *
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
              minLength={3}
              maxLength={50}
              pattern="[a-zA-Z0-9_-]+"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              Разрешены: буквы, цифры, _ и -
            </p>
          </div>

          {/* Поле email */}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1">
              Email *
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500"
              placeholder="you@example.com"
              autoComplete="email"
              disabled={loading}
              required
            />
          </div>

          {/* Поле password */}
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-1">
              Пароль *
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500"
              placeholder="••••••••"
              autoComplete="new-password"
              disabled={loading}
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              Минимум 8 символов, буквы и цифры
            </p>
          </div>

          {/* Поле confirmPassword */}
          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-300 mb-1">
              Подтвердите пароль *
            </label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500"
              placeholder="••••••••"
              autoComplete="new-password"
              disabled={loading}
              required
            />
          </div>

          {/* Кнопка регистрации */}
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
                Регистрация...
              </span>
            ) : (
              "🚀 Создать аккаунт"
            )}
          </Button>
        </form>

        {/* Ссылка на вход */}
        <div className="mt-6 text-center text-sm text-gray-400">
          Уже есть аккаунт?{" "}
          <Link href="/auth/login" className="text-purple-400 hover:text-purple-300 font-medium">
            Войти
          </Link>
        </div>

        {/* Требования */}
        <div className="mt-6 p-4 bg-gray-800/50 rounded-lg border border-gray-700">
          <p className="text-xs text-gray-500 mb-2">🔒 Требования:</p>
          <ul className="text-xs text-gray-400 space-y-1">
            <li>• Имя: 3-50 символов (буквы, цифры, _, -)</li>
            <li>• Пароль: мин. 8 символов, буквы и цифры</li>
          </ul>
        </div>
      </Card>
    </main>
  );
}
