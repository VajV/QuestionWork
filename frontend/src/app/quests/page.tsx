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
import type { QuestFilterState } from "@/types";
import {
  getQuests,
  applyToQuest,
  Quest,
  QuestApplicationCreate,
} from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import QuestCard from "@/components/quests/QuestCard";
import QuestFilters from "@/components/quests/QuestFilters";
import ApplyModal from "@/components/quests/ApplyModal";
import QuestStatusBadge from "@/components/quests/QuestStatusBadge";

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
    async (reset = false, targetPage?: number) => {
      setLoading(true);
      setError(null);

      try {
        const fetchPage = reset ? 1 : (targetPage ?? page);
        const response = await getQuests(fetchPage, 10, filters);

        setQuests((prev) =>
          reset ? response.quests : [...prev, ...response.quests],
        );
        setTotal(response.total);
        setHasMore(response.has_more);
        setPage(fetchPage);
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
    setAppliedQuests(new Set([...Array.from(appliedQuests), selectedQuest.id]));
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
    loadQuests(false, page + 1);
  };

  return (
    <main className="min-h-screen bg-gray-950 text-gray-200 font-inter">
      <Header />

      <div className="container mx-auto px-4 py-8">
        {/* Заголовок */}
        <div className="text-center mb-10 mt-6">
          <h1 className="text-4xl font-cinzel font-bold text-amber-500 drop-shadow-[0_0_10px_rgba(217,119,6,0.5)] uppercase tracking-widest mb-2 flex items-center justify-center gap-4">
            <span className="text-3xl grayscale">📜</span>
            Доска Заданий
            <span className="text-3xl grayscale">⚔️</span>
          </h1>
          <div className="divider-ornament w-64 mx-auto"></div>
          <p className="text-gray-400 font-inter mt-4 tracking-wide">
            Заключайте контракты, получайте золото и возвышайте своё Имя
          </p>
        </div>

        {/* Статистика */}
        <div className="flex items-center justify-between mb-6 bg-black/40 border border-purple-900/30 p-4 rounded text-sm font-mono">
          <p className="text-gray-400 uppercase tracking-widest">
            Актуальных контрактов:{" "}
            <span className="text-amber-500 font-bold ml-2">{total}</span>
          </p>
          {filters.status && (
            <div className="flex items-center gap-3">
              <span className="text-purple-400 opacity-60 uppercase tracking-wider text-xs">Метка Искателя:</span>
              <QuestStatusBadge status={filters.status} size="sm" />
            </div>
          )}
        </div>

        {/* Фильтры */}
        <QuestFilters onFilterChange={handleFilterChange} />

        {/* Лоадер */}
        {loading && quests.length === 0 && (
          <Card className="p-12 text-center bg-transparent border-none shadow-none">
            <div className="w-16 h-16 border-4 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto mb-6 shadow-[0_0_15px_rgba(217,119,6,0.5)]" />
            <p className="text-amber-500/70 font-cinzel uppercase tracking-widest">Чтение древних свитков...</p>
          </Card>
        )}

        {/* Ошибка */}
        {error && (
          <Card className="p-6 mb-6 border-red-900/50 bg-red-950/20">
            <div className="text-center">
              <span className="text-5xl mb-4 block drop-shadow-[0_0_15px_rgba(220,38,38,0.8)]">⚠️</span>
              <h3 className="text-xl font-cinzel font-bold text-red-500 mb-2">
                Магическая Аномалия
              </h3>
              <p className="text-gray-400 mb-6 font-mono text-sm">{error}</p>
              <Button onClick={() => loadQuests(true)} variant="secondary" className="border-red-900/50 hover:border-red-500/50 text-red-400">
                🔄 Сотворить заклинание заново
              </Button>
            </div>
          </Card>
        )}

        {/* Список квестов */}
        {!loading && quests.length === 0 && !error && (
          <Card className="p-12 text-center bg-black/40 border-purple-900/30">
            <span className="text-6xl mb-6 block opacity-50 grayscale">📭</span>
            <h3 className="text-2xl font-cinzel font-bold mb-4 text-gray-300">Свитки не найдены</h3>
            <p className="text-gray-500 mb-8 font-inter">
              Доска заданий пуста. Возможно, стоит поискать в других землях (изменить фильтры).
            </p>
            <Button onClick={() => handleFilterChange({})} variant="primary" className="shadow-[0_0_15px_rgba(217,119,6,0.2)]">
              🔄 Очистить условия поиска
            </Button>
          </Card>
        )}

        {/* Карточки квестов */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
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
          <div className="text-center mt-12">
            <Button
              onClick={loadMore}
              variant="secondary"
              disabled={loading}
              className="px-10 py-3 border-purple-900/50 hover:border-purple-500/50 shadow-[0_0_10px_rgba(88,28,135,0.3)] hover:shadow-[0_0_20px_rgba(168,85,247,0.4)]"
            >
              {loading ? (
                <span className="flex items-center gap-3 font-cinzel">
                  <svg className="animate-spin h-5 w-5 text-amber-500" viewBox="0 0 24 24">
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
                  Раскрываем свитки...
                </span>
              ) : (
                "📜 Показать больше записей"
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
