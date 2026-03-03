/**
 * Страница деталей квеста
 *
 * - Полное описание квеста
 * - Информация о клиенте
 * - Награды (бюджет + XP)
 * - Кнопки действий в зависимости от роли
 * - Список откликов (для клиента)
 * - Визуальные подсказки статуса
 */

"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  getQuest,
  applyToQuest,
  assignQuest,
  completeQuest,
  confirmQuest,
  cancelQuest,
  getQuestApplications,
  Quest,
  QuestApplication,
} from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import QuestStatusBadge from "@/components/quests/QuestStatusBadge";
import ApplyModal from "@/components/quests/ApplyModal";

export default function QuestDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { isAuthenticated, user } = useAuth();

  const questId = params.id as string;

  // Состояния
  const [quest, setQuest] = useState<Quest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [applications, setApplications] = useState<QuestApplication[]>([]);

  // Модальное окно
  const [showApplyModal, setShowApplyModal] = useState(false);

  // Действия
  type ActionType = "apply" | "complete" | "confirm" | "cancel" | "assign";
  const [actionLoading, setActionLoading] = useState<ActionType | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const messageTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Cleanup таймеров при unmount
  useEffect(() => {
    return () => {
      if (messageTimerRef.current) clearTimeout(messageTimerRef.current);
    };
  }, []);

  const showMessage = useCallback((msg: string) => {
    setSuccessMessage(msg);
    if (messageTimerRef.current) clearTimeout(messageTimerRef.current);
    messageTimerRef.current = setTimeout(() => setSuccessMessage(null), 5000);
  }, []);

  /**
   * Загрузка деталей квеста
   */
  useEffect(() => {
    async function loadQuest() {
      setLoading(true);
      setError(null);
      setSuccessMessage(null);

      try {
        const data = await getQuest(questId);
        setQuest(data);

        // Загружаем отклики если это клиент
        if (isAuthenticated && user && data.client_id === user.id) {
          try {
            const appsData = await getQuestApplications(questId);
            setApplications(appsData.applications);
          } catch (err) {
            console.error("Не удалось загрузить отклики:", err);
          }
        }
      } catch (err) {
        console.error("Ошибка загрузки квеста:", err);
        setError("Квест не найден или произошла ошибка");
      } finally {
        setLoading(false);
      }
    }

    loadQuest();
  }, [questId, isAuthenticated, user]);

  /**
   * Отклик на квест
   */
  const handleApply = async (data: {
    cover_letter?: string;
    proposed_price?: number;
  }) => {
    if (!quest) return;

    setActionLoading("apply");
    try {
      await applyToQuest(quest.id, data);
      showMessage("✅ Отклик успешно отправлен!");
      setShowApplyModal(false);
      // Обновляем квест
      const updated = await getQuest(quest.id);
      setQuest(updated);
    } catch (_err) {
      showMessage("❌ Ошибка при отправке отклика");
      throw _err;
    } finally {
      setActionLoading(null);
    }
  };

  /**
   * Завершение квеста (исполнитель)
   */
  const handleComplete = async () => {
    if (!quest) return;

    if (!confirm("Вы уверены, что завершили работу над квестом?")) return;

    setActionLoading("complete");
    try {
      const result = await completeQuest(quest.id);
      showMessage(`✅ ${result.message}\nXP награда: ${result.xp_earned}`);
      const updated = await getQuest(quest.id);
      setQuest(updated);
    } catch (_err) {
      showMessage("❌ Ошибка при завершении квеста");
    } finally {
      setActionLoading(null);
    }
  };

  /**
   * Подтверждение квеста (клиент)
   */
  const handleConfirm = async () => {
    if (!quest) return;

    if (
      !confirm(
        "Подтверждаете завершение квеста? Награда будет начислена исполнителю.",
      )
    )
      return;

    setActionLoading("confirm");
    try {
      const result = await confirmQuest(quest.id);
      showMessage(
        `✅ ${result.message}\n💰 ${result.money_reward}₽\n⚡ ${result.xp_reward} XP`,
      );
      const updated = await getQuest(quest.id);
      setQuest(updated);
    } catch (_err) {
      showMessage("❌ Ошибка при подтверждении");
    } finally {
      setActionLoading(null);
    }
  };

  /**
   * Отмена квеста (клиент)
   */
  const handleCancel = async () => {
    if (!quest) return;

    if (!confirm("Вы уверены, что хотите отменить квест?")) return;

    setActionLoading("cancel");
    try {
      await cancelQuest(quest.id);
      showMessage("✅ Квест отменён");
      const updated = await getQuest(quest.id);
      setQuest(updated);
    } catch (_err) {
      showMessage("❌ Ошибка при отмене");
    } finally {
      setActionLoading(null);
    }
  };

  /**
   * Назначение исполнителя (клиент)
   */
  const handleAssign = async (_freelancerId: string) => {
    if (!quest) return;

    if (!confirm(`Назначить исполнителя?`)) return;

    setActionLoading("assign");
    try {
      const result = await assignQuest(quest.id, _freelancerId);
      showMessage(`✅ ${result.message}`);
      const updated = await getQuest(quest.id);
      setQuest(updated);
      // Refresh applications list
      try {
        const appsData = await getQuestApplications(quest.id);
        setApplications(appsData.applications);
      } catch (_) {}
    } catch (_err) {
      showMessage("❌ Ошибка при назначении");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <Card className="p-12 text-center">
            <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-400">Загрузка квеста...</p>
          </Card>
        </div>
      </main>
    );
  }

  if (error || !quest) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <Card className="p-12 text-center">
            <span className="text-6xl mb-4 block">❌</span>
            <h2 className="text-2xl font-bold mb-4">Квест не найден</h2>
            <p className="text-gray-400 mb-6">
              {error || "Квест не существует или был удалён"}
            </p>
            <Button onClick={() => router.push("/quests")} variant="primary">
              📜 Вернуться к ленте
            </Button>
          </Card>
        </div>
      </main>
    );
  }

  const isClient = user?.id === quest.client_id;
  const isAssigned = quest.assigned_to === user?.id;
  const hasApplied = quest.applications.includes(user?.id || "");

  // Статусы для подсказок
  const getStatusHint = () => {
    if (quest.status === "open") {
      if (isClient)
        return "📢 Ожидает откликов — выберите исполнителя из списка";
      return "📢 Открыт — можете откликнуться";
    }
    if (quest.status === "in_progress") {
      if (isAssigned)
        return "⚡ В работе — выполните квест и нажмите 'Завершить'";
      if (isClient) return "⚡ В работе — фрилансер выполняет задачу";
      return "⚡ В работе — назначен исполнитель";
    }
    if (quest.status === "completed") {
      if (isClient)
        return "🟣 Готов к проверке — подтвердите выполнение для выплаты награды";
      return "🟣 Ожидает подтверждения клиента";
    }
    return "❌ Квест отменён";
  };

  return (
    <main className="min-h-screen bg-gray-950 text-gray-200 font-inter">
      <Header />

      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Сообщение об успехе */}
        {successMessage && (
          <div className="mb-6 p-4 bg-green-950/40 border border-green-700/50 rounded text-green-400 font-mono text-sm shadow-[0_0_10px_rgba(34,197,94,0.2)]">
            ✨ {successMessage}
          </div>
        )}

        {/* Заголовок и статус */}
        <div className="flex flex-col md:flex-row md:items-start justify-between mb-8 gap-6">
          <div className="flex-1">
            <h1 className="text-3xl md:text-4xl font-cinzel font-bold mb-3 text-gray-100">{quest.title}</h1>
            <p className="text-gray-500 font-mono text-sm">
              <span className="text-gray-400 uppercase tracking-widest text-xs mr-2">Заказчик:</span> 
              <span className="text-amber-500 mr-4">{quest.client_username}</span>
              <span className="text-gray-400 uppercase tracking-widest text-xs mr-2">Создано:</span>
              <span className="text-gray-300">{new Date(quest.created_at).toLocaleDateString("ru-RU")}</span>
            </p>
          </div>
          <div className="shrink-0 bg-black/40 p-3 rounded border border-purple-900/30">
            <QuestStatusBadge status={quest.status} size="lg" showDescription />
          </div>
        </div>

        {/* Подсказка по статусу */}
        <div className="p-4 mb-8 bg-blue-950/20 border border-blue-900/50 rounded font-mono text-sm text-blue-300 shadow-inner">
          <span className="mr-2">💡</span> {getStatusHint()}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Основная информация */}
          <div className="lg:col-span-2 space-y-8">
            {/* Описание */}
            <Card className="p-0 border-none bg-transparent">
              <div className="rpg-card p-6 md:p-8">
                <h2 className="text-xl font-cinzel font-bold mb-6 text-amber-500 flex items-center gap-3 border-b border-amber-900/30 pb-3">
                  <span className="grayscale opacity-70">📜</span> Детали Контракта
                </h2>
                <p className="text-gray-300 whitespace-pre-wrap leading-relaxed">
                  {quest.description}
                </p>
              </div>
            </Card>

            {/* Требования */}
            <Card className="p-0 border-none bg-transparent">
              <div className="rpg-card p-6 md:p-8">
                <h2 className="text-xl font-cinzel font-bold mb-6 text-purple-400 flex items-center gap-3 border-b border-purple-900/30 pb-3">
                  <span className="grayscale opacity-70">🎯</span> Требования Гильдии
                </h2>
                <div className="space-y-6">
                  <div>
                    <p className="text-gray-500 text-xs uppercase tracking-widest mb-3">Минимальный Ранг:</p>
                    <span
                      className={`px-4 py-1.5 rounded font-cinzel font-bold tracking-wider text-sm shadow-inner inline-block ${
                        quest.required_grade === "novice"
                          ? "bg-gray-800 text-gray-300 border border-gray-600"
                          : quest.required_grade === "junior"
                            ? "bg-green-950 text-green-400 border border-green-700"
                            : quest.required_grade === "middle"
                              ? "bg-blue-950 text-blue-400 border border-blue-700"
                              : "bg-purple-950 text-purple-300 border border-purple-700 shadow-[0_0_10px_rgba(168,85,247,0.3)]"
                      }`}
                    >
                      {quest.required_grade.toUpperCase()}
                    </span>
                  </div>
                  {quest.skills.length > 0 && (
                    <div>
                      <p className="text-gray-500 text-xs uppercase tracking-widest mb-3">Специализация:</p>
                      <div className="flex flex-wrap gap-2">
                        {quest.skills.map((skill) => (
                          <span
                            key={skill}
                            className="px-3 py-1 bg-black/60 border border-gray-800 rounded font-mono text-sm text-gray-300"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </Card>

            {/* Отклики (для клиента) */}
            {isClient && applications.length > 0 && (
              <Card className="p-0 border-none bg-transparent">
                <div className="rpg-card p-6 md:p-8">
                  <h2 className="text-xl font-cinzel font-bold mb-6 text-gray-100 flex items-center gap-3 border-b border-gray-800 pb-3">
                    <span className="grayscale opacity-70">📩</span> Отклики Искателей ({applications.length})
                  </h2>
                  <div className="space-y-4">
                    {applications.map((app) => (
                      <div
                        key={app.id}
                        className="p-5 bg-black/40 rounded border border-purple-900/30 shadow-inner"
                      >
                        <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-800/50">
                          <span className="font-cinzel font-bold text-amber-500 text-lg">
                            {app.freelancer_username}
                          </span>
                          <span className="text-sm font-mono text-gray-400 bg-gray-900 px-2 py-1 rounded border border-gray-800">
                            {app.freelancer_grade}
                          </span>
                        </div>

                        {app.cover_letter && (
                          <div className="bg-black/60 p-4 rounded text-sm text-gray-300 font-inter border-l-2 border-purple-800 italic mb-4">
                            "{app.cover_letter}"
                          </div>
                        )}

                        {app.proposed_price && (
                          <div className="mb-4 text-sm font-mono flex items-center gap-2">
                            <span className="text-gray-500 uppercase tracking-widest text-xs">Запрашиваемая награда:</span>
                            <span className="text-amber-500 font-bold">{app.proposed_price.toLocaleString("ru-RU")}₽</span>
                          </div>
                        )}

                        {quest.status === "open" && (
                          <Button
                            onClick={() => handleAssign(app.freelancer_id)}
                            variant="primary"
                            className="w-full text-sm py-2 shadow-[0_0_10px_rgba(217,119,6,0.2)]"
                            disabled={actionLoading === "assign"}
                          >
                            🤝 Назначить Исполнителем
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            )}

            {/* Нет откликов */}
            {isClient &&
              quest.status === "open" &&
              applications.length === 0 && (
                <Card className="p-0 border-none bg-transparent">
                  <div className="rpg-card p-10 text-center opacity-80">
                    <span className="text-5xl mb-4 block grayscale opacity-50">📭</span>
                    <p className="text-gray-400 font-inter">
                      Пока нет откликов на этот контракт
                    </p>
                  </div>
                </Card>
              )}
          </div>

          {/* Боковая панель: Награды и действия */}
          <div className="space-y-8">
            {/* Награды */}
            <Card className="p-0 border-none bg-transparent">
              <div className="rpg-card p-6 md:p-8">
                <h2 className="text-xl font-cinzel font-bold mb-6 text-amber-500 flex items-center gap-3 border-b border-amber-900/30 pb-3">
                  <span className="grayscale opacity-70">💎</span> Награда
                </h2>
                <div className="space-y-4 font-mono">
                  <div className="text-center p-5 bg-gradient-to-b from-amber-950/40 to-black/60 border border-amber-700/50 rounded shadow-[inset_0_0_15px_rgba(217,119,6,0.1)] relative overflow-hidden">
                    <div className="absolute -right-4 -top-4 text-6xl opacity-10">💰</div>
                    <div className="text-3xl font-bold text-amber-500 mb-2 relative z-10 drop-shadow-[0_0_8px_rgba(217,119,6,0.8)]">
                      {quest.budget.toLocaleString("ru-RU")}₽
                    </div>
                    <div className="text-xs text-gray-500 uppercase tracking-widest relative z-10">Золото</div>
                  </div>
                  <div className="text-center p-5 bg-gradient-to-b from-purple-950/40 to-black/60 border border-purple-700/50 rounded shadow-[inset_0_0_15px_rgba(168,85,247,0.1)] relative overflow-hidden">
                    <div className="absolute -right-4 -top-4 text-6xl opacity-10">⚡</div>
                    <div className="text-3xl font-bold text-purple-400 mb-2 relative z-10 drop-shadow-[0_0_8px_rgba(168,85,247,0.8)]">
                      {quest.xp_reward} XP
                    </div>
                    <div className="text-xs text-gray-500 uppercase tracking-widest relative z-10">Опыт</div>
                  </div>
                  <div className="text-center p-4 bg-gray-900/50 border border-gray-800 rounded">
                    <div className="text-xs text-gray-500 uppercase tracking-widest mb-1">Валюта Королевства</div>
                    <div className="text-lg font-bold text-gray-300">{quest.currency}</div>
                  </div>
                </div>
              </div>
            </Card>

            {/* Действия */}
            <Card className="p-0 border-none bg-transparent">
              <div className="rpg-card p-6 md:p-8">
                <h2 className="text-xl font-cinzel font-bold mb-6 text-gray-100 flex items-center gap-3 border-b border-gray-800 pb-3">
                  <span className="grayscale opacity-70">⚔️</span> Действия
                </h2>
                <div className="space-y-4">
                  {/* Фрилансер: Откликнуться */}
                  {!isClient && !isAssigned && quest.status === "open" && (
                    <>
                      {hasApplied ? (
                        <Button disabled variant="secondary" className="w-full opacity-70 border-gray-700 font-cinzel tracking-wider">
                          ✅ Отклик отправлен
                        </Button>
                      ) : (
                        <Button
                          onClick={() => setShowApplyModal(true)}
                          variant="primary"
                          className="w-full font-cinzel tracking-wider shadow-[0_0_15px_rgba(217,119,6,0.3)] hover:shadow-[0_0_25px_rgba(217,119,6,0.5)]"
                          disabled={!isAuthenticated || actionLoading !== null}
                        >
                          📩 Откликнуться
                        </Button>
                      )}
                    </>
                  )}

                  {/* Исполнитель: Завершить */}
                  {isAssigned && quest.status === "in_progress" && (
                    <Button
                      onClick={handleComplete}
                      variant="primary"
                      className="w-full font-cinzel tracking-wider"
                      disabled={actionLoading !== null}
                    >
                      {actionLoading === "complete"
                        ? "⏳ Завершение..."
                        : "✅ Завершить Миссию"}
                    </Button>
                  )}

                  {/* Клиент: Подтвердить */}
                  {isClient && quest.status === "completed" && (
                    <>
                      <Button
                        onClick={handleConfirm}
                        variant="primary"
                        className="w-full font-cinzel tracking-wider"
                        disabled={actionLoading !== null}
                      >
                        {actionLoading === "confirm"
                          ? "⏳ Подтверждение..."
                          : "💰 Подтвердить выполнение"}
                      </Button>
                      <Button
                        onClick={handleCancel}
                        variant="danger"
                        className="w-full font-cinzel tracking-wider mt-2 border-red-900/50 hover:border-red-500/50 bg-red-950/30 text-red-400 hover:bg-red-900/40"
                        disabled={actionLoading !== null}
                      >
                        ❌ Отменить квест
                      </Button>
                    </>
                  )}

                  {/* Клиент: Квест открыт */}
                  {isClient && quest.status === "open" && (
                    <Button
                      onClick={handleCancel}
                      variant="danger"
                      className="w-full font-cinzel tracking-wider border-red-900/50 hover:border-red-500/50 bg-red-950/30 text-red-400 hover:bg-red-900/40"
                      disabled={actionLoading !== null}
                    >
                      ❌ Отменить квест
                    </Button>
                  )}

                  {/* Статус для остальных */}
                  {quest.status !== "open" && !isClient && (
                    <div className="text-center text-gray-500 font-mono text-sm py-3 border border-gray-800 bg-gray-900/30 rounded">
                      {quest.status === "in_progress" && "🔵 Квест в работе"}
                      {quest.status === "completed" && "🟣 Ожидает подтверждения"}
                      {quest.status === "cancelled" && "⚫ Квест отменён"}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </div>
        </div>

        {/* Кнопка назад */}
        <div className="mt-12 text-center md:text-left">
          <Button onClick={() => router.back()} variant="secondary" className="border-purple-900/50 hover:border-purple-500/50 font-cinzel tracking-wider px-8">
            ← Вернуться назад
          </Button>
        </div>
      </div>

      {/* Модальное окно отклика */}
      {showApplyModal && (
        <ApplyModal
          questTitle={quest.title}
          onSubmit={handleApply}
          onClose={() => setShowApplyModal(false)}
        />
      )}
    </main>
  );
}
