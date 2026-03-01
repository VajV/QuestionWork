"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

type UserRole = "client" | "freelancer";

export default function RegisterPage() {
  const router = useRouter();
  const { register, isAuthenticated } = useAuth();
  
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState<UserRole>("freelancer");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isAuthenticated) {
    router.push("/profile");
    return null;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!username.trim() || !email.trim() || !password.trim()) {
      setError("Заполните все поля");
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setError("Некорректный email");
      return;
    }

    if (username.trim().length < 3) {
      setError("Имя должно содержать минимум 3 символа");
      return;
    }

    if (password.length < 8) {
      setError("Пароль должен содержать минимум 8 символов");
      return;
    }

    if (password !== confirmPassword) {
      setError("Пароли не совпадают");
      return;
    }

    setLoading(true);

    try {
      const result = await register({
        username: username.trim(),
        email: email.trim(),
        password,
        role,
      });

      if (result.success) {
        setTimeout(() => router.push("/profile"), 100);
      } else {
        setError(result.error || "Ошибка регистрации");
      }
    } catch (err) {
      console.error("Registration error:", err);
      setError("Произошла ошибка");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 flex items-center justify-center px-4 py-8">
      <Card className="w-full max-w-md p-8">
        <div className="text-center mb-8">
          <Link href="/" className="text-3xl font-bold">
            <span className="text-purple-400">Question</span>
            <span className="text-white">Work</span>
          </Link>
          <h1 className="text-2xl font-bold mt-4">Создать аккаунт</h1>
          <p className="text-gray-400 mt-2">Начните свой путь в IT-фрилансе</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-900/30 border border-red-500/50 rounded-lg text-red-200 text-sm">
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-1">
              Имя пользователя *
            </label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white"
              placeholder="novice_dev"
              disabled={loading}
              required
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1">
              Email *
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white"
              placeholder="you@example.com"
              disabled={loading}
              required
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-1">
              Пароль *
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white"
              placeholder="••••••••"
              disabled={loading}
              required
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-300 mb-1">
              Подтвердите пароль *
            </label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white"
              placeholder="••••••••"
              disabled={loading}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Тип аккаунта *</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setRole("freelancer")}
                className={`p-3 rounded-lg border-2 transition-all ${
                  role === "freelancer"
                    ? "border-purple-500 bg-purple-500/20"
                    : "border-gray-700 bg-gray-800"
                }`}
              >
                <div className="text-2xl mb-1">👨‍💻</div>
                <div className="font-medium text-sm">Фрилансер</div>
                <div className="text-xs text-gray-400 mt-1">Выполнять квесты</div>
              </button>
              <button
                type="button"
                onClick={() => setRole("client")}
                className={`p-3 rounded-lg border-2 transition-all ${
                  role === "client"
                    ? "border-purple-500 bg-purple-500/20"
                    : "border-gray-700 bg-gray-800"
                }`}
              >
                <div className="text-2xl mb-1">💼</div>
                <div className="font-medium text-sm">Клиент</div>
                <div className="text-xs text-gray-400 mt-1">Создавать квесты</div>
              </button>
            </div>
          </div>

          <Button type="submit" variant="primary" className="w-full" disabled={loading}>
            {loading ? "Регистрация..." : "🚀 Создать аккаунт"}
          </Button>
        </form>

        <div className="mt-6 text-center text-sm text-gray-400">
          Уже есть аккаунт?{" "}
          <Link href="/auth/login" className="text-purple-400 hover:text-purple-300 font-medium">
            Войти
          </Link>
        </div>
      </Card>
    </main>
  );
}
