/**
 * Страница ленты квестов
 *
 * - Загрузка квестов через API (с пагинацией)
 * - Фильтры: по грейду, навыкам, бюджету, статусу
 * - Карточки квестов с кнопками отклика
 */

"use client";

import { useState, useEffect, useCallback } from "react";

import { useAuth } from "@/context/AuthContext";
import {
  getQuests,
  applyToQuest,
  Quest,
  UserGrade,
  QuestStatus,
  QuestApplicationCreate,
} from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import QuestCard from "@/components/quests/QuestCard";
import QuestFilters from "@/components/quests/QuestFilters";
import ApplyModal from "@/components/quests/ApplyModal";
import QuestStatusBadge from "@/components/quests/QuestStatusBadge";

interface QuestFilterState {
  grade?: UserGrade;
  status?: QuestStatus;
  skill?: string;
  minBudget?: number;
  maxBudget?: number;
}

export default function QuestsPage() {
  const { isAuthenticated, user } = useAuth();

  // Состояния
  const [quests, setQuests] = useState<Quest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  // Фильтры
  const [filters, setFilters] = useState<QuestFilterState>({
    status: "open",
  });

  // Модальное окно отклика
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [selectedQuest, setSelectedQuest] = useState<Quest | null>(null);
  const [appliedQuests, setAppliedQuests] = useState<Set<string>>(new Set());

  /**
   * Загрузка квестов
   */
  const loadQuests = useCallback(
    async (reset = false) => {
      setLoading(true);
      setError(null);

      try {
        const response = await getQuests(reset ? 1 : page, 10, filters);

        setQuests((prev) =>
          reset ? response.quests : [...prev, ...response.quests],
        );
        setTotal(response.total);
        setHasMore(response.has_more);
        setPage(response.page);
      } catch (err) {
        console.error("Ошибка загрузки квестов:", err);
        setError("Не удалось загрузить квесты. Попробуйте позже.");
      } finally {
        setLoading(false);
      }
    },
    [page, filters],
  );

  // Первоначальная загрузка
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    loadQuests(true);
  }, [filters]);

  /**
   * Обработка изменения фильтров
   */
  const handleFilterChange = (newFilters: QuestFilterState) => {
    setFilters(newFilters);
    setPage(1);
    setQuests([]);
  };

  /**
   * Обработка клика "Откликнуться"
   */
  const handleApplyClick = (questId: string) => {
    const quest = quests.find((q) => q.id === questId);
    if (quest) {
      setSelectedQuest(quest);
      setShowApplyModal(true);
    }
  };

  /**
   * Отправка отклика
   */
  const handleApplySubmit = async (data: QuestApplicationCreate) => {
    if (!selectedQuest) return;

    await applyToQuest(selectedQuest.id, data);
    setAppliedQuests(new Set([...appliedQuests, selectedQuest.id]));
    setShowApplyModal(false);
    setSelectedQuest(null);

    // Обновляем квест в списке
    setQuests(
      quests.map((q) =>
        q.id === selectedQuest.id
          ? { ...q, applications: [...q.applications, user?.id || ""] }
          : q,
      ),
    );
  };

  /**
   * Загрузка ещё (пагинация)
   */
  const loadMore = () => {
    setPage(page + 1);
    loadQuests(false);
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />

      <div className="container mx-auto px-4 py-8">
        {/* Заголовок */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-center mb-4 glow-text">
            <span className="text-purple-400">📜</span> Лента квестов
          </h1>
          <p className="text-gray-400 text-center">
            Найдите подходящий заказ и заработайте XP + деньги
          </p>
        </div>

        {/* Статистика */}
        <div className="flex items-center justify-between mb-6">
          <p className="text-gray-400">
            Найдено квестов:{" "}
            <span className="text-white font-bold">{total}</span>
          </p>
          {filters.status && (
            <div className="flex items-center gap-2">
              <span className="text-gray-400 text-sm">Фильтр:</span>
              <QuestStatusBadge status={filters.status} size="sm" />
            </div>
          )}
        </div>

        {/* Фильтры */}
        <QuestFilters onFilterChange={handleFilterChange} />

        {/* Лоадер */}
        {loading && quests.length === 0 && (
          <Card className="p-12 text-center">
            <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-400">Загрузка квестов...</p>
          </Card>
        )}

        {/* Ошибка */}
        {error && (
          <Card className="p-6 mb-6 border-red-500/50">
            <div className="text-center">
              <span className="text-4xl mb-2 block">⚠️</span>
              <h3 className="text-xl font-bold text-red-400 mb-2">
                Ошибка загрузки
              </h3>
              <p className="text-gray-400 mb-4">{error}</p>
              <Button onClick={() => loadQuests(true)} variant="secondary">
                🔄 Повторить
              </Button>
            </div>
          </Card>
        )}

        {/* Список квестов */}
        {!loading && quests.length === 0 && !error && (
          <Card className="p-12 text-center">
            <span className="text-6xl mb-4 block">📭</span>
            <h3 className="text-xl font-bold mb-2">Квесты не найдены</h3>
            <p className="text-gray-400 mb-4">
              Попробуйте изменить параметры фильтров
            </p>
            <Button onClick={() => handleFilterChange({})} variant="primary">
              🔄 Сбросить фильтры
            </Button>
          </Card>
        )}

        {/* Карточки квестов */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {quests.map((quest) => (
            <QuestCard
              key={quest.id}
              quest={quest}
              onApply={handleApplyClick}
              isApplied={
                appliedQuests.has(quest.id) ||
                quest.applications.includes(user?.id || "")
              }
              canApply={isAuthenticated && quest.client_id !== user?.id}
            />
          ))}
        </div>

        {/* Кнопка "Загрузить ещё" */}
        {hasMore && (
          <div className="text-center mt-8">
            <Button
              onClick={loadMore}
              variant="secondary"
              disabled={loading}
              className="px-8 py-3"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Загрузка...
                </span>
              ) : (
                "📥 Загрузить ещё"
              )}
            </Button>
          </div>
        )}
      </div>

      {/* Модальное окно отклика */}
      {showApplyModal && selectedQuest && (
        <ApplyModal
          questTitle={selectedQuest.title}
          onSubmit={handleApplySubmit}
          onClose={() => {
            setShowApplyModal(false);
            setSelectedQuest(null);
          }}
        />
      )}
    </main>
  );
}
