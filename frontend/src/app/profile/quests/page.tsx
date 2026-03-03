/**
 * Страница моих квестов в профиле
 * 
 * Вкладки:
 * - Созданные (клиент)
 * - В работе (назначенные мне)
 * - Завершённые
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getQuests, Quest, QuestStatus } from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import QuestStatusBadge from "@/components/quests/QuestStatusBadge";
import Link from "next/link";

type TabType = 'created' | 'assigned' | 'completed';

export default function ProfileQuestsPage() {
  const router = useRouter();
  const { isAuthenticated, user, loading: authLoading } = useAuth();
  
  const [activeTab, setActiveTab] = useState<TabType>('created');
  const [quests, setQuests] = useState<Quest[]>([]);
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
      let statusFilter: QuestStatus | undefined = undefined;

      if (activeTab === 'completed') {
        statusFilter = 'completed';
      } else if (activeTab === 'assigned') {
        statusFilter = 'in_progress';
      }

      const response = await getQuests(1, 50, { status: statusFilter });

      // Фильтрация на клиенте
      let filteredQuests = response.quests;

      if (activeTab === 'created') {
        filteredQuests = filteredQuests.filter(q => q.client_id === user.id);
      } else if (activeTab === 'assigned') {
        filteredQuests = filteredQuests.filter(q => q.assigned_to === user.id);
      } else if (activeTab === 'completed') {
        filteredQuests = filteredQuests.filter(
          q => q.assigned_to === user.id || q.client_id === user.id
        );
      }

      setQuests(filteredQuests);
    } catch (err) {
      console.error("Ошибка загрузки квестов:", err);
      setError("Не удалось загрузить квесты");
    } finally {
      setLoading(false);
    }
  }, [activeTab, user?.id, isAuthenticated]);

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

  return (
    <main className="min-h-screen bg-gray-950 text-gray-200 font-inter">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        {/* Заголовок */}
        <div className="mb-10 mt-4 text-center">
          <h1 className="text-3xl md:text-4xl font-cinzel font-bold mb-3 text-amber-500 drop-shadow-[0_0_10px_rgba(217,119,6,0.5)] uppercase tracking-widest flex items-center justify-center gap-3">
            <span className="text-3xl grayscale opacity-70">📋</span>
            Журнал Заданий
          </h1>
          <div className="divider-ornament w-48 mx-auto my-4"></div>
          <p className="text-gray-400 font-inter">
            Хроника ваших триумфов и текущих обязательств
          </p>
        </div>

        {/* Вкладки */}
        <div className="flex flex-wrap gap-2 mb-8 justify-center">
          <button
            onClick={() => setActiveTab('created')}
            className={`px-6 py-3 rounded font-cinzel tracking-wider text-sm transition-all border ${
              activeTab === 'created'
                ? 'bg-amber-950/40 text-amber-400 border-amber-700/50 shadow-[inset_0_0_10px_rgba(217,119,6,0.2)]'
                : 'bg-black/40 text-gray-400 border-gray-800 hover:border-gray-600 hover:text-gray-300'
            }`}
          >
            📝 Размещённые Контракты ({quests.filter(q => q.client_id === user.id).length})
          </button>
          <button
            onClick={() => setActiveTab('assigned')}
            className={`px-6 py-3 rounded font-cinzel tracking-wider text-sm transition-all border ${
              activeTab === 'assigned'
                ? 'bg-purple-950/40 text-purple-400 border-purple-700/50 shadow-[inset_0_0_10px_rgba(168,85,247,0.2)]'
                : 'bg-black/40 text-gray-400 border-gray-800 hover:border-gray-600 hover:text-gray-300'
            }`}
          >
            ⚡ Активные Миссии ({quests.filter(q => q.assigned_to === user.id && q.status === 'in_progress').length})
          </button>
          <button
            onClick={() => setActiveTab('completed')}
            className={`px-6 py-3 rounded font-cinzel tracking-wider text-sm transition-all border ${
              activeTab === 'completed'
                ? 'bg-green-950/40 text-green-400 border-green-700/50 shadow-[inset_0_0_10px_rgba(34,197,94,0.2)]'
                : 'bg-black/40 text-gray-400 border-gray-800 hover:border-gray-600 hover:text-gray-300'
            }`}
          >
            ✅ Былая Слава ({quests.filter(q => q.status === 'completed' && (q.assigned_to === user.id || q.client_id === user.id)).length})
          </button>
        </div>

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
        {!loading && quests.length === 0 && (
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
                <Link href="/quests/create">
                  <Button variant="primary" className="shadow-[0_0_15px_rgba(217,119,6,0.3)]">
                    ➕ Объявить Контракт
                  </Button>
                </Link>
              ) : (
                <Link href="/quests">
                  <Button variant="secondary" className="border-purple-900/50 hover:border-purple-500/50 shadow-[0_0_10px_rgba(168,85,247,0.2)]">
                    📜 Открыть Доску Заданий
                  </Button>
                </Link>
              )}
            </div>
          </Card>
        )}

        {/* Список квестов */}
        {!loading && quests.length > 0 && (
          <div className="space-y-4">
            {quests.map((quest) => (
              <Card key={quest.id} className="p-0 border-none shadow-none bg-transparent">
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
                      <Link href={`/quests/${quest.id}`} className="w-full md:w-auto">
                        <Button variant="secondary" className="w-full text-sm font-cinzel tracking-wider border-purple-900/50 hover:border-purple-500/50 bg-black/50">
                          Изучить Свиток
                        </Button>
                      </Link>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Навигация */}
        <div className="mt-10 text-center md:text-left">
          <Link href="/profile">
            <Button variant="secondary" className="border-gray-800 hover:border-gray-600 font-cinzel text-sm tracking-wider px-8 opacity-80 hover:opacity-100">
              ← Назад к Личному Делу
            </Button>
          </Link>
        </div>
      </div>
    </main>
  );
}
