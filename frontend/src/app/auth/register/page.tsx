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
        <div className="text-center mb-8 relative">
          <Link href="/" className="text-3xl font-cinzel font-bold tracking-widest flex justify-center items-center gap-2 group">
            <span className="text-amber-500 drop-shadow-[0_0_8px_rgba(217,119,6,0.5)] group-hover:text-amber-400 transition-colors">⚡ Question</span>
            <span className="text-gray-300">Work</span>
          </Link>
          <div className="divider-ornament my-6"></div>
          <h1 className="text-2xl font-cinzel font-bold mt-4 text-purple-200">Инициация Гильдии</h1>
          <p className="text-gray-400 font-inter mt-2 text-sm">Впишите своё имя в историю</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-950/40 border border-red-800/50 rounded text-red-300 font-mono text-sm shadow-[0_0_10px_rgba(220,38,38,0.2)]">
            💀 {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="username" className="block text-xs font-cinzel font-bold text-amber-500/80 uppercase tracking-widest mb-2">
              Имя Героя *
            </label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 bg-black/40 border border-purple-900/50 rounded focus:outline-none focus:border-amber-500/50 focus:bg-purple-950/20 text-gray-200 placeholder-gray-600 font-mono transition-all shadow-inner"
              placeholder="novice_dev"
              disabled={loading}
              required
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-xs font-cinzel font-bold text-amber-500/80 uppercase tracking-widest mb-2">
              Магическая почта (Email) *
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 bg-black/40 border border-purple-900/50 rounded focus:outline-none focus:border-amber-500/50 focus:bg-purple-950/20 text-gray-200 placeholder-gray-600 font-mono transition-all shadow-inner"
              placeholder="you@example.com"
              disabled={loading}
              required
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-cinzel font-bold text-amber-500/80 uppercase tracking-widest mb-2">
              Секретный Код *
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 bg-black/40 border border-purple-900/50 rounded focus:outline-none focus:border-amber-500/50 focus:bg-purple-950/20 text-gray-200 placeholder-gray-600 font-mono transition-all shadow-inner"
              placeholder="••••••••"
              disabled={loading}
              required
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-xs font-cinzel font-bold text-amber-500/80 uppercase tracking-widest mb-2">
              Повторите Код *
            </label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-3 bg-black/40 border border-purple-900/50 rounded focus:outline-none focus:border-amber-500/50 focus:bg-purple-950/20 text-gray-200 placeholder-gray-600 font-mono transition-all shadow-inner"
              placeholder="••••••••"
              disabled={loading}
              required
            />
          </div>

          <div>
            <label className="block text-xs font-cinzel font-bold text-amber-500/80 uppercase tracking-widest mb-3">Выберите Путь *</label>
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => setRole("freelancer")}
                className={`p-4 rounded border transition-all ${
                  role === "freelancer"
                    ? "border-amber-500 bg-amber-950/30 shadow-[0_0_15px_rgba(217,119,6,0.3)] filter brightness-110"
                    : "border-gray-800 bg-black/40 hover:border-gray-600 grayscale opacity-70"
                }`}
              >
                <div className="text-3xl mb-2 drop-shadow-md">⚔️</div>
                <div className="font-cinzel font-bold text-sm tracking-widest text-amber-100">Наёмник</div>
                <div className="font-inter text-[10px] text-gray-400 mt-1 uppercase">Выполнять квесты</div>
              </button>
              <button
                type="button"
                onClick={() => setRole("client")}
                className={`p-4 rounded border transition-all ${
                  role === "client"
                    ? "border-purple-500 bg-purple-950/30 shadow-[0_0_15px_rgba(168,85,247,0.3)] filter brightness-110"
                    : "border-gray-800 bg-black/40 hover:border-gray-600 grayscale opacity-70"
                }`}
              >
                <div className="text-3xl mb-2 drop-shadow-md">📜</div>
                <div className="font-cinzel font-bold text-sm tracking-widest text-purple-100">Заказчик</div>
                <div className="font-inter text-[10px] text-gray-400 mt-1 uppercase">Создавать контракты</div>
              </button>
            </div>
          </div>

          <Button type="submit" variant="primary" className="w-full py-4 mt-4" disabled={loading}>
            {loading ? "Призыв..." : "Подписать Контракт"}
          </Button>
        </form>

        <div className="mt-8 text-center text-sm font-inter text-gray-400 border-t border-gray-800/50 pt-6">
          Уже состоите в рядах?{" "}
          <Link href="/auth/login" className="text-amber-500 hover:text-amber-400 font-bold hover:underline underline-offset-4 decoration-amber-500/30">
            Войти во Врата
          </Link>
        </div>
      </Card>
    </main>
  );
}
