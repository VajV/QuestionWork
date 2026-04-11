"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { motion } from "@/lib/motion";
import { useRouter } from "next/navigation";
import Header from "@/components/layout/Header";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import SeasonFactionRail from "@/components/ui/SeasonFactionRail";
import WorldPanel from "@/components/ui/WorldPanel";
import { useAuth } from "@/context/AuthContext";
import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  getNotificationPreferences,
  updateNotificationPreferences,
  type Notification,
  type NotificationPreferences,
  getApiErrorMessage,
} from "@/lib/api";

type FilterMode = "all" | "unread";

function formatGroupLabel(dateKey: string): string {
  const date = new Date(dateKey);
  const today = new Date();
  const todayKey = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  const targetKey = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const diffDays = Math.round((todayKey - targetKey) / 86_400_000);

  if (diffDays === 0) return "Сегодня";
  if (diffDays === 1) return "Вчера";
  return date.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

export default function NotificationsPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterMode>("all");
  const [markingAll, setMarkingAll] = useState(false);
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [prefsSaving, setPrefsSaving] = useState(false);

  const groupedItems = useMemo(() => {
    const groups = new Map<string, Notification[]>();
    for (const item of items) {
      const groupKey = new Date(item.created_at).toISOString().slice(0, 10);
      const bucket = groups.get(groupKey) ?? [];
      bucket.push(item);
      groups.set(groupKey, bucket);
    }
    return Array.from(groups.entries()).map(([date, notifications]) => ({
      date,
      label: formatGroupLabel(date),
      notifications,
    }));
  }, [items]);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [authLoading, isAuthenticated, router]);

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getNotifications(100, 0, filter === "unread");
      setItems(response.notifications);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Не удалось загрузить уведомления"));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    if (isAuthenticated) {
      loadNotifications();
      getNotificationPreferences().then(setPrefs).catch(() => {/* non-blocking */});
    }
  }, [isAuthenticated, loadNotifications]);

  const handleMarkRead = async (notificationId: string) => {
    try {
      await markNotificationRead(notificationId);
      setItems((prev) =>
        prev.map((item) =>
          item.id === notificationId ? { ...item, is_read: true } : item,
        ),
      );
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Не удалось отметить уведомление"));
    }
  };

  const handleMarkAllRead = async () => {
    setMarkingAll(true);
    setError(null);
    try {
      await markAllNotificationsRead();
      setItems((prev) => prev.map((item) => ({ ...item, is_read: true })));
      loadNotifications();
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Не удалось отметить все уведомления"));
    } finally {
      setMarkingAll(false);
    }
  };

  const handlePrefToggle = async (key: keyof NotificationPreferences) => {
    if (!prefs) return;
    const updated = { ...prefs, [key]: !prefs[key] };
    setPrefs(updated);
    setPrefsSaving(true);
    try {
      await updateNotificationPreferences(updated);
    } catch (e) {
      console.warn("Preference update failed, reverting", e);
      setPrefs(prefs); // revert on failure
    } finally {
      setPrefsSaving(false);
    }
  };

  if (authLoading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-950 via-purple-950/20 to-gray-950 text-gray-100">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto rounded-2xl border border-gray-800 bg-gray-900/60 p-10 text-center">
            <div className="mx-auto mb-4 h-12 w-12 rounded-full border-4 border-amber-500 border-t-transparent animate-spin" />
            <p className="text-gray-400">Проверка сессии...</p>
          </div>
        </div>
      </main>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-950 via-purple-950/20 to-gray-950 text-gray-100">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto rounded-2xl border border-gray-800 bg-gray-900/60 p-10 text-center">
            <div className="mx-auto mb-4 h-12 w-12 rounded-full border-4 border-amber-500 border-t-transparent animate-spin" />
            <p className="text-gray-400">Загружаем уведомления...</p>
          </div>
        </div>
      </main>
    );
  }

  const unreadCount = items.filter((item) => !item.is_read).length;

  return (
    <main className="guild-world-shell min-h-screen bg-gradient-to-br from-gray-950 via-purple-950/20 to-gray-950 text-gray-100">
      <Header />

      <div className="container mx-auto px-4 py-8">
        <div className="mx-auto max-w-4xl space-y-6">
          <GuildStatusStrip
            mode="guild"
            eyebrow="Event relay"
            title="Уведомления стали частью общего relay-слоя гильдии"
            description="Системные сигналы, ответы по квестам и кошелёк теперь читаются как единый событийный поток с приоритетами и режимами обзора."
            stats={[
              { label: "Events", value: items.length, note: "в текущей выборке", tone: "purple" },
              { label: "Unread", value: unreadCount, note: "ждут внимания", tone: unreadCount > 0 ? "amber" : "slate" },
              { label: "Days", value: groupedItems.length, note: "группы по датам", tone: "cyan" },
              { label: "View", value: filter === "all" ? "ALL" : "UNREAD", note: "режим потока", tone: "emerald" },
            ]}
            signals={[
              { label: filter === "all" ? "full relay" : "triage mode", tone: filter === "all" ? "purple" : "amber" },
              { label: markingAll ? "bulk clean in progress" : "manual control", tone: markingAll ? "cyan" : "slate" },
            ]}
          />

          <SeasonFactionRail mode="notifications" unreadCount={unreadCount} />

          <WorldPanel
            eyebrow="Signal routing"
            title="Фильтры и массовые действия переведены в единый command block"
            description="Блоки выше унифицируют уведомления с остальными внутренними разделами, поэтому страница больше не выглядит инородной относительно profile и quests."
            tone="purple"
            compact
          />

          <div className="flex flex-col gap-4 rounded-2xl border border-gray-800 bg-gray-900/60 p-6 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-amber-500/80">Центр уведомлений</p>
              <h1 className="mt-2 text-3xl font-bold text-white">События гильдии</h1>
              <p className="mt-2 text-sm text-gray-400">
                Все системные события, ответы по квестам и действия администрации в одном месте.
              </p>
            </div>

            <motion.div layout className="flex flex-wrap items-center gap-3" role="tablist" onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                e.preventDefault();
                setFilter((prev) => (prev === "all" ? "unread" : "all"));
              }
            }}>
              <motion.button
                type="button"
                role="tab"
                aria-selected={filter === "all"}
                tabIndex={filter === "all" ? 0 : -1}
                onClick={() => setFilter("all")}
                whileTap={{ scale: 0.98 }}
                className={`rounded-lg border px-4 py-2 text-sm transition-colors ${
                  filter === "all"
                    ? "border-amber-500/50 bg-amber-900/30 text-amber-300"
                    : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200"
                }`}
              >
                Все
              </motion.button>
              <motion.button
                type="button"
                role="tab"
                aria-selected={filter === "unread"}
                tabIndex={filter === "unread" ? 0 : -1}
                onClick={() => setFilter("unread")}
                whileTap={{ scale: 0.98 }}
                className={`rounded-lg border px-4 py-2 text-sm transition-colors ${
                  filter === "unread"
                    ? "border-amber-500/50 bg-amber-900/30 text-amber-300"
                    : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200"
                }`}
              >
                Непрочитанные {unreadCount > 0 ? `(${unreadCount})` : ""}
              </motion.button>
              <motion.button
                type="button"
                onClick={handleMarkAllRead}
                disabled={markingAll || unreadCount === 0}
                whileTap={{ scale: 0.98 }}
                className="rounded-lg border border-purple-500/40 bg-purple-900/20 px-4 py-2 text-sm text-purple-300 transition-colors hover:bg-purple-800/30 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {markingAll ? "Отмечаем..." : "Прочитать все"}
              </motion.button>
            </motion.div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
              <div className="text-[11px] uppercase tracking-[0.25em] text-gray-500">Всего событий</div>
              <div className="mt-2 text-3xl font-bold text-white">{items.length}</div>
              <div className="mt-1 text-xs text-gray-400">Сообщения в текущей выборке</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
              <div className="text-[11px] uppercase tracking-[0.25em] text-gray-500">Непрочитанные</div>
              <div className="mt-2 text-3xl font-bold text-amber-300">{unreadCount}</div>
              <div className="mt-1 text-xs text-gray-400">Требуют вашего внимания</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
              <div className="text-[11px] uppercase tracking-[0.25em] text-gray-500">Режим просмотра</div>
              <div className="mt-2 text-3xl font-bold text-purple-300">{filter === "all" ? "Все" : "Unread"}</div>
              <div className="mt-1 text-xs text-gray-400">Переключайте поток уведомлений</div>
            </div>
          </div>

          {error && (
            <div className="rounded-2xl border border-red-500/30 bg-red-950/20 p-4">
              <p className="text-sm text-red-300">{error}</p>
              <button
                type="button"
                onClick={loadNotifications}
                className="mt-2 text-xs text-amber-400 hover:underline"
              >
                Повторить
              </button>
            </div>
          )}

          {!error && items.length === 0 && (
            <div className="rounded-2xl border border-gray-800 bg-gray-900/60 p-10 text-center">
              <div className="mb-4 text-5xl">🔔</div>
              <h2 className="text-xl font-semibold text-white">Уведомлений пока нет</h2>
              <p className="mt-2 text-sm text-gray-400">
                Когда появятся новые события по квестам, кошельку или классу, они будут видны здесь.
              </p>
              <Link href="/quests" className="mt-4 inline-flex text-sm text-amber-400 hover:underline">
                Перейти к доске заданий
              </Link>
            </div>
          )}

          {items.length > 0 && (
            <div className="space-y-6">
              {groupedItems.map((group) => (
                <section key={group.date} className="space-y-3">
                  <div className="flex items-center gap-3">
                    <h2 className="text-sm font-cinzel uppercase tracking-[0.25em] text-amber-400/80">{group.label}</h2>
                    <div className="h-px flex-1 bg-gradient-to-r from-amber-500/20 to-transparent" />
                  </div>

                  {group.notifications.map((item, index) => (
                    <motion.article
                      key={item.id}
                      initial={{ opacity: 0, y: 12 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true, amount: 0.2 }}
                      transition={{ duration: 0.24, delay: index * 0.03, ease: "easeOut" }}
                      className={`rounded-2xl border p-5 ${
                        item.is_read
                          ? "border-gray-800 bg-gray-900/60"
                          : "border-amber-500/30 bg-amber-950/10"
                      }`}
                    >
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <h2 className="text-lg font-semibold text-white">{item.title}</h2>
                            {!item.is_read && (
                              <span className="inline-flex rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] uppercase tracking-wider text-amber-300">
                                Новое
                              </span>
                            )}
                            <span className="inline-flex rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wider text-gray-400">
                              {item.event_type}
                            </span>
                          </div>
                          <p className="text-sm leading-relaxed text-gray-300">{item.message}</p>
                          <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                            <span>{new Date(item.created_at).toLocaleString("ru-RU")}</span>
                          </div>
                        </div>

                        {!item.is_read && (
                          <button
                            type="button"
                            onClick={() => handleMarkRead(item.id)}
                            className="rounded-lg border border-amber-500/40 px-3 py-2 text-sm text-amber-300 transition-colors hover:bg-amber-900/20"
                          >
                            Отметить прочитанным
                          </button>
                        )}
                      </div>
                    </motion.article>
                  ))}
                </section>
              ))}
            </div>
          )}

          {/* Notification preferences */}
          {prefs && (
            <div className="rounded-2xl border border-gray-800 bg-gray-900/60 p-6">
              <h2 className="mb-4 text-sm font-cinzel uppercase tracking-widest text-purple-400">
                Настройки уведомлений {prefsSaving ? "(сохраняем…)" : ""}
              </h2>
              <div className="space-y-3 text-sm">
                {(
                  [
                    { key: "transactional_enabled", label: "Транзакционные (квесты, кошелёк, назначения)" },
                    { key: "growth_enabled", label: "Рост и геймификация (XP, уровни, ачивки)" },
                    { key: "digest_enabled", label: "Дайджест (еженедельная сводка)" },
                  ] as { key: keyof NotificationPreferences; label: string }[]
                ).map(({ key, label }) => (
                  <label key={key} className="flex cursor-pointer items-center gap-3 text-gray-300">
                    <input
                      type="checkbox"
                      checked={prefs[key]}
                      onChange={() => handlePrefToggle(key)}
                      className="accent-purple-500 h-4 w-4"
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
