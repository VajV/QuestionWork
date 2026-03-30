/**
 * Страница моих квестов в профиле
 * 
 * Вкладки:
 * - Созданные (клиент)
 * - В работе (назначенные мне)
 * - Завершённые
 */

"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { motion } from "@/lib/motion";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getApiErrorMessage, getQuests, Quest } from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import SeasonFactionRail from "@/components/ui/SeasonFactionRail";
import WorldPanel from "@/components/ui/WorldPanel";
import QuestStatusBadge from "@/components/quests/QuestStatusBadge";
import RepeatHireCard from "@/components/growth/RepeatHireCard";

type TabType = 'created' | 'assigned' | 'completed';

export default function ProfileQuestsPage() {
  const router = useRouter();
  const { isAuthenticated, user, loading: authLoading } = useAuth();
  
  const [activeTab, setActiveTab] = useState<TabType>('created');
  const [quests, setQuests] = useState<Quest[]>([]);
  const [allUserQuests, setAllUserQuests] = useState<Quest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Загрузка квестов для текущей вкладки
   */
  const loadQuests = useCallback(async () => {
    if (!isAuthenticated || !user) return;

    setLoading(true);
    setError(null);

    try {
      const allResponse = await getQuests(1, 100, { userId: user.id });
      setAllUserQuests(allResponse.quests);
      setQuests(allResponse.quests);
    } catch (err: unknown) {
      console.error("Ошибка загрузки квестов:", err);
      setError(getApiErrorMessage(err, "Не удалось загрузить квесты"));
    } finally {
      setLoading(false);
    }
  }, [user, isAuthenticated]);

  const visibleQuests = useMemo(() => {
    if (!user) {
      return [];
    }

    if (activeTab === 'created') {
      return quests.filter((q) => q.client_id === user.id);
    }

    if (activeTab === 'assigned') {
      return quests.filter((q) => q.assigned_to === user.id && (q.status === 'assigned' || q.status === 'in_progress' || q.status === 'revision_requested'));
    }

    return quests.filter((q) =>
      (q.status === 'completed' || q.status === 'confirmed') &&
        (q.assigned_to === user.id || q.client_id === user.id),
    );
  }, [activeTab, quests, user]);

  useEffect(() => {
    loadQuests();
  }, [loadQuests]);

  // Редирект если не авторизован
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [isAuthenticated, authLoading, router]);

  if (authLoading || loading) {
    return (
      <main className="min-h-screen bg-gray-950 text-gray-200">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <Card className="p-12 text-center bg-transparent border-none">
            <div className="w-16 h-16 border-4 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto mb-6 shadow-[0_0_15px_rgba(217,119,6,0.5)]" />
            <p className="text-amber-500/70 font-cinzel tracking-widest uppercase">Поиск в архивах...</p>
          </Card>
        </div>
      </main>
    );
  }

  if (!isAuthenticated || !user) {
    return null;
  }

  const createdCount = allUserQuests.filter((q) => q.client_id === user.id).length;
  const assignedCount = allUserQuests.filter((q) => q.assigned_to === user.id && (q.status === 'assigned' || q.status === 'in_progress' || q.status === 'revision_requested')).length;
  const completedCount = allUserQuests.filter((q) => (q.status === 'completed' || q.status === 'confirmed') && (q.assigned_to === user.id || q.client_id === user.id)).length;

  return (
    <main className="guild-world-shell min-h-screen bg-gray-950 text-gray-200 font-inter">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        <GuildStatusStrip
          mode="profile"
          eyebrow="Quest ledger"
          title="Журнал заданий теперь выглядит как карьера, а не как голый список статусов"
          description="Размещённые контракты, активные миссии и закрытые циклы собраны в один слой, который рифмуется с profile, marketplace и quest board."
          stats={[
            { label: "Created", value: createdCount, note: "контракты клиента", tone: "amber" },
            { label: "Assigned", value: assignedCount, note: "в работе у вас", tone: "purple" },
            { label: "Completed", value: completedCount, note: "закрытые циклы", tone: "emerald" },
            { label: "Visible", value: visibleQuests.length, note: "в текущей вкладке", tone: "cyan" },
          ]}
          signals={[
            { label: `${activeTab} tab`, tone: activeTab === 'completed' ? 'emerald' : activeTab === 'assigned' ? 'purple' : 'amber' },
            { label: error ? 'archive recovery needed' : 'archive synced', tone: error ? 'red' : 'slate' },
          ]}
          className="mb-6"
        />

        <SeasonFactionRail mode="profile" questCount={visibleQuests.length} className="mb-6" />

        {/* Заголовок */}
        <WorldPanel
          eyebrow="Career archive"
          title="Хроника ваших триумфов и текущих обязательств"
          description="Новый panel primitive сводит заголовочные блоки на внутренних страницах к единой форме, вместо разрозненных hero-секций."
          tone="amber"
          className="mb-8"
          compact
        />

        {/* Вкладки */}
        <motion.div layout className="flex flex-wrap gap-2 mb-8 justify-center">
          <motion.button
            onClick={() => setActiveTab('created')}
            whileTap={{ scale: 0.98 }}
            className={`px-6 py-3 rounded font-cinzel tracking-wider text-sm transition-all border ${
              activeTab === 'created'
                ? 'bg-amber-950/40 text-amber-400 border-amber-700/50 shadow-[inset_0_0_10px_rgba(217,119,6,0.2)]'
                : 'bg-black/40 text-gray-400 border-gray-800 hover:border-gray-600 hover:text-gray-300'
            }`}
          >
            📝 Размещённые Контракты ({createdCount})
          </motion.button>
          <motion.button
            onClick={() => setActiveTab('assigned')}
            whileTap={{ scale: 0.98 }}
            className={`px-6 py-3 rounded font-cinzel tracking-wider text-sm transition-all border ${
              activeTab === 'assigned'
                ? 'bg-purple-950/40 text-purple-400 border-purple-700/50 shadow-[inset_0_0_10px_rgba(168,85,247,0.2)]'
                : 'bg-black/40 text-gray-400 border-gray-800 hover:border-gray-600 hover:text-gray-300'
            }`}
          >
            ⚡ Активные Миссии ({assignedCount})
          </motion.button>
          <motion.button
            onClick={() => setActiveTab('completed')}
            whileTap={{ scale: 0.98 }}
            className={`px-6 py-3 rounded font-cinzel tracking-wider text-sm transition-all border ${
              activeTab === 'completed'
                ? 'bg-green-950/40 text-green-400 border-green-700/50 shadow-[inset_0_0_10px_rgba(34,197,94,0.2)]'
                : 'bg-black/40 text-gray-400 border-gray-800 hover:border-gray-600 hover:text-gray-300'
            }`}
          >
            ✅ Былая Слава ({completedCount})
          </motion.button>
        </motion.div>

        {/* Ошибка */}
        {error && (
          <Card className="p-0 border-none bg-transparent mb-6">
            <div className="bg-red-950/30 border border-red-900/50 p-6 rounded text-center">
              <span className="text-4xl mb-4 block drop-shadow-[0_0_10px_rgba(220,38,38,0.5)]">⚠️</span>
              <h3 className="text-xl font-cinzel font-bold text-red-500 mb-2">Проклятие Архивов</h3>
              <p className="text-gray-400 mb-4 font-mono text-sm">{error}</p>
              <Button variant="secondary" onClick={loadQuests} className="text-red-400 border-red-900/50 hover:border-red-500/50">
                🔄 Прочитать свиток заново
              </Button>
            </div>
          </Card>
        )}

        {/* Пустой список */}
        {!loading && !error && visibleQuests.length === 0 && (
          <Card className="p-0 border-none bg-transparent">
            <div className="rpg-card p-12 text-center opacity-90">
              <span className="text-6xl mb-6 block grayscale opacity-50 drop-shadow-md">
                {activeTab === 'created' && '📭'}
                {activeTab === 'assigned' && '⚔️'}
                {activeTab === 'completed' && '🏆'}
              </span>
              <h3 className="text-2xl font-cinzel font-bold mb-3 text-gray-200">
                {activeTab === 'created' && 'Доска пуста'}
                {activeTab === 'assigned' && 'Нет активных миссий'}
                {activeTab === 'completed' && 'Зал Славы пустует'}
              </h3>
              <p className="text-gray-400 mb-8 font-inter max-w-md mx-auto">
                {activeTab === 'created' && 'Объявите о задаче, чтобы привлечь смелых искателей на помощь.'}
                {activeTab === 'assigned' && 'Ваш клинок бездействует. Отправляйтесь на Доску Заданий.'}
                {activeTab === 'completed' && 'Завершите свой первый контракт, чтобы ваше имя вошло в легенды.'}
              </p>
              {activeTab === 'created' ? (
                <Button href="/quests/create" variant="primary" className="shadow-[0_0_15px_rgba(217,119,6,0.3)]">
                  ➕ Объявить Контракт
                </Button>
              ) : (
                <Button href="/quests" variant="secondary" className="border-purple-900/50 hover:border-purple-500/50 shadow-[0_0_10px_rgba(168,85,247,0.2)]">
                  📜 Открыть Доску Заданий
                </Button>
              )}
            </div>
          </Card>
        )}

        {/* Список квестов */}
        {!loading && !error && visibleQuests.length > 0 && (
          <div className="space-y-4">
            {visibleQuests.map((quest, index) => (
              <motion.div
                key={quest.id}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.15 }}
                transition={{ duration: 0.24, delay: index * 0.03, ease: "easeOut" }}
              >
              <Card className="p-0 border-none shadow-none bg-transparent">
                <div className="rpg-card p-5 md:p-6 hover:shadow-[0_0_15px_rgba(168,85,247,0.2)] transition-shadow">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
                    {/* Информация о квесте */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-3">
                        <QuestStatusBadge status={quest.status} size="sm" />
                        <h3 className="text-lg md:text-xl font-cinzel font-bold text-gray-100 truncate">{quest.title}</h3>
                      </div>
                      <div className="flex flex-wrap items-center gap-4 md:gap-6 text-sm font-mono text-gray-500">
                        <span className="flex items-center gap-1 bg-black/40 px-2 py-1 rounded border border-gray-800">
                          <span className="opacity-70 text-amber-500">💰</span> 
                          <span className="text-gray-300 font-bold">{quest.budget.toLocaleString('ru-RU')}₽</span>
                        </span>
                        <span className="flex items-center gap-1 bg-black/40 px-2 py-1 rounded border border-gray-800">
                          <span className="opacity-70 text-purple-400">⚡</span> 
                          <span className="text-gray-300 font-bold">{quest.xp_reward} XP</span>
                        </span>
                        <span className="flex items-center gap-1 text-xs uppercase tracking-widest">
                          <span className="opacity-50">📅</span> 
                          {new Date(quest.created_at).toLocaleDateString('ru-RU')}
                        </span>
                      </div>
                    </div>

                    {/* Действия */}
                    <div className="flex items-center md:justify-end shrink-0">
                      <Button href={`/quests/${quest.id}`} variant="secondary" className="w-full md:w-auto text-sm font-cinzel tracking-wider border-purple-900/50 hover:border-purple-500/50 bg-black/50">
                        Изучить Свиток
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
              {activeTab === 'completed' && user && quest.client_id === user.id && (
                <RepeatHireCard quest={quest} freelancerId={quest.assigned_to} />
              )}
              </motion.div>
            ))}
          </div>
        )}

        {/* Навигация */}
        <div className="mt-10 text-center md:text-left">
          <Button href="/profile" variant="secondary" className="border-gray-800 hover:border-gray-600 font-cinzel text-sm tracking-wider px-8 opacity-80 hover:opacity-100">
            ← Назад к Личному Делу
          </Button>
        </div>
      </div>
    </main>
  );
}
