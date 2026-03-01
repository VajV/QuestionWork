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
      // TODO: Реализовать endpoint assign
      showMessage("✅ Исполнитель назначен (функция в разработке)");
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
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />

      <div className="container mx-auto px-4 py-8">
        {/* Сообщение об успехе */}
        {successMessage && (
          <div className="mb-6 p-4 bg-green-900/30 border border-green-500/50 rounded-lg text-green-200">
            {successMessage}
          </div>
        )}

        {/* Заголовок и статус */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold mb-2">{quest.title}</h1>
            <p className="text-gray-400">
              Клиент: {quest.client_username} •{" "}
              {new Date(quest.created_at).toLocaleDateString("ru-RU")}
            </p>
          </div>
          <QuestStatusBadge status={quest.status} size="lg" showDescription />
        </div>

        {/* Подсказка по статусу */}
        <Card className="p-4 mb-6 bg-blue-900/20 border-blue-700/50">
          <p className="text-blue-200 text-sm">{getStatusHint()}</p>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Основная информация */}
          <div className="lg:col-span-2 space-y-6">
            {/* Описание */}
            <Card className="p-6">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span>📋</span> Описание
              </h2>
              <p className="text-gray-300 whitespace-pre-wrap">
                {quest.description}
              </p>
            </Card>

            {/* Требования */}
            <Card className="p-6">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span>🎯</span> Требования
              </h2>
              <div className="space-y-4">
                <div>
                  <p className="text-gray-400 text-sm mb-2">Требуемый грейд:</p>
                  <span
                    className={`px-3 py-1.5 rounded-lg bg-gradient-to-r font-bold ${
                      quest.required_grade === "novice"
                        ? "from-gray-500 to-gray-700"
                        : quest.required_grade === "junior"
                          ? "from-green-500 to-green-700"
                          : quest.required_grade === "middle"
                            ? "from-blue-500 to-blue-700"
                            : "from-purple-500 to-purple-700"
                    }`}
                  >
                    {quest.required_grade.toUpperCase()}
                  </span>
                </div>
                {quest.skills.length > 0 && (
                  <div>
                    <p className="text-gray-400 text-sm mb-2">Навыки:</p>
                    <div className="flex flex-wrap gap-2">
                      {quest.skills.map((skill) => (
                        <span
                          key={skill}
                          className="px-3 py-1.5 bg-gray-700 rounded-lg text-sm"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>

            {/* Отклики (для клиента) */}
            {isClient && applications.length > 0 && (
              <Card className="p-6">
                <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                  <span>📩</span> Отклики ({applications.length})
                </h2>
                <div className="space-y-3">
                  {applications.map((app) => (
                    <div
                      key={app.id}
                      className="p-4 bg-gray-800/50 rounded-lg border border-gray-700"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-bold">
                          {app.freelancer_username}
                        </span>
                        <span className="text-sm text-gray-400">
                          {app.freelancer_grade}
                        </span>
                      </div>
                      {app.cover_letter && (
                        <p className="text-gray-300 text-sm mb-2">
                          {app.cover_letter}
                        </p>
                      )}
                      {app.proposed_price && (
                        <p className="text-green-400 font-bold">
                          Предлагает: {app.proposed_price}₽
                        </p>
                      )}
                      {quest.status === "open" && (
                        <Button
                          onClick={() => handleAssign(app.freelancer_id)}
                          variant="primary"
                          className="mt-2 text-sm py-1"
                          disabled={actionLoading === "assign"}
                        >
                          ✅ Выбрать исполнителем
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Нет откликов */}
            {isClient &&
              quest.status === "open" &&
              applications.length === 0 && (
                <Card className="p-6 text-center">
                  <span className="text-4xl mb-2 block">📭</span>
                  <p className="text-gray-400">
                    Пока нет откликов на этот квест
                  </p>
                </Card>
              )}
          </div>

          {/* Боковая панель: Награды и действия */}
          <div className="space-y-6">
            {/* Награды */}
            <Card className="p-6">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span>💎</span> Награды
              </h2>
              <div className="space-y-4">
                <div className="text-center p-4 bg-green-900/30 border border-green-700 rounded-lg">
                  <div className="text-3xl font-bold text-green-400 mb-1">
                    💰 {quest.budget.toLocaleString("ru-RU")}₽
                  </div>
                  <div className="text-sm text-gray-400">Бюджет</div>
                </div>
                <div className="text-center p-4 bg-purple-900/30 border border-purple-700 rounded-lg">
                  <div className="text-3xl font-bold text-purple-400 mb-1">
                    ⚡ {quest.xp_reward} XP
                  </div>
                  <div className="text-sm text-gray-400">Опыт</div>
                </div>
                <div className="text-center p-4 bg-blue-900/30 border border-blue-700 rounded-lg">
                  <div className="text-sm text-gray-400">Валюта</div>
                  <div className="text-lg font-bold">{quest.currency}</div>
                </div>
              </div>
            </Card>

            {/* Действия */}
            <Card className="p-6">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span>⚡</span> Действия
              </h2>
              <div className="space-y-3">
                {/* Фрилансер: Откликнуться */}
                {!isClient && !isAssigned && quest.status === "open" && (
                  <>
                    {hasApplied ? (
                      <Button disabled variant="secondary" className="w-full">
                        ✅ Отклик отправлен
                      </Button>
                    ) : (
                      <Button
                        onClick={() => setShowApplyModal(true)}
                        variant="primary"
                        className="w-full"
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
                    className="w-full"
                    disabled={actionLoading !== null}
                  >
                    {actionLoading === "complete"
                      ? "⏳ Завершение..."
                      : "✅ Завершить квест"}
                  </Button>
                )}

                {/* Клиент: Подтвердить */}
                {isClient && quest.status === "completed" && (
                  <>
                    <Button
                      onClick={handleConfirm}
                      variant="primary"
                      className="w-full"
                      disabled={actionLoading !== null}
                    >
                      {actionLoading === "confirm"
                        ? "⏳ Подтверждение..."
                        : "✅ Подтвердить выполнение"}
                    </Button>
                    <Button
                      onClick={handleCancel}
                      variant="danger"
                      className="w-full"
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
                    className="w-full"
                    disabled={actionLoading !== null}
                  >
                    ❌ Отменить квест
                  </Button>
                )}

                {/* Статус для остальных */}
                {quest.status !== "open" && !isClient && (
                  <div className="text-center text-gray-400 py-2">
                    {quest.status === "in_progress" && "🔵 Квест в работе"}
                    {quest.status === "completed" && "🟣 Ожидает подтверждения"}
                    {quest.status === "cancelled" && "⚫ Квест отменён"}
                  </div>
                )}
              </div>
            </Card>
          </div>
        </div>

        {/* Кнопка назад */}
        <div className="mt-8">
          <Button onClick={() => router.back()} variant="secondary">
            ← Назад
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
