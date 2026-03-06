/**
 * Дашборд клиента — сводка активности
 *
 * Маршрут: /profile/dashboard
 * - Только для role=client
 * - Сводка: активные квесты, бюджет, статистика
 */

"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { getQuests, Quest } from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import QuestStatusBadge from "@/components/quests/QuestStatusBadge";
import {
  LayoutDashboard,
  TrendingUp,
  Wallet,
  Clock,
  CheckCircle2,
  BarChart3,
  Scroll,
  AlertTriangle,
} from "lucide-react";

function formatMoney(n: number): string {
  return n.toLocaleString("ru-RU") + "₽";
}

function StatBox({
  icon,
  label,
  value,
  sub,
  color = "text-amber-400",
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="rpg-card p-5 flex flex-col items-center text-center gap-1.5">
      <div className={`${color}`}>{icon}</div>
      <span className={`text-2xl font-cinzel font-bold ${color}`}>{value}</span>
      <span className="text-xs text-gray-400 uppercase tracking-wider">{label}</span>
      {sub && <span className="text-[10px] text-gray-500">{sub}</span>}
    </div>
  );
}

export default function ClientDashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [quests, setQuests] = useState<Quest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && (!isAuthenticated || user?.role !== "client")) {
      router.push("/profile");
    }
  }, [authLoading, isAuthenticated, user, router]);

  const loadData = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      // Fetch all client quests (up to 200)
      const res = await getQuests(1, 200);
      const mine = res.quests.filter((q) => q.client_id === user.id);
      setQuests(mine);
    } catch {
      setError("Не удалось загрузить данные");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const stats = useMemo(() => {
    const open = quests.filter((q) => q.status === "open");
    const inProgress = quests.filter((q) => q.status === "in_progress");
    const confirmed = quests.filter((q) => q.status === "confirmed");
    const completed = quests.filter((q) => q.status === "completed");
    const cancelled = quests.filter((q) => q.status === "cancelled");

    const totalSpent = confirmed.reduce((s, q) => s + q.budget, 0);
    const activeCount = open.length + inProgress.length + completed.length;

    // Average completion time (confirmed quests with created_at)
    let avgDays = 0;
    if (confirmed.length > 0) {
      const totalMs = confirmed.reduce((sum, q) => {
        const start = new Date(q.created_at).getTime();
        const end = Date.now(); // approximate
        return sum + (end - start);
      }, 0);
      avgDays = Math.round(totalMs / confirmed.length / 86400000);
    }

    return {
      total: quests.length,
      active: activeCount,
      open,
      inProgress,
      completed,
      confirmed,
      cancelled,
      totalSpent,
      avgDays,
    };
  }, [quests]);

  if (authLoading || loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-8 max-w-5xl">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="rpg-card p-5 h-28 animate-pulse" />
            ))}
          </div>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-8 max-w-5xl">
          <Card className="p-8 text-center">
            <AlertTriangle className="mx-auto mb-3 text-red-400" size={40} />
            <p className="text-red-400 mb-4">{error}</p>
            <Button onClick={loadData} variant="secondary">🔄 Повторить</Button>
          </Card>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />

      <div className="container mx-auto px-4 py-8 max-w-5xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          {/* Header */}
          <div className="flex items-center justify-between flex-wrap gap-4">
            <h1 className="text-2xl md:text-3xl font-cinzel font-bold text-gray-100 flex items-center gap-3">
              <LayoutDashboard className="text-amber-500" size={28} /> Дашборд
            </h1>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => router.push("/profile")}>
                ← Профиль
              </Button>
              <Button variant="primary" onClick={() => router.push("/quests/create")}>
                ➕ Новый квест
              </Button>
            </div>
          </div>

          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatBox
              icon={<Scroll size={24} />}
              label="Всего квестов"
              value={stats.total}
              color="text-purple-400"
            />
            <StatBox
              icon={<Clock size={24} />}
              label="Активные"
              value={stats.active}
              sub={`${stats.open.length} открыт · ${stats.inProgress.length} в работе`}
              color="text-blue-400"
            />
            <StatBox
              icon={<Wallet size={24} />}
              label="Потрачено"
              value={formatMoney(stats.totalSpent)}
              color="text-amber-400"
            />
            <StatBox
              icon={<TrendingUp size={24} />}
              label="Завершено"
              value={stats.confirmed.length}
              sub={stats.avgDays > 0 ? `~${stats.avgDays} дн. в среднем` : undefined}
              color="text-emerald-400"
            />
          </div>

          {/* Active quests */}
          <section className="rpg-card p-6">
            <h3 className="text-lg font-cinzel text-amber-500 mb-4 flex items-center gap-2 border-b border-amber-900/30 pb-2">
              <BarChart3 size={20} className="text-amber-500" /> Активные квесты
            </h3>

            {stats.active === 0 ? (
              <div className="text-center py-8">
                <Scroll className="mx-auto mb-2 text-gray-600" size={32} />
                <p className="text-sm text-gray-500 mb-3">Нет активных квестов</p>
                <Button variant="primary" onClick={() => router.push("/quests/create")}>
                  ➕ Создать квест
                </Button>
              </div>
            ) : (
              <ul className="divide-y divide-gray-800/60">
                {[...stats.open, ...stats.inProgress, ...stats.completed]
                  .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                  .slice(0, 10)
                  .map((q) => (
                    <li key={q.id}>
                      <Link
                        href={`/quests/${q.id}`}
                        className="flex items-center gap-3 py-3 px-1 hover:bg-white/[0.02] rounded transition-colors"
                      >
                        <QuestStatusBadge status={q.status} size="sm" />
                        <span className="flex-1 min-w-0 truncate text-sm text-gray-300">
                          {q.title}
                        </span>
                        <span className="text-xs text-amber-400 font-mono shrink-0">
                          {formatMoney(q.budget)}
                        </span>
                        <span className="text-xs text-gray-500 shrink-0">
                          {q.applications.length} откл.
                        </span>
                      </Link>
                    </li>
                  ))}
              </ul>
            )}
          </section>

          {/* Confirmed history */}
          {stats.confirmed.length > 0 && (
            <section className="rpg-card p-6">
              <h3 className="text-lg font-cinzel text-amber-500 mb-4 flex items-center gap-2 border-b border-amber-900/30 pb-2">
                <CheckCircle2 size={20} className="text-emerald-400" /> Завершённые
              </h3>
              <ul className="divide-y divide-gray-800/60">
                {stats.confirmed.slice(0, 5).map((q) => (
                  <li key={q.id}>
                    <Link
                      href={`/quests/${q.id}`}
                      className="flex items-center gap-3 py-2.5 px-1 hover:bg-white/[0.02] rounded transition-colors"
                    >
                      <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
                      <span className="flex-1 min-w-0 truncate text-sm text-gray-300">{q.title}</span>
                      <span className="text-xs text-amber-400 font-mono shrink-0">{formatMoney(q.budget)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </motion.div>
      </div>
    </main>
  );
}
