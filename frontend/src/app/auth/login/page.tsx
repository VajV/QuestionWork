/**
 * Страница входа в систему
 */

"use client";

import { useState, FormEvent, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated } = useAuth();
  
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  // Detect ?expired=1 in URL — avoids useSearchParams Suspense requirement
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      setSessionExpired(params.get("expired") === "1");
    }
  }, []);

  // Редирект если уже авторизован
  useEffect(() => {
    if (isAuthenticated) {
      router.push("/profile");
    }
  }, [isAuthenticated, router]);

  if (isAuthenticated) {
    return null;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    if (!username.trim() || !password.trim()) {
      setError("Заполните все поля");
      setLoading(false);
      return;
    }

    const result = await login({ username: username.trim(), password });

    if (result.success) {
      router.push("/profile");
    } else {
      setError(result.error || "Не удалось войти");
    }

    setLoading(false);
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 flex items-center justify-center px-4">
      <Card className="w-full max-w-md p-8">
        <div className="text-center mb-8 relative">
          <Link href="/" className="text-3xl font-cinzel font-bold tracking-widest flex justify-center items-center gap-2 group">
            <span className="text-amber-500 drop-shadow-[0_0_8px_rgba(217,119,6,0.5)] group-hover:text-amber-400 transition-colors">⚡ Question</span>
            <span className="text-gray-300">Work</span>
          </Link>
          <div className="divider-ornament my-6"></div>
          <h1 className="text-2xl font-cinzel font-bold mt-4 text-purple-200">Врата Гильдии</h1>
          <p className="text-gray-400 font-inter mt-2 text-sm">Представьтесь, чтобы войти.</p>
        </div>

        {sessionExpired && !error && (
          <div className="mb-6 p-4 bg-amber-950/40 border border-amber-500/50 rounded text-amber-300 text-sm flex items-start gap-3 shadow-[0_0_10px_rgba(217,119,6,0.2)]">
            <span className="text-lg">⏳</span>
            <span className="flex-1 font-mono">
              Магическая связь прервана — заклинание требует обновления.
            </span>
            <button
              className="opacity-60 hover:opacity-100 transition-opacity"
              onClick={() => setSessionExpired(false)}
              aria-label="Закрыть"
            >
              ✕
            </button>
          </div>
        )}

        {error && (
          <div className="mb-6 p-4 bg-red-950/40 border border-red-800/50 rounded text-red-300 font-mono text-sm shadow-[0_0_10px_rgba(220,38,38,0.2)]">
            💀 {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="username" className="block text-xs font-cinzel font-bold text-amber-500/80 uppercase tracking-widest mb-2">
              Имя Героя
            </label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 bg-black/40 border border-purple-900/50 rounded focus:outline-none focus:border-amber-500/50 focus:bg-purple-950/20 text-gray-200 placeholder-gray-600 font-mono transition-all shadow-inner"
              placeholder="novice_dev"
              autoComplete="username"
              disabled={loading}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-cinzel font-bold text-amber-500/80 uppercase tracking-widest mb-2">
              Секретный Код
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 bg-black/40 border border-purple-900/50 rounded focus:outline-none focus:border-amber-500/50 focus:bg-purple-950/20 text-gray-200 placeholder-gray-600 font-mono transition-all shadow-inner"
              placeholder="••••••••"
              autoComplete="current-password"
              disabled={loading}
            />
          </div>

          <Button
            type="submit"
            variant="primary"
            className="w-full py-3"
            disabled={loading}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-5 w-5 text-amber-400" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Соединение...
              </span>
            ) : (
              "Войти в Игру"
            )}
          </Button>
        </form>

        <div className="mt-8 text-center text-sm font-inter text-gray-400 border-t border-gray-800/50 pt-6">
          Ещё не состоите в Гильдии?{" "}
          <Link href="/auth/register" className="text-amber-500 hover:text-amber-400 font-bold hover:underline underline-offset-4 decoration-amber-500/30">
            Пройти Инициацию
          </Link>
        </div>

        {process.env.NODE_ENV === "development" && (
          <div className="mt-8 p-4 bg-gray-900/50 rounded border border-gray-800 border-dashed">
            <p className="text-xs font-cinzel text-gray-500 mb-2 uppercase">📝 Магические шпаргалки (Dev):</p>
            <div className="text-xs text-gray-400 space-y-1 font-mono">
              <div>Username: <span className="text-purple-400">novice_dev</span></div>
              <div>Password: <span className="text-purple-400">password123</span></div>
            </div>
          </div>
        )}
      </Card>
    </main>
  );
}
