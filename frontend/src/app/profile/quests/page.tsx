/**
 * Страница моих квестов в профиле
 * 
 * Вкладки:
 * - Созданные (клиент)
 * - В работе (назначенные мне)
 * - Завершённые
 */

"use client";

import { useState, useEffect } from "react";
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
  useEffect(() => {
    async function loadQuests() {
      if (!isAuthenticated || !user) return;
      
      setLoading(true);
      setError(null);
      
      try {
        let statusFilter: QuestStatus | undefined = undefined;
        
        if (activeTab === 'completed') {
          statusFilter = 'completed';
        } else if (activeTab === 'assigned') {
          // Квесты где пользователь назначен исполнителем
          // Пока загружаем все и фильтруем на клиенте
        }
        
        const response = await getQuests(1, 50, {
          status: statusFilter,
        });
        
        // Фильтрация на клиенте
        let filteredQuests = response.quests;
        
        if (activeTab === 'created') {
          // Квесты созданные пользователем
          filteredQuests = filteredQuests.filter(q => q.client_id === user.id);
        } else if (activeTab === 'assigned') {
          // Квесты где пользователь назначен исполнителем
          filteredQuests = filteredQuests.filter(q => q.assigned_to === user.id);
        } else if (activeTab === 'completed') {
          // Завершённые квесты пользователя
          filteredQuests = filteredQuests.filter(q => 
            q.assigned_to === user.id || q.client_id === user.id
          );
        }
        
        setQuests(filteredQuests);
      } catch (err) {
        console.error("Ошибка загрузки квестов:", err);
        setError("Не удалось загрузить квесты");
      } finally {
        setLoading(false);
      }
    }
    
    loadQuests();
  }, [activeTab, isAuthenticated, user]);

  // Редирект если не авторизован
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [isAuthenticated, authLoading, router]);

  if (authLoading || loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <Card className="p-12 text-center">
            <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-400">Загрузка квестов...</p>
          </Card>
        </div>
      </main>
    );
  }

  if (!isAuthenticated || !user) {
    return null;
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        {/* Заголовок */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-center mb-4">
            📋 Мои квесты
          </h1>
          <p className="text-gray-400 text-center">
            Управление вашими квестами и заказами
          </p>
        </div>

        {/* Вкладки */}
        <div className="flex gap-2 mb-6 overflow-x-auto">
          <button
            onClick={() => setActiveTab('created')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors whitespace-nowrap ${
              activeTab === 'created'
                ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/30'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            📝 Созданные ({quests.filter(q => q.client_id === user.id).length})
          </button>
          <button
            onClick={() => setActiveTab('assigned')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors whitespace-nowrap ${
              activeTab === 'assigned'
                ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/30'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            ⚡ В работе ({quests.filter(q => q.assigned_to === user.id && q.status === 'in_progress').length})
          </button>
          <button
            onClick={() => setActiveTab('completed')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors whitespace-nowrap ${
              activeTab === 'completed'
                ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/30'
                : 'bg-gray-800 text-gray-400 hover:text-white'
            }`}
          >
            ✅ Завершённые ({quests.filter(q => q.status === 'completed' && (q.assigned_to === user.id || q.client_id === user.id)).length})
          </button>
        </div>

        {/* Ошибка */}
        {error && (
          <Card className="p-6 mb-6 border-red-500/50">
            <div className="text-center">
              <span className="text-4xl mb-2 block">⚠️</span>
              <h3 className="text-xl font-bold text-red-400 mb-2">Ошибка</h3>
              <p className="text-gray-400">{error}</p>
            </div>
          </Card>
        )}

        {/* Пустой список */}
        {!loading && quests.length === 0 && (
          <Card className="p-12 text-center">
            <span className="text-6xl mb-4 block">
              {activeTab === 'created' && '📭'}
              {activeTab === 'assigned' && '🔍'}
              {activeTab === 'completed' && '🏆'}
            </span>
            <h3 className="text-xl font-bold mb-2">
              {activeTab === 'created' && 'Нет созданных квестов'}
              {activeTab === 'assigned' && 'Нет квестов в работе'}
              {activeTab === 'completed' && 'Нет завершённых квестов'}
            </h3>
            <p className="text-gray-400 mb-4">
              {activeTab === 'created' && 'Создайте свой первый квест и найдите исполнителя'}
              {activeTab === 'assigned' && 'Откликнитесь на квесты в ленте'}
              {activeTab === 'completed' && 'Завершите первый квест для получения награды'}
            </p>
            {activeTab === 'created' ? (
              <Link href="/quests/create">
                <Button variant="primary">➕ Создать квест</Button>
              </Link>
            ) : (
              <Link href="/quests">
                <Button variant="secondary">📜 Перейти к ленте</Button>
              </Link>
            )}
          </Card>
        )}

        {/* Список квестов */}
        {!loading && quests.length > 0 && (
          <div className="space-y-4">
            {quests.map((quest) => (
              <Card key={quest.id} className="p-6 hover:border-purple-500/50 transition-colors">
                <div className="flex items-center justify-between flex-wrap gap-4">
                  {/* Информация о квесте */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <QuestStatusBadge status={quest.status} size="sm" />
                      <h3 className="text-lg font-bold truncate">{quest.title}</h3>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-gray-400">
                      <span>💰 {quest.budget.toLocaleString('ru-RU')}₽</span>
                      <span>⚡ {quest.xp_reward} XP</span>
                      <span>📅 {new Date(quest.created_at).toLocaleDateString('ru-RU')}</span>
                    </div>
                  </div>

                  {/* Действия */}
                  <div className="flex items-center gap-3">
                    <Link href={`/quests/${quest.id}`}>
                      <Button variant="secondary" className="text-sm">
                        📄 Подробнее
                      </Button>
                    </Link>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Навигация */}
        <div className="mt-8">
          <Link href="/profile">
            <Button variant="secondary">← Назад в профиль</Button>
          </Link>
        </div>
      </div>
    </main>
  );
}
