/**
 * Страница ленты квестов
 *
 * - Загрузка квестов через API (с пагинацией)
 * - Фильтры: по грейду, навыкам, бюджету, статусу
 * - Карточки квестов с кнопками отклика
 */

"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useSWRFetch } from "@/hooks/useSWRFetch";

import { useAuth } from "@/context/AuthContext";
import type { QuestFilterState } from "@/types";
import {
  getQuests,
  getTrainingQuests,
  getRaidQuests,
  applyToQuest,
  acceptTrainingQuest,
  Quest,
  QuestApplicationCreate,
} from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import SeasonFactionRail from "@/components/ui/SeasonFactionRail";
import WorldPanel from "@/components/ui/WorldPanel";
import QuestCard from "@/components/quests/QuestCard";
import QuestFilters from "@/components/quests/QuestFilters";
import ApplyModal from "@/components/quests/ApplyModal";
import QuestStatusBadge from "@/components/quests/QuestStatusBadge";
import RecommendedQuestPanel from "@/components/quests/RecommendedQuestPanel";
import ErrorBoundary from "@/components/ui/ErrorBoundary";

export default function QuestsPage() {
  const { isAuthenticated, user } = useAuth();

  // Состояния
  const [quests, setQuests] = useState<Quest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageRef = useRef(page);
  pageRef.current = page;
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  // Фильтры
  const [filters, setFilters] = useState<QuestFilterState>({
    status: "open",
  });

  // Quest mode toggle
  const [questMode, setQuestMode] = useState<"standard" | "training" | "raid">("standard");

  // Build a stable SWR key for the first page fetch
  const swrKey = `quests:${questMode}:${JSON.stringify(filters)}:1`;
  const { data: swrPage1 } = useSWRFetch(
    swrKey,
    () => questMode === "training"
      ? getTrainingQuests(1, 10, filters.grade, filters.skill)
      : questMode === "raid"
        ? getRaidQuests(1, 10, filters.grade, filters.skill)
        : getQuests(1, 10, filters),
    { revalidateOnFocus: false },
  );

  // Модальное окно отклика
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [selectedQuest, setSelectedQuest] = useState<Quest | null>(null);
  const [appliedQuests, setAppliedQuests] = useState<Set<string>>(new Set());

  const activeFilterCount = useMemo(
    () =>
      [filters.grade, filters.status, filters.skill, filters.minBudget, filters.maxBudget].filter(
        (value) => value !== undefined && value !== "" && value !== null,
      ).length,
    [filters],
  );

  const urgentCount = useMemo(
    () => quests.filter((quest) => quest.is_urgent).length,
    [quests],
  );

  /**
   * Загрузка квестов
   */
  const loadQuests = useCallback(
    async (reset = false, targetPage?: number) => {
      setLoading(true);
      setError(null);

      try {
        const fetchPage = reset ? 1 : (targetPage ?? pageRef.current);
        const response = questMode === "training"
          ? await getTrainingQuests(fetchPage, 10, filters.grade, filters.skill)
          : questMode === "raid"
            ? await getRaidQuests(fetchPage, 10, filters.grade, filters.skill)
            : await getQuests(fetchPage, 10, filters);

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
    [filters, questMode],
  );

  // Первоначальная загрузка
  useEffect(() => {
    // If SWR already has fresh data for page 1, seed the state and skip the manual fetch
    if (swrPage1 && page === 1 && quests.length === 0) {
      setQuests(swrPage1.quests);
      setTotal(swrPage1.total);
      setHasMore(swrPage1.has_more);
      setLoading(false);
      return;
    }
    loadQuests(true);
  }, [loadQuests]); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Обработка изменения фильтров
   */
  const handleFilterChange = (newFilters: QuestFilterState) => {
    setFilters(newFilters);
    setPage(1);
    setQuests([]);
  };

  /**
   * Обработка клика "Откликнуться" (standard) or "Принять" (training)
   */
  const handleApplyClick = (questId: string) => {
    const quest = quests.find((q) => q.id === questId);
    if (!quest) return;
    if (quest.quest_type === "training") {
      handleAcceptTraining(questId);
    } else {
      setSelectedQuest(quest);
      setShowApplyModal(true);
    }
  };

  /**
   * Accept a training quest (auto-assign + start)
   */
  const handleAcceptTraining = async (questId: string) => {
    try {
      await acceptTrainingQuest(questId);
      setAppliedQuests(new Set([...Array.from(appliedQuests), questId]));
      // Reload to get updated status
      loadQuests(true);
    } catch (err) {
      console.error("Ошибка принятия тренировки:", err);
      setError("Не удалось принять тренировочный квест.");
    }
  };

  /**
   * Отправка отклика
   */
  const handleApplySubmit = async (data: QuestApplicationCreate) => {
    if (!selectedQuest) return;

    const result = await applyToQuest(selectedQuest.id, data);
    setAppliedQuests(new Set([...Array.from(appliedQuests), selectedQuest.id]));
    setShowApplyModal(false);
    setSelectedQuest(null);

    // Обновляем квест в списке
    setQuests(
      quests.map((q) =>
        q.id === selectedQuest.id
          ? {
              ...q,
              applications: q.applications.includes(result.application.freelancer_id)
                ? q.applications
                : [...q.applications, result.application.freelancer_id],
            }
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
    <ErrorBoundary>
    <main className="guild-world-shell min-h-screen bg-[var(--bg-primary)] text-gray-200 font-inter">
      <Header />

      <div className="container mx-auto px-4 py-8">
        <GuildStatusStrip
          mode="guild"
          eyebrow="Quest board"
          title="Доска заданий включена в общий world-state и читает рынок как живую систему"
          description="Верхний слой сразу показывает объём рынка, срочность, активные фильтры и текущий режим просмотра. Ниже уже идут конкретные свитки и инструменты отбора."
          stats={[
            { label: "Контракты", value: total, note: "в доступном рынке", tone: "amber" },
            { label: "Urgent", value: urgentCount, note: "с высоким давлением", tone: urgentCount > 0 ? "red" : "slate" },
            { label: "Filters", value: activeFilterCount, note: "активные условия", tone: activeFilterCount > 0 ? "purple" : "slate" },
            { label: "Loaded", value: quests.length, note: "на текущем экране", tone: "cyan" },
          ]}
          signals={[
            { label: filters.status ? `${filters.status} scope` : 'any status', tone: filters.status ? 'amber' : 'slate' },
            { label: hasMore ? 'board extends further' : 'visible board complete', tone: hasMore ? 'cyan' : 'emerald' },
          ]}
          className="mb-6"
        />

        <SeasonFactionRail mode="quests" questCount={total} className="mb-6" />

        {/* Quest mode tabs: Standard vs Training vs Raid */}
        <div className="mb-6 flex gap-2 rounded-2xl border border-white/10 bg-black/30 p-1.5">
          <button
            onClick={() => { setQuestMode("standard"); setQuests([]); setPage(1); }}
            className={`flex-1 rounded-xl px-4 py-2.5 text-sm font-cinzel font-bold uppercase tracking-widest transition-all ${
              questMode === "standard"
                ? "bg-amber-900/50 text-amber-400 border border-amber-500/40 shadow-[0_0_10px_rgba(217,119,6,0.2)]"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            Контракты
          </button>
          <button
            onClick={() => { setQuestMode("training"); setQuests([]); setPage(1); }}
            className={`flex-1 rounded-xl px-4 py-2.5 text-sm font-cinzel font-bold uppercase tracking-widest transition-all ${
              questMode === "training"
                ? "bg-cyan-900/50 text-cyan-400 border border-cyan-500/40 shadow-[0_0_10px_rgba(34,211,238,0.2)]"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            PvE Тренировка
          </button>
          <button
            onClick={() => { setQuestMode("raid"); setQuests([]); setPage(1); }}
            className={`flex-1 rounded-xl px-4 py-2.5 text-sm font-cinzel font-bold uppercase tracking-widest transition-all ${
              questMode === "raid"
                ? "bg-violet-900/50 text-violet-400 border border-violet-500/40 shadow-[0_0_10px_rgba(139,92,246,0.2)]"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            ⚔️ Боевой Отряд
          </button>
        </div>

        {/* Заголовок */}
        <div className="mb-8 mt-6 rounded-3xl border border-purple-900/30 bg-gradient-to-br from-gray-950 via-gray-900 to-purple-950/30 p-6 md:p-8">
          <div className="flex flex-col gap-8 xl:flex-row xl:items-center xl:justify-between">
            <div className="max-w-2xl">
              <p className="text-xs uppercase tracking-[0.35em] text-amber-500/80">Quest Board</p>
              <h1 className="mt-3 text-4xl font-cinzel font-bold text-amber-500 drop-shadow-[0_0_10px_rgba(217,119,6,0.5)] uppercase tracking-widest flex items-center gap-4">
                <span className="text-3xl grayscale">📜</span>
                Доска Заданий
                <span className="text-3xl grayscale">⚔️</span>
              </h1>
              <p className="mt-4 text-sm leading-relaxed text-gray-400 md:text-base">
                Заключайте контракты, фильтруйте по бюджету и статусу, отслеживайте срочные миссии и быстро откликайтесь на лучшие заказы.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:min-w-[420px]">
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500">Контракты</div>
                <div className="mt-2 text-2xl font-bold text-white">{total}</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500">Срочные</div>
                <div className="mt-2 text-2xl font-bold text-red-300">{urgentCount}</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500">Фильтры</div>
                <div className="mt-2 text-2xl font-bold text-purple-300">{activeFilterCount}</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500">Статус</div>
                <div className="mt-2 text-sm font-bold text-amber-200">
                  {filters.status ? filters.status : "любой"}
                </div>
              </div>
            </div>
          </div>
        </div>

        <WorldPanel
          eyebrow="Selection control"
          title="Фильтрация и статус рынка объединены в один reusable panel"
          description="Эта секция заменяет одиночные summary-блоки и задаёт общий ритм перед списком квестов."
          tone="purple"
          className="mb-6"
          compact
          chips={[
            ...(filters.status ? [{ label: `status: ${filters.status}`, tone: 'amber' as const }] : []),
            ...(activeFilterCount > 0 ? [{ label: `filters: ${activeFilterCount}`, tone: 'purple' as const }] : [{ label: 'filters cleared', tone: 'slate' as const }]),
          ]}
        >
          <div className="flex flex-col gap-4 text-sm font-mono md:flex-row md:items-center md:justify-between">
            <p className="text-gray-400 uppercase tracking-widest">
              Актуальных контрактов:{" "}
              <span className="ml-2 font-bold text-amber-500">{total}</span>
            </p>
            <div className="flex flex-wrap items-center gap-3">
              {filters.status && (
                <div className="flex items-center gap-3">
                  <span className="text-xs uppercase tracking-wider text-purple-400/70">Метка Искателя:</span>
                  <QuestStatusBadge status={filters.status} size="sm" />
                </div>
              )}
            </div>
          </div>
        </WorldPanel>

        {/* Фильтры */}
        <WorldPanel
          eyebrow="Filter forge"
          title="Настройка поля охоты"
          description="Одинаковый card primitive держит форму панели фильтров и оставляет весь визуальный шум на содержимом, а не на случайных обвязках."
          tone="cyan"
          className="mb-8"
          compact
        >
          <QuestFilters onFilterChange={handleFilterChange} />
        </WorldPanel>

        {isAuthenticated && user?.role === "freelancer" && <RecommendedQuestPanel limit={4} />}

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
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mt-8">
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
    </ErrorBoundary>
  );
}
