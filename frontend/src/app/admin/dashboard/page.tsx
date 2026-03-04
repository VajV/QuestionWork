"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users,
  ScrollText,
  Wallet,
  TrendingUp,
  Activity,
  Trash2,
  ArrowRight,
  AlertCircle,
  ShieldBan,
  DollarSign,
  CalendarPlus,
  Megaphone,
  Clock,
  Send,
  CheckCircle2,
} from "lucide-react";
import {
  adminGetPlatformStats,
  adminGetPendingWithdrawals,
  adminGetLogs,
  adminCleanupNotifications,
  adminBroadcastNotification,
} from "@/lib/api";
import type {
  AdminPlatformStats,
  AdminTransactionsResponse,
  AdminTransaction,
  AdminLogEntry,
} from "@/types";

interface StatCard {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
  sub?: string;
}

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.07, duration: 0.4 },
  }),
};

const ACTION_LABELS: Record<string, string> = {
  update_user: "Обновил пользователя",
  ban_user: "Заблокировал",
  unban_user: "Разблокировал",
  delete_user: "Удалил пользователя",
  grant_xp: "Начислил XP",
  adjust_wallet: "Изменил баланс",
  grant_badge: "Выдал бейдж",
  revoke_badge: "Отозвал бейдж",
  change_class: "Сменил класс",
  update_quest: "Обновил квест",
  force_cancel_quest: "Отменил квест",
  force_complete_quest: "Завершил квест",
  delete_quest: "Удалил квест",
  broadcast_notification: "Рассылка",
  cleanup_notifications: "Очистка уведомлений",
};

export default function AdminDashboard() {
  const [stats, setStats] = useState<AdminPlatformStats | null>(null);
  const [pendingData, setPendingData] =
    useState<AdminTransactionsResponse | null>(null);
  const [recentLogs, setRecentLogs] = useState<AdminLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Cleanup
  const [cleanupMsg, setCleanupMsg] = useState<string | null>(null);
  const [cleanupLoading, setCleanupLoading] = useState(false);

  // Broadcast
  const [bcTitle, setBcTitle] = useState("");
  const [bcMessage, setBcMessage] = useState("");
  const [bcUserIds, setBcUserIds] = useState("");
  const [bcLoading, setBcLoading] = useState(false);
  const [bcResult, setBcResult] = useState<string | null>(null);

  const reload = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, p, logs] = await Promise.all([
        adminGetPlatformStats(),
        adminGetPendingWithdrawals(1, 10),
        adminGetLogs(1, 8),
      ]);
      setStats(s);
      setPendingData(p);
      setRecentLogs(logs.logs ?? []);
    } catch {
      setError("Не удалось загрузить данные. Проверьте права доступа.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  const handleCleanup = async () => {
    setCleanupLoading(true);
    setCleanupMsg(null);
    try {
      const r = await adminCleanupNotifications();
      setCleanupMsg(r.message);
    } catch {
      setCleanupMsg("Ошибка при очистке уведомлений.");
    } finally {
      setCleanupLoading(false);
    }
  };

  const handleBroadcast = async () => {
    if (!bcTitle.trim() || !bcMessage.trim()) return;
    setBcLoading(true);
    setBcResult(null);
    try {
      const ids = bcUserIds
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const r = await adminBroadcastNotification(
        ids,
        bcTitle.trim(),
        bcMessage.trim(),
      );
      setBcResult(`Отправлено ${r.sent} из ${r.total_recipients} получателей`);
      setBcTitle("");
      setBcMessage("");
      setBcUserIds("");
      reload();
    } catch {
      setBcResult("Ошибка при отправке рассылки.");
    } finally {
      setBcLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-cinzel font-bold text-white">Дашборд</h1>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="h-28 rounded-2xl bg-gray-900/60 border border-white/5 animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-cinzel font-bold text-white">Дашборд</h1>
        <div className="bg-red-900/20 border border-red-500/30 rounded-2xl p-6 flex items-center gap-3">
          <AlertCircle className="text-red-400 shrink-0" size={22} />
          <p className="text-red-300">{error}</p>
        </div>
      </div>
    );
  }

  const statCards: StatCard[] = [
    {
      label: "Всего пользователей",
      value: stats?.total_users ?? 0,
      icon: <Users size={22} />,
      color: "text-blue-400",
      sub: "зарегистрировано",
    },
    {
      label: "Всего квестов",
      value: stats?.total_quests ?? 0,
      icon: <ScrollText size={22} />,
      color: "text-emerald-400",
      sub: "создано",
    },
    {
      label: "Транзакций",
      value: stats?.total_transactions ?? 0,
      icon: <Activity size={22} />,
      color: "text-cyan-400",
      sub: "за всё время",
    },
    {
      label: "Ожидают вывода",
      value: stats?.pending_withdrawals ?? 0,
      icon: <Wallet size={22} />,
      color: stats?.pending_withdrawals ? "text-yellow-400" : "text-gray-400",
      sub: stats?.pending_withdrawals ? "требуют рассмотрения" : "всё обработано",
    },
    {
      label: "Выручка платформы",
      value: `${(stats?.total_revenue ?? 0).toLocaleString("ru")} ₽`,
      icon: <DollarSign size={22} />,
      color: "text-green-400",
      sub: "общий доход",
    },
    {
      label: "Забанено",
      value: stats?.banned_users ?? 0,
      icon: <ShieldBan size={22} />,
      color: stats?.banned_users ? "text-red-400" : "text-gray-400",
      sub: stats?.banned_users ? "заблокировано" : "нет блокировок",
    },
    {
      label: "Новых за сегодня",
      value: stats?.users_today ?? 0,
      icon: <CalendarPlus size={22} />,
      color: "text-purple-400",
      sub: "пользователей",
    },
    {
      label: "Квестов за сегодня",
      value: stats?.quests_today ?? 0,
      icon: <CalendarPlus size={22} />,
      color: "text-amber-400",
      sub: "создано",
    },
  ];

  const pendingTxs = pendingData?.transactions ?? [];

  // Breakdown helpers
  const roleEntries = stats?.users_by_role
    ? Object.entries(stats.users_by_role)
    : [];
  const statusEntries = stats?.quests_by_status
    ? Object.entries(stats.quests_by_status)
    : [];

  return (
    <div className="space-y-8">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-cinzel font-bold text-white">Дашборд</h1>
        <p className="text-gray-500 text-sm mt-1">
          Обзор состояния платформы — God Mode
        </p>
      </div>

      {/* Stat cards — 4 cols */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((s, i) => (
          <motion.div
            key={s.label}
            custom={i}
            variants={fadeUp}
            initial="hidden"
            animate="show"
            className="bg-gray-900/60 backdrop-blur-md border border-white/10 rounded-2xl p-5 shadow-2xl"
          >
            <div className="flex items-center justify-between mb-3">
              <span className={`${s.color}`}>{s.icon}</span>
              <TrendingUp size={14} className="text-gray-600" />
            </div>
            <div className="text-2xl font-bold text-white font-mono">
              {s.value}
            </div>
            <div className="text-xs text-gray-400 mt-1">{s.label}</div>
            {s.sub && (
              <div className="text-[10px] text-gray-600 mt-0.5">{s.sub}</div>
            )}
          </motion.div>
        ))}
      </div>

      {/* Breakdowns row */}
      {(roleEntries.length > 0 || statusEntries.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Users by role */}
          {roleEntries.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="bg-gray-900/60 backdrop-blur-md border border-white/10 rounded-2xl p-6 shadow-2xl"
            >
              <h2 className="text-sm font-cinzel font-bold text-white mb-3">
                Пользователи по ролям
              </h2>
              <div className="space-y-2">
                {roleEntries.map(([role, count]) => (
                  <div
                    key={role}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-gray-400 capitalize">{role}</span>
                    <span className="font-mono text-white">{count}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* Quests by status */}
          {statusEntries.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 }}
              className="bg-gray-900/60 backdrop-blur-md border border-white/10 rounded-2xl p-6 shadow-2xl"
            >
              <h2 className="text-sm font-cinzel font-bold text-white mb-3">
                Квесты по статусам
              </h2>
              <div className="space-y-2">
                {statusEntries.map(([status, count]) => (
                  <div
                    key={status}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="text-gray-400 capitalize">{status}</span>
                    <span className="font-mono text-white">{count}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </div>
      )}

      {/* Quick actions + pending withdrawals */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quick actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-gray-900/60 backdrop-blur-md border border-white/10 rounded-2xl p-6 shadow-2xl"
        >
          <h2 className="text-lg font-cinzel font-bold text-white mb-4">
            Быстрые действия
          </h2>
          <div className="space-y-3">
            <Link
              href="/admin/users"
              className="flex items-center justify-between p-3 rounded-lg bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 transition-colors group"
            >
              <span className="flex items-center gap-3 text-sm text-gray-300">
                <Users size={16} className="text-blue-400" />
                Управление пользователями
              </span>
              <ArrowRight
                size={14}
                className="text-gray-600 group-hover:text-white transition-colors"
              />
            </Link>
            <Link
              href="/admin/withdrawals"
              className="flex items-center justify-between p-3 rounded-lg bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 transition-colors group"
            >
              <span className="flex items-center gap-3 text-sm text-gray-300">
                <Wallet size={16} className="text-yellow-400" />
                Обработать выводы
                {(stats?.pending_withdrawals ?? 0) > 0 && (
                  <span className="bg-yellow-500/20 text-yellow-400 text-xs px-2 py-0.5 rounded-full font-mono">
                    {stats!.pending_withdrawals}
                  </span>
                )}
              </span>
              <ArrowRight
                size={14}
                className="text-gray-600 group-hover:text-white transition-colors"
              />
            </Link>
            <Link
              href="/admin/quests"
              className="flex items-center justify-between p-3 rounded-lg bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 transition-colors group"
            >
              <span className="flex items-center gap-3 text-sm text-gray-300">
                <ScrollText size={16} className="text-emerald-400" />
                Управление квестами
              </span>
              <ArrowRight
                size={14}
                className="text-gray-600 group-hover:text-white transition-colors"
              />
            </Link>
            <Link
              href="/admin/logs"
              className="flex items-center justify-between p-3 rounded-lg bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 transition-colors group"
            >
              <span className="flex items-center gap-3 text-sm text-gray-300">
                <Clock size={16} className="text-purple-400" />
                Журнал действий
              </span>
              <ArrowRight
                size={14}
                className="text-gray-600 group-hover:text-white transition-colors"
              />
            </Link>
            <button
              onClick={handleCleanup}
              disabled={cleanupLoading}
              className="w-full flex items-center justify-between p-3 rounded-lg bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 transition-colors group disabled:opacity-50"
            >
              <span className="flex items-center gap-3 text-sm text-gray-300">
                <Trash2 size={16} className="text-red-400" />
                {cleanupLoading
                  ? "Очистка..."
                  : "Очистить старые уведомления"}
              </span>
            </button>
            {cleanupMsg && (
              <p className="text-xs text-gray-400 pl-9">{cleanupMsg}</p>
            )}
          </div>
        </motion.div>

        {/* Pending withdrawals */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-gray-900/60 backdrop-blur-md border border-white/10 rounded-2xl p-6 shadow-2xl"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-cinzel font-bold text-white">
              Ожидающие вывода
            </h2>
            {pendingTxs.length > 0 && (
              <Link
                href="/admin/withdrawals"
                className="text-xs text-purple-400 hover:text-purple-300"
              >
                Все →
              </Link>
            )}
          </div>

          {pendingTxs.length === 0 ? (
            <div className="text-center py-8">
              <Wallet size={32} className="mx-auto text-gray-700 mb-2" />
              <p className="text-gray-500 text-sm">
                Нет ожидающих выводов
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {pendingTxs.slice(0, 5).map((tx: AdminTransaction) => (
                <div
                  key={tx.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-gray-800/40 border border-gray-700/30"
                >
                  <div>
                    <span className="text-sm text-gray-300 font-mono">
                      {tx.user_id.slice(0, 12)}...
                    </span>
                    <span className="text-xs text-gray-500 ml-2">
                      {new Date(tx.created_at).toLocaleDateString("ru")}
                    </span>
                  </div>
                  <span className="text-sm font-mono font-bold text-yellow-400">
                    {tx.amount} {tx.currency}
                  </span>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      </div>

      {/* Broadcast + recent logs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Broadcast notification form */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
          className="bg-gray-900/60 backdrop-blur-md border border-white/10 rounded-2xl p-6 shadow-2xl"
        >
          <h2 className="text-lg font-cinzel font-bold text-white mb-4 flex items-center gap-2">
            <Megaphone size={18} className="text-orange-400" />
            Рассылка уведомлений
          </h2>

          <div className="space-y-3">
            <input
              type="text"
              value={bcTitle}
              onChange={(e) => setBcTitle(e.target.value)}
              placeholder="Заголовок"
              className="w-full bg-gray-800/60 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-purple-500/50"
            />
            <textarea
              value={bcMessage}
              onChange={(e) => setBcMessage(e.target.value)}
              placeholder="Текст сообщения"
              rows={3}
              className="w-full bg-gray-800/60 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-purple-500/50 resize-none"
            />
            <input
              type="text"
              value={bcUserIds}
              onChange={(e) => setBcUserIds(e.target.value)}
              placeholder="User IDs через запятую (пусто = всем)"
              className="w-full bg-gray-800/60 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-purple-500/50"
            />
            <button
              onClick={handleBroadcast}
              disabled={bcLoading || !bcTitle.trim() || !bcMessage.trim()}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium transition-colors disabled:opacity-40"
            >
              <Send size={14} />
              {bcLoading ? "Отправка..." : "Отправить"}
            </button>

            <AnimatePresence>
              {bcResult && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="flex items-center gap-2 text-xs text-emerald-400"
                >
                  <CheckCircle2 size={14} />
                  {bcResult}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {/* Recent admin actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="bg-gray-900/60 backdrop-blur-md border border-white/10 rounded-2xl p-6 shadow-2xl"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-cinzel font-bold text-white flex items-center gap-2">
              <Clock size={18} className="text-purple-400" />
              Последние действия
            </h2>
            <Link
              href="/admin/logs"
              className="text-xs text-purple-400 hover:text-purple-300"
            >
              Все →
            </Link>
          </div>

          {recentLogs.length === 0 ? (
            <div className="text-center py-8">
              <Clock size={32} className="mx-auto text-gray-700 mb-2" />
              <p className="text-gray-500 text-sm">Нет записей</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {recentLogs.map((log) => (
                <div
                  key={log.id}
                  className="p-2.5 rounded-lg bg-gray-800/40 border border-gray-700/30"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-300">
                      {ACTION_LABELS[log.action] || log.action}
                    </span>
                    <span className="text-[10px] text-gray-600 font-mono">
                      {new Date(log.created_at).toLocaleString("ru", {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <div className="text-[10px] text-gray-500 mt-0.5">
                    {log.target_type} · {log.target_id.slice(0, 12)}...
                  </div>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
