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
import dynamic from "next/dynamic";
import { useRouter, useParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getBlockReason, formatXpBadge, calcXpMultiplier } from "@/lib/classEngine";
import { UserClassInfo } from "@/lib/api";
import {
  getQuest,
  applyToQuest,
  assignQuest,
  startQuest,
  completeQuest,
  requestQuestRevision,
  confirmQuest,
  cancelQuest,
  getQuestApplications,
  getQuestHistory,
  publishQuest,
  getReviewStatus,
  getAbilities,
  getApiErrorMessage,
  acceptTrainingQuest,
  completeTrainingQuest,
  getRaidParty,
  joinRaidQuest,
  leaveRaidQuest,
  startRaidQuest,
  completeRaidQuest,
  getChainDetail,
  Quest,
  QuestApplication,
  QuestStatusHistoryEntry,
  Review,
  QuestCompletionData,
  QuestRevisionRequestData,
  AbilityInfo,
  RaidPartyResponse,
  RAID_ROLE_SLOTS,
  ChainDetailResponse,
} from "@/lib/api";
import { ActiveAbilityBadge } from "@/components/rpg/AbilityPanel";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import SeasonFactionRail from "@/components/ui/SeasonFactionRail";
import WorldPanel from "@/components/ui/WorldPanel";
import QuestStatusBadge from "@/components/quests/QuestStatusBadge";

const ApplyModal = dynamic(() => import("@/components/quests/ApplyModal"), { ssr: false });
const QuestChat = dynamic(() => import("@/components/quests/QuestChat"), { ssr: false });
const ReviewModal = dynamic(() => import("@/components/quests/ReviewModal"), { ssr: false });
const DisputeModal = dynamic(() => import("@/components/quests/DisputeModal"), { ssr: false });
const RecommendedTalentRail = dynamic(() => import("@/components/marketplace/RecommendedTalentRail"), { ssr: false });
const RepeatHireCard = dynamic(() => import("@/components/growth/RepeatHireCard"), { ssr: false });

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
  const [history, setHistory] = useState<QuestStatusHistoryEntry[]>([]);
  const [abilities, setAbilities] = useState<AbilityInfo[]>([]);

  // Модальное окно
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [showDisputeModal, setShowDisputeModal] = useState(false);
  const [deliveryNote, setDeliveryNote] = useState("");
  const [deliveryUrl, setDeliveryUrl] = useState("");
  const [revisionReason, setRevisionReason] = useState("");
  const [hasReviewed, setHasReviewed] = useState(false);
  const [reviewCheckLoading, setReviewCheckLoading] = useState(false);

  // Raid state
  const [raidParty, setRaidParty] = useState<RaidPartyResponse | null>(null);
  const [selectedRaidRole, setSelectedRaidRole] = useState<string>("any");

  // Chain state
  const [chainDetail, setChainDetail] = useState<ChainDetailResponse | null>(null);

  // Действия
  type ActionType = "apply" | "complete" | "confirm" | "cancel" | "assign" | "start" | "revision" | "publish" | "training_accept" | "training_complete" | "raid_join" | "raid_leave" | "raid_start" | "raid_complete";
  const [actionLoading, setActionLoading] = useState<ActionType | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const messageTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Cleanup таймеров при unmount
  useEffect(() => {
    return () => {
      if (messageTimerRef.current) clearTimeout(messageTimerRef.current);
    };
  }, []);

  // Load active abilities for the ability XP indicator (non-blocking)
  useEffect(() => {
    if (!isAuthenticated || user?.role === "client") return;
    getAbilities().then(setAbilities).catch((e) => console.warn("Failed to load abilities", e));
  }, [isAuthenticated, user?.role]);

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
        setDeliveryNote(data.delivery_note || "");
        setDeliveryUrl(data.delivery_url || "");
        setRevisionReason(data.revision_reason || "");

        // Загружаем отклики если это клиент
        if (isAuthenticated && user && data.client_id === user.id) {
          try {
            const appsData = await getQuestApplications(questId);
            setApplications(appsData.applications);
          } catch (err) {
            console.error("Не удалось загрузить отклики:", err);
          }
        }

        if (user && (user.id === data.client_id || user.id === data.assigned_to || user.role === "admin")) {
          try {
            const historyData = await getQuestHistory(questId);
            setHistory(historyData.history);
          } catch (err) {
            console.error("Не удалось загрузить историю статусов:", err);
            setHistory([]);
          }
        } else {
          setHistory([]);
        }

        // Load raid party if this is a raid quest
        if (data.quest_type === "raid") {
          try {
            const party = await getRaidParty(questId);
            setRaidParty(party);
          } catch (e) {
            console.warn("Failed to load raid party", e);
            setRaidParty(null);
          }
        }

        // Load chain detail if this quest belongs to a chain
        if (data.chain_id) {
          try {
            const detail = await getChainDetail(data.chain_id);
            setChainDetail(detail);
          } catch (e) {
            console.warn("Failed to load chain detail", e);
            setChainDetail(null);
          }
        }
      } catch (err: unknown) {
        console.error("Ошибка загрузки квеста:", err);
        setError(getApiErrorMessage(err, "Квест не найден или произошла ошибка"));
      } finally {
        setLoading(false);
      }
    }

    loadQuest();
  }, [questId, isAuthenticated, user]);

  useEffect(() => {
    let cancelled = false;

    async function loadReviewStatus() {
      if (!quest || !isAuthenticated || !user) {
        setHasReviewed(false);
        setReviewCheckLoading(false);
        return;
      }

      const userIsParticipant = user.id === quest.client_id || user.id === quest.assigned_to;
      if (quest.status !== "confirmed" || !userIsParticipant) {
        setHasReviewed(false);
        setReviewCheckLoading(false);
        return;
      }

      setReviewCheckLoading(true);
      try {
        const result = await getReviewStatus(quest.id);
        if (!cancelled) {
          setHasReviewed(result.has_reviewed);
        }
      } catch {
        if (!cancelled) {
          setHasReviewed(false);
        }
      } finally {
        if (!cancelled) {
          setReviewCheckLoading(false);
        }
      }
    }

    loadReviewStatus();

    return () => {
      cancelled = true;
    };
  }, [quest, isAuthenticated, user]);

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
      const result = await applyToQuest(quest.id, data);
      showMessage("✅ Отклик успешно отправлен!");
      setShowApplyModal(false);
      setQuest((prev) => {
        if (!prev) {
          return prev;
        }

        return {
          ...prev,
          applications: prev.applications.includes(result.application.freelancer_id)
            ? prev.applications
            : [...prev.applications, result.application.freelancer_id],
        };
      });
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

    const payload: QuestCompletionData = {
      delivery_note: deliveryNote.trim() || undefined,
      delivery_url: deliveryUrl.trim() || undefined,
    };

    if (!payload.delivery_note && !payload.delivery_url) {
      showMessage("❌ Добавьте описание результата или ссылку перед сдачей");
      return;
    }

    setActionLoading("complete");
    try {
      const result = await completeQuest(quest.id, payload);
      showMessage(`✅ ${result.message}\nXP награда: ${result.xp_earned}`);
      setQuest(result.quest);
      setDeliveryNote(result.quest.delivery_note || "");
      setDeliveryUrl(result.quest.delivery_url || "");
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
      setQuest(result.quest);
    } catch (_err) {
      showMessage("❌ Ошибка при подтверждении");
    } finally {
      setActionLoading(null);
    }
  };

  /**
   * Запрос доработок (клиент)
   */
  const handleRequestRevision = async () => {
    if (!quest) return;

    const payload: QuestRevisionRequestData = {
      revision_reason: revisionReason.trim(),
    };

    if (payload.revision_reason.length < 10) {
      showMessage("❌ Опишите, что нужно исправить, минимум в 10 символов");
      return;
    }

    if (!confirm("Отправить квест на доработку исполнителю?")) return;

    setActionLoading("revision");
    try {
      const result = await requestQuestRevision(quest.id, payload);
      showMessage(`✅ ${result.message}`);
      setQuest(result.quest);
      setRevisionReason(result.quest.revision_reason || "");
    } catch (_err) {
      showMessage("❌ Ошибка при запросе доработок");
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
      const result = await cancelQuest(quest.id);
      showMessage(`✅ ${result.message}`);
      setQuest(result.quest);
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
      setQuest(result.quest);
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

  /**
   * Старт квеста (назначенный исполнитель)
   */
  const handleStart = async () => {
    if (!quest) return;

    if (!confirm("Начать работу по этому контракту?")) return;

    setActionLoading("start");
    try {
      const result = await startQuest(quest.id);
      showMessage(`✅ ${result.message}`);
      setQuest(result.quest);
    } catch (_err) {
      showMessage("❌ Ошибка при старте квеста");
    } finally {
      setActionLoading(null);
    }
  };

  const handleReviewSubmitted = useCallback((review: Review) => {
    setHasReviewed(true);
    setShowReviewModal(false);
    showMessage(
      review.xp_bonus && review.xp_bonus > 0
        ? `✅ Отзыв отправлен! Бонус: +${review.xp_bonus} XP`
        : "✅ Отзыв отправлен!",
    );
  }, [showMessage]);

  const handlePublish = async () => {
    if (!quest) return;
    if (!confirm("Опубликовать черновик на бирже?")) return;

    setActionLoading("publish");
    try {
      const result = await publishQuest(quest.id);
      showMessage(`✅ ${result.message}`);
      setQuest(result.quest);
      try {
        const historyData = await getQuestHistory(quest.id);
        setHistory(historyData.history);
      } catch (e) {
        console.warn("Failed to refresh quest history after publish", e);
      }
    } catch (_err) {
      showMessage("❌ Ошибка при публикации черновика");
    } finally {
      setActionLoading(null);
    }
  };

  const handleTrainingAccept = async () => {
    if (!quest) return;
    if (!confirm("Принять и начать тренировочный квест?")) return;
    setActionLoading("training_accept");
    try {
      const updated = await acceptTrainingQuest(quest.id);
      showMessage("✅ Тренировочный квест принят! Приступайте к выполнению.");
      setQuest(updated);
    } catch (_err) {
      showMessage("❌ Не удалось принять тренировочный квест");
    } finally {
      setActionLoading(null);
    }
  };

  const handleTrainingComplete = async () => {
    if (!quest) return;
    if (!confirm("Завершить тренировочный квест и получить XP?")) return;
    setActionLoading("training_complete");
    try {
      const result = await completeTrainingQuest(quest.id);
      showMessage(
        `✅ ${result.message}\n⚡ +${result.xp_reward} XP (сегодня: ${result.daily_xp_earned}/${result.daily_xp_cap})`
      );
      setQuest(result.quest);
    } catch (_err) {
      showMessage("❌ Ошибка при завершении тренировки");
    } finally {
      setActionLoading(null);
    }
  };

  // ─── Raid handlers ───

  const handleRaidJoin = async () => {
    if (!quest) return;
    setActionLoading("raid_join");
    try {
      const party = await joinRaidQuest(quest.id, selectedRaidRole);
      setRaidParty(party);
      setQuest((prev) => prev ? { ...prev, raid_current_members: party.current_members } : prev);
      showMessage("✅ Вы вступили в боевой отряд!");
    } catch (_err) {
      showMessage("❌ Не удалось вступить в отряд");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRaidLeave = async () => {
    if (!quest) return;
    if (!confirm("Покинуть боевой отряд?")) return;
    setActionLoading("raid_leave");
    try {
      const party = await leaveRaidQuest(quest.id);
      setRaidParty(party);
      setQuest((prev) => prev ? { ...prev, raid_current_members: party.current_members } : prev);
      showMessage("✅ Вы покинули отряд");
    } catch (_err) {
      showMessage("❌ Ошибка при выходе из отряда");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRaidStart = async () => {
    if (!quest) return;
    if (!confirm("Начать рейд? Набор будет закрыт.")) return;
    setActionLoading("raid_start");
    try {
      const updated = await startRaidQuest(quest.id);
      setQuest(updated);
      showMessage("✅ Рейд начался! Отряд в сборе.");
    } catch (_err) {
      showMessage("❌ Не удалось начать рейд");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRaidComplete = async () => {
    if (!quest) return;
    if (!confirm("Пометить рейд как выполненный?")) return;
    setActionLoading("raid_complete");
    try {
      const result = await completeRaidQuest(quest.id);
      showMessage(`✅ ${result.message}`);
      setQuest(result.quest);
    } catch (_err) {
      showMessage("❌ Ошибка при завершении рейда");
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
    const assignedApplication = applications.find((app) => app.freelancer_id === quest.assigned_to);
    
    // Class Engine Constraints
    const blockReason = (!isClient && user?.character_class) 
      ? getBlockReason(user as unknown as UserClassInfo, quest) 
      : null;

  const reviewTargetId = isClient ? quest.assigned_to : isAssigned ? quest.client_id : null;
  const reviewTargetName = isClient
    ? assignedApplication?.freelancer_username || "исполнителя"
    : isAssigned
      ? quest.client_username || "заказчика"
      : "";
  const canOpenChat = Boolean(
    user?.id &&
      (isClient || isAssigned) &&
      ["assigned", "in_progress", "completed", "revision_requested", "confirmed"].includes(quest.status),
  );
  const canViewHistory = Boolean(user?.id && (isClient || isAssigned || user.role === "admin"));

  // Статусы для подсказок
  const getStatusHint = () => {
    if (quest.status === "draft") {
      if (isClient) return "📝 Черновик сохранён — доведите описание до ума и опубликуйте, когда будете готовы";
      return "📝 Черновик недоступен для чужих пользователей";
    }
    if (quest.status === "open") {
      if (isClient)
        return "📢 Ожидает откликов — выберите исполнителя из списка";
      return "📢 Открыт — можете откликнуться";
    }
    if (quest.status === "assigned") {
      if (isAssigned)
        return "📌 Вас выбрали исполнителем — подтвердите старт работы";
      if (isClient) return "📌 Исполнитель выбран — ожидается старт работы";
      return "📌 Исполнитель уже выбран";
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
    if (quest.status === "revision_requested") {
      if (isAssigned)
        return "🛠️ Клиент запросил доработки — внесите правки и повторно сдайте результат";
      if (isClient) return "🛠️ Доработка запрошена — ожидается повторная сдача";
      return "🛠️ Квест отправлен на доработку";
    }
    if (quest.status === "confirmed") {
      return "🏆 Контракт успешно завершён и подтверждён";
    }
    return "❌ Квест отменён";
  };

  return (
    <main className="guild-world-shell min-h-screen bg-gray-950 text-gray-200 font-inter">
      <Header />

      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Сообщение об успехе */}
        {successMessage && (
          <div className="mb-6 p-4 bg-green-950/40 border border-green-700/50 rounded text-green-400 font-mono text-sm shadow-[0_0_10px_rgba(34,197,94,0.2)]">
            ✨ {successMessage}
          </div>
        )}

        <GuildStatusStrip
          mode="guild"
          eyebrow="Quest dossier"
          title="Карточка квеста получила общий world-state и контроль качества сверху"
          description="Вместо локального hero-блока у страницы теперь есть единый guild-layer с денежным, статусным и коммуникационным контекстом."
          stats={[
            { label: "Budget", value: quest.quest_type === "training" ? "PvE" : quest.quest_type === "raid" ? "Рейд" : `${quest.budget.toLocaleString("ru-RU")}₽`, note: quest.quest_type === "training" ? "тренировочный" : quest.quest_type === "raid" ? `${quest.raid_current_members}/${quest.raid_max_members ?? "?"} в отряде` : "награда контракта", tone: "amber" },
            { label: "XP", value: quest.xp_reward, note: "опыт за закрытие", tone: "purple" },
            { label: "Apps", value: quest.applications.length, note: "отклики", tone: "cyan" },
            { label: "History", value: history.length, note: "события статуса", tone: canViewHistory ? "emerald" : "slate" },
          ]}
          signals={[
            { label: quest.status, tone: quest.status === 'confirmed' ? 'emerald' : quest.status === 'revision_requested' ? 'amber' : 'purple' },
            { label: canOpenChat ? 'chat unlocked' : 'chat locked', tone: canOpenChat ? 'cyan' : 'slate' },
          ]}
          className="mb-6"
        />

        <SeasonFactionRail mode="dossier" questCount={history.length} className="mb-6" />

        <WorldPanel
          eyebrow="Status pressure"
          title="Подсказка статуса и текущий режим контракта вынесены в отдельный reusable panel"
          description="Это уменьшает визуальный шум в hero-блоке и делает состояние квеста читаемым раньше детального описания."
          tone="cyan"
          className="mb-6"
          compact
        >
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="font-mono text-sm text-blue-300">
              <span className="mr-2">💡</span> {getStatusHint()}
            </div>
            <div className="shrink-0 rounded-xl border border-purple-900/30 bg-black/30 p-3">
              <QuestStatusBadge status={quest.status} size="lg" showDescription />
            </div>
          </div>
        </WorldPanel>

        {/* Заголовок и статус */}
        <div className="mb-8 rounded-3xl border border-purple-900/30 bg-gradient-to-br from-gray-950 via-gray-900 to-purple-950/20 p-6 md:p-8">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
            <div className="flex-1">
              <p className="text-xs uppercase tracking-[0.35em] text-amber-500/80">Quest dossier</p>
              <h1 className="mt-3 text-3xl md:text-4xl font-cinzel font-bold text-gray-100">{quest.title}</h1>
              <p className="mt-4 text-gray-500 font-mono text-sm flex flex-wrap gap-x-4 gap-y-2">
                <span>
                  <span className="text-gray-400 uppercase tracking-widest text-xs mr-2">Заказчик:</span>
                  <span className="text-amber-500">{quest.client_username}</span>
                </span>
                <span>
                  <span className="text-gray-400 uppercase tracking-widest text-xs mr-2">Создано:</span>
                  <span className="text-gray-300">{new Date(quest.created_at).toLocaleDateString("ru-RU")}</span>
                </span>
              </p>
              <p className="mt-4 max-w-3xl text-sm leading-relaxed text-gray-400">
                Полный свиток задания с наградой, требованиями, статусом выполнения и переговорами между участниками.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 xl:w-[380px]">
              <div className="rounded-2xl border border-amber-500/20 bg-amber-950/10 p-4 text-center">
                <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500">Золото</div>
                <div className="mt-2 text-2xl font-bold text-amber-300">{quest.budget.toLocaleString("ru-RU")}₽</div>
              </div>
              <div className="rounded-2xl border border-purple-500/20 bg-purple-950/10 p-4 text-center">
                <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500">XP</div>
                <div className="mt-2 text-2xl font-bold text-purple-300">{quest.xp_reward}</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-center">
                <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500">Отклики</div>
                <div className="mt-2 text-2xl font-bold text-white">{quest.applications.length}</div>
              </div>
            </div>
          </div>
          {/* Active ability bonus indicator */}
          {abilities.some((a) => a.is_active) && (
            <div className="mt-3">
              <ActiveAbilityBadge abilities={abilities} />
            </div>
          )}
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

            {/* Raid party panel */}
            {quest.quest_type === "raid" && raidParty && (
              <Card className="p-0 border-none bg-transparent">
                <div className="rpg-card p-6 md:p-8">
                  <h2 className="text-xl font-cinzel font-bold mb-6 text-violet-400 flex items-center gap-3 border-b border-violet-900/30 pb-3">
                    <span className="grayscale opacity-70">⚔️</span> Боевой Отряд ({raidParty.current_members}/{raidParty.max_members})
                  </h2>
                  <div className="space-y-4">
                    {/* Participants */}
                    {raidParty.participants.length > 0 ? (
                      <div className="space-y-2">
                        {raidParty.participants.map((p) => (
                          <div key={p.user_id} className="flex items-center justify-between rounded-xl border border-violet-900/30 bg-violet-950/10 p-3">
                            <div className="flex items-center gap-3">
                              <div className="h-8 w-8 rounded-full bg-violet-900/40 border border-violet-700/50 flex items-center justify-center text-sm">
                                {p.role_slot === "leader" ? "👑" : "⚔️"}
                              </div>
                              <div>
                                <div className="text-sm font-bold text-gray-200">{p.username}</div>
                                <div className="text-xs text-violet-400 uppercase tracking-wider">{p.role_slot}</div>
                              </div>
                            </div>
                            <div className="text-xs text-gray-500 font-mono">
                              {new Date(p.joined_at).toLocaleDateString("ru-RU")}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-4 text-gray-500 text-sm">Отряд пока пуст — ожидается набор</div>
                    )}

                    {/* Open slots */}
                    {raidParty.open_slots > 0 && (
                      <div className="text-center text-sm text-violet-300 font-mono py-2 border border-violet-800/30 rounded-lg bg-violet-950/20">
                        {raidParty.open_slots} свободных мест
                      </div>
                    )}

                    {/* Role slots info */}
                    {raidParty.role_slots && raidParty.role_slots.length > 0 && (
                      <div>
                        <div className="text-xs text-gray-500 uppercase tracking-widest mb-2">Роли в отряде:</div>
                        <div className="flex flex-wrap gap-2">
                          {raidParty.role_slots.map((slot, i) => {
                            const taken = raidParty.participants.some((p) => p.role_slot === slot);
                            return (
                              <span key={`${slot}-${i}`} className={`text-xs font-mono px-2 py-1 rounded border ${taken ? "bg-violet-950/40 border-violet-700/50 text-violet-300" : "bg-black/30 border-gray-700 text-gray-500"}`}>
                                {slot} {taken ? "✓" : ""}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            )}

            {/* Legendary quest chain progress panel */}
            {chainDetail && (
              <Card className="p-0 border-none bg-transparent">
                <div className="rpg-card p-6 md:p-8">
                  <h2 className="text-xl font-cinzel font-bold mb-6 text-amber-400 flex items-center gap-3 border-b border-amber-900/30 pb-3">
                    <span className="grayscale opacity-70">🔗</span> Легендарная цепочка: {chainDetail.chain.title}
                  </h2>
                  <p className="text-sm text-gray-400 mb-4">{chainDetail.chain.description}</p>

                  {/* Steps progress */}
                  <div className="space-y-2 mb-4">
                    {chainDetail.steps.map((step, idx) => {
                      const stepQuest = chainDetail.quests[idx];
                      const userStep = chainDetail.user_progress?.current_step ?? 0;
                      const isDone = userStep >= step.step_order;
                      const isCurrent = quest.id === step.quest_id;
                      return (
                        <div
                          key={step.id}
                          className={`flex items-center gap-3 rounded-xl border p-3 transition-all ${
                            isCurrent
                              ? "border-amber-500/50 bg-amber-950/20"
                              : isDone
                              ? "border-emerald-700/40 bg-emerald-950/10"
                              : "border-gray-700/30 bg-black/20"
                          }`}
                        >
                          <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                            isDone ? "bg-emerald-600 text-white" : isCurrent ? "bg-amber-600 text-white" : "bg-gray-700 text-gray-400"
                          }`}>
                            {isDone ? "✓" : step.step_order}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className={`text-sm font-medium truncate ${isCurrent ? "text-amber-300" : isDone ? "text-emerald-300" : "text-gray-400"}`}>
                              {stepQuest?.title ?? `Шаг ${step.step_order}`}
                            </div>
                          </div>
                          {isCurrent && (
                            <span className="text-[10px] uppercase tracking-widest text-amber-500 font-mono">Текущий</span>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Chain progress summary */}
                  <div className="flex items-center gap-4 pt-3 border-t border-amber-900/20">
                    <div className="text-xs text-gray-500 uppercase tracking-widest">
                      Прогресс: {chainDetail.user_progress?.current_step ?? 0} / {chainDetail.chain.total_steps}
                    </div>
                    {chainDetail.chain.final_xp_bonus > 0 && (
                      <div className="text-xs text-amber-400 font-mono">
                        Финальный бонус: +{chainDetail.chain.final_xp_bonus} XP
                      </div>
                    )}
                    {chainDetail.user_progress?.status === "completed" && (
                      <span className="text-xs text-emerald-400 font-bold">✅ Цепочка завершена!</span>
                    )}
                  </div>
                </div>
              </Card>
            )}

            {(isClient || isAssigned) && (quest.delivery_note || quest.delivery_url || quest.delivery_submitted_at) && (
              <Card className="p-0 border-none bg-transparent">
                <div className="rpg-card p-6 md:p-8">
                  <h2 className="text-xl font-cinzel font-bold mb-6 text-cyan-300 flex items-center gap-3 border-b border-cyan-900/30 pb-3">
                    <span className="grayscale opacity-70">📦</span> Сдача результата
                  </h2>
                  <div className="space-y-4 text-sm">
                    {quest.delivery_submitted_at && (
                      <div className="font-mono text-gray-500">
                        Отправлено: <span className="text-gray-300">{new Date(quest.delivery_submitted_at).toLocaleString("ru-RU")}</span>
                      </div>
                    )}
                    {quest.delivery_note && (
                      <div className="whitespace-pre-wrap rounded-xl border border-cyan-900/30 bg-cyan-950/10 p-4 text-gray-300">
                        {quest.delivery_note}
                      </div>
                    )}
                    {quest.delivery_url && (() => { try { const p = new URL(quest.delivery_url).protocol; return p === 'http:' || p === 'https:'; } catch { return false; } })() && (
                      <a
                        href={quest.delivery_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-2 rounded-lg border border-cyan-700/40 bg-cyan-950/20 px-4 py-2 text-cyan-300 hover:text-cyan-200"
                      >
                        🔗 Открыть результат
                      </a>
                    )}
                  </div>
                </div>
              </Card>
            )}

            {(isClient || isAssigned) && quest.revision_reason && (
              <Card className="p-0 border-none bg-transparent">
                <div className="rpg-card p-6 md:p-8">
                  <h2 className="text-xl font-cinzel font-bold mb-6 text-orange-300 flex items-center gap-3 border-b border-orange-900/30 pb-3">
                    <span className="grayscale opacity-70">🛠️</span> Запрос на доработку
                  </h2>
                  <div className="space-y-3 text-sm">
                    {quest.revision_requested_at && (
                      <div className="font-mono text-gray-500">
                        Запрошено: <span className="text-gray-300">{new Date(quest.revision_requested_at).toLocaleString("ru-RU")}</span>
                      </div>
                    )}
                    <div className="whitespace-pre-wrap rounded-xl border border-orange-900/30 bg-orange-950/10 p-4 text-orange-100">
                      {quest.revision_reason}
                    </div>
                  </div>
                </div>
              </Card>
            )}

            {canViewHistory && history.length > 0 && (
              <Card className="p-0 border-none bg-transparent">
                <div className="rpg-card p-6 md:p-8">
                  <h2 className="text-xl font-cinzel font-bold mb-6 text-indigo-300 flex items-center gap-3 border-b border-indigo-900/30 pb-3">
                    <span className="grayscale opacity-70">🕰️</span> Хроника Статусов
                  </h2>
                  <div className="space-y-4">
                    {history.map((entry) => (
                      <div key={entry.id} className="rounded-xl border border-indigo-900/30 bg-indigo-950/10 p-4">
                        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                          <div className="text-sm text-gray-300">
                            <span className="font-mono text-indigo-300 uppercase tracking-wider">{entry.from_status ?? "created"}</span>
                            <span className="mx-2 text-gray-600">→</span>
                            <span className="font-mono text-white uppercase tracking-wider">{entry.to_status}</span>
                          </div>
                          <div className="text-xs font-mono text-gray-500">
                            {new Date(entry.created_at).toLocaleString("ru-RU")}
                          </div>
                        </div>
                        {(entry.changed_by_username || entry.note) && (
                          <div className="mt-2 text-sm text-gray-400">
                            {entry.changed_by_username && <span>Изменил: <span className="text-gray-200">{entry.changed_by_username}</span>.</span>} {entry.note}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            )}

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
                            &ldquo;{app.cover_letter}&rdquo;
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

            {canOpenChat && user?.id && (
              <QuestChat questId={quest.id} currentUserId={user.id} />
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
                  {quest.quest_type === "training" ? (
                    <div className="text-center p-5 bg-gradient-to-b from-cyan-950/40 to-black/60 border border-cyan-700/50 rounded shadow-[inset_0_0_15px_rgba(34,211,238,0.1)] relative overflow-hidden">
                      <div className="absolute -right-4 -top-4 text-6xl opacity-10">⚔️</div>
                      <div className="text-xs text-cyan-400 uppercase tracking-widest mb-2 relative z-10">PvE Тренировка</div>
                      <div className="text-3xl font-bold text-cyan-300 mb-2 relative z-10 drop-shadow-[0_0_8px_rgba(34,211,238,0.8)]">
                        {quest.xp_reward} XP
                      </div>
                      <div className="text-xs text-gray-500 uppercase tracking-widest relative z-10">Макс. 500 XP / день</div>
                    </div>
                  ) : quest.quest_type === "raid" ? (
                    <>
                      <div className="text-center p-5 bg-gradient-to-b from-violet-950/40 to-black/60 border border-violet-700/50 rounded shadow-[inset_0_0_15px_rgba(139,92,246,0.1)] relative overflow-hidden">
                        <div className="absolute -right-4 -top-4 text-6xl opacity-10">⚔️</div>
                        <div className="text-xs text-violet-400 uppercase tracking-widest mb-2 relative z-10">Рейд</div>
                        <div className="text-3xl font-bold text-amber-500 mb-2 relative z-10 drop-shadow-[0_0_8px_rgba(217,119,6,0.8)]">
                          {quest.budget.toLocaleString("ru-RU")}₽
                        </div>
                        <div className="text-xs text-gray-500 uppercase tracking-widest relative z-10">Общая награда</div>
                      </div>
                      <div className="text-center p-5 bg-gradient-to-b from-purple-950/40 to-black/60 border border-purple-700/50 rounded shadow-[inset_0_0_15px_rgba(168,85,247,0.1)] relative overflow-hidden">
                        <div className="absolute -right-4 -top-4 text-6xl opacity-10">⚡</div>
                        <div className="text-3xl font-bold text-purple-400 mb-2 relative z-10 drop-shadow-[0_0_8px_rgba(168,85,247,0.8)]">
                          {quest.xp_reward} XP
                        </div>
                        <div className="text-xs text-gray-500 uppercase tracking-widest relative z-10">Опыт каждому</div>
                      </div>
                      <div className="text-center p-4 bg-violet-950/20 border border-violet-800/30 rounded">
                        <div className="text-xs text-gray-500 uppercase tracking-widest mb-1">Отряд</div>
                        <div className="text-lg font-bold text-violet-300">{quest.raid_current_members}/{quest.raid_max_members ?? "?"}</div>
                      </div>
                    </>
                  ) : (
                    <>
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
                        {user?.character_class && (
                          <div className="text-sm text-purple-300/80 mb-2 font-mono">
                            {formatXpBadge(calcXpMultiplier(user as unknown as UserClassInfo, quest))}
                          </div>
                        )}
                        <div className="text-xs text-gray-500 uppercase tracking-widest relative z-10">Опыт</div>
                      </div>
                    </>
                  )}
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
                  {isClient && quest.status === "draft" && (
                    <Button
                      onClick={handlePublish}
                      variant="primary"
                      className="w-full font-cinzel tracking-wider"
                      disabled={actionLoading !== null}
                    >
                      {actionLoading === "publish" ? "⏳ Публикация..." : "📢 Опубликовать черновик"}
                    </Button>
                  )}

                  {/* Фрилансер: Откликнуться */}
                  
                    {quest.quest_type === "training" && !isClient && quest.status === "open" && (
                      <Button
                        onClick={() => {
                          if (!isAuthenticated) {
                            router.push("/auth/login");
                            return;
                          }
                          handleTrainingAccept();
                        }}
                        variant="primary"
                        className="w-full font-cinzel tracking-wider shadow-[0_0_15px_rgba(34,211,238,0.3)] hover:shadow-[0_0_25px_rgba(34,211,238,0.5)] bg-gradient-to-r from-cyan-800 to-cyan-900 border-cyan-500/50"
                        disabled={actionLoading !== null}
                      >
                        {actionLoading === "training_accept" ? "⏳ Принятие..." : "⚔️ Принять Тренировку"}
                      </Button>
                    )}

                    {quest.quest_type === "training" && isAssigned && quest.status === "in_progress" && (
                      <Button
                        onClick={handleTrainingComplete}
                        variant="primary"
                        className="w-full font-cinzel tracking-wider shadow-[0_0_15px_rgba(34,211,238,0.3)] bg-gradient-to-r from-cyan-800 to-cyan-900 border-cyan-500/50"
                        disabled={actionLoading !== null}
                      >
                        {actionLoading === "training_complete" ? "⏳ Завершение..." : "✅ Завершить Тренировку"}
                      </Button>
                    )}

                    {/* Raid actions */}
                    {quest.quest_type === "raid" && !isClient && quest.status === "open" && (
                      <div className="space-y-3 rounded-xl border border-violet-900/30 bg-violet-950/10 p-4">
                        {raidParty && raidParty.participants.some((p) => p.user_id === user?.id) ? (
                          <Button
                            onClick={handleRaidLeave}
                            variant="secondary"
                            className="w-full font-cinzel tracking-wider border-red-700/40 text-red-400"
                            disabled={actionLoading !== null}
                          >
                            {actionLoading === "raid_leave" ? "⏳ Выход..." : "🚪 Покинуть отряд"}
                          </Button>
                        ) : (
                          <>
                            <div className="text-xs text-violet-400 uppercase tracking-widest mb-1">Выберите роль:</div>
                            <select
                              value={selectedRaidRole}
                              onChange={(e) => setSelectedRaidRole(e.target.value)}
                              className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-sm text-gray-200 focus:border-violet-500 focus:outline-none"
                            >
                              {RAID_ROLE_SLOTS.map((role) => (
                                <option key={role} value={role}>{role}</option>
                              ))}
                            </select>
                            <Button
                              onClick={() => {
                                if (!isAuthenticated) { router.push("/auth/login"); return; }
                                handleRaidJoin();
                              }}
                              variant="primary"
                              className="w-full font-cinzel tracking-wider shadow-[0_0_15px_rgba(139,92,246,0.3)] bg-gradient-to-r from-violet-800 to-violet-900 border-violet-500/50"
                              disabled={actionLoading !== null}
                            >
                              {actionLoading === "raid_join" ? "⏳ Вступление..." : "⚔️ Вступить в отряд"}
                            </Button>
                          </>
                        )}
                      </div>
                    )}

                    {/* Raid start — client/admin only */}
                    {quest.quest_type === "raid" && isClient && quest.status === "open" && (
                      <Button
                        onClick={handleRaidStart}
                        variant="primary"
                        className="w-full font-cinzel tracking-wider shadow-[0_0_15px_rgba(139,92,246,0.3)] bg-gradient-to-r from-violet-800 to-violet-900 border-violet-500/50"
                        disabled={actionLoading !== null}
                      >
                        {actionLoading === "raid_start" ? "⏳ Старт..." : "🚀 Начать Рейд"}
                      </Button>
                    )}

                    {/* Raid complete — any member */}
                    {quest.quest_type === "raid" && quest.status === "in_progress" && raidParty?.participants.some((p) => p.user_id === user?.id) && (
                      <Button
                        onClick={handleRaidComplete}
                        variant="primary"
                        className="w-full font-cinzel tracking-wider shadow-[0_0_15px_rgba(139,92,246,0.3)] bg-gradient-to-r from-violet-800 to-violet-900 border-violet-500/50"
                        disabled={actionLoading !== null}
                      >
                        {actionLoading === "raid_complete" ? "⏳ Завершение..." : "✅ Завершить Рейд"}
                      </Button>
                    )}

                    {quest.quest_type !== "training" && quest.quest_type !== "raid" && !isClient && !isAssigned && quest.status === "open" && (
                      <>
                        {hasApplied ? (
                          <Button disabled variant="secondary" className="w-full opacity-70 border-gray-700 font-cinzel tracking-wider">
                             Отклик отправлен
                          </Button>
                        ) : blockReason ? (
                          <div className="w-full">
                            <Button disabled variant="secondary" className="w-full opacity-50 border-red-900 font-cinzel tracking-wider bg-red-950/20 text-red-500">
                               Недоступно
                            </Button>
                            <div className="mt-2 text-xs text-red-400 text-center font-mono">{blockReason}</div>
                          </div>
                        ) : (
                          <Button
                          onClick={() => {
                            if (!isAuthenticated) {
                              router.push("/auth/login");
                              return;
                            }
                            setShowApplyModal(true);
                          }}
                          variant="primary"
                          className="w-full font-cinzel tracking-wider shadow-[0_0_15px_rgba(217,119,6,0.3)] hover:shadow-[0_0_25px_rgba(217,119,6,0.5)]"
                          disabled={actionLoading !== null}
                        >
                          📩 Откликнуться
                        </Button>
                      )}
                    </>
                  )}

                  {/* Исполнитель: Завершить */}
                  {isAssigned && quest.status === "assigned" && (
                    <Button
                      onClick={handleStart}
                      variant="primary"
                      className="w-full font-cinzel tracking-wider"
                      disabled={actionLoading !== null}
                    >
                      {actionLoading === "start"
                        ? "⏳ Старт..."
                        : "🚀 Начать работу"}
                    </Button>
                  )}

                  {/* Исполнитель: Завершить */}
                  {isAssigned && ["in_progress", "revision_requested"].includes(quest.status) && (
                    <div className="space-y-3 rounded-xl border border-cyan-900/30 bg-cyan-950/10 p-4">
                      {quest.status === "revision_requested" && quest.revision_reason && (
                        <div className="rounded-lg border border-orange-900/40 bg-orange-950/20 p-3 text-sm text-orange-200 whitespace-pre-wrap">
                          <div className="mb-1 text-xs uppercase tracking-wider text-orange-400">Что нужно исправить</div>
                          {quest.revision_reason}
                        </div>
                      )}
                      <textarea
                        value={deliveryNote}
                        onChange={(e) => setDeliveryNote(e.target.value)}
                        rows={5}
                        placeholder="Опишите, что именно выполнено, какие файлы приложены и что нужно проверить..."
                        className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-sm text-gray-200 placeholder:text-gray-500 focus:border-cyan-500 focus:outline-none"
                      />
                      <input
                        type="url"
                        value={deliveryUrl}
                        onChange={(e) => setDeliveryUrl(e.target.value)}
                        placeholder="https://github.com/... или https://drive.google.com/..."
                        className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-sm text-gray-200 placeholder:text-gray-500 focus:border-cyan-500 focus:outline-none"
                      />
                      <Button
                        onClick={handleComplete}
                        variant="primary"
                        className="w-full font-cinzel tracking-wider"
                        disabled={actionLoading !== null}
                      >
                        {actionLoading === "complete"
                          ? "⏳ Завершение..."
                          : quest.status === "revision_requested"
                            ? "🔁 Отправить исправления"
                            : "✅ Сдать результат"}
                      </Button>
                    </div>
                  )}

                  {/* Клиент: Подтвердить */}
                  {isClient && quest.status === "completed" && (
                    <>
                      <div className="space-y-3 rounded-xl border border-orange-900/30 bg-orange-950/10 p-4">
                        <textarea
                          value={revisionReason}
                          onChange={(e) => setRevisionReason(e.target.value)}
                          rows={4}
                          placeholder="Если нужна доработка, опишите, что именно исправить или дополнить..."
                          className="w-full rounded-lg border border-gray-700 bg-black/30 px-3 py-2 text-sm text-gray-200 placeholder:text-gray-500 focus:border-orange-500 focus:outline-none"
                        />
                        <Button
                          onClick={handleRequestRevision}
                          variant="secondary"
                          className="w-full font-cinzel tracking-wider border-orange-700/40 text-orange-300 hover:text-orange-200"
                          disabled={actionLoading !== null}
                        >
                          {actionLoading === "revision"
                            ? "⏳ Отправка..."
                            : "🛠️ Запросить доработку"}
                        </Button>
                      </div>
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

                  {/* Исполнитель: Открыть спор (клиент не подтверждает) */}
                  {isAssigned && ["completed", "revision_requested"].includes(quest.status) && quest.status !== "disputed" && (
                    <button
                      onClick={() => setShowDisputeModal(true)}
                      className="w-full font-cinzel tracking-wider px-4 py-2.5 rounded-lg border border-yellow-700/50 text-yellow-400 hover:bg-yellow-900/20 text-sm transition-colors"
                    >
                      ⚖️ Открыть спор
                    </button>
                  )}

                  {/* Клиент: Квест открыт */}
                  {isClient && ["open", "assigned"].includes(quest.status) && (
                    <Button
                      onClick={handleCancel}
                      variant="danger"
                      className="w-full font-cinzel tracking-wider border-red-900/50 hover:border-red-500/50 bg-red-950/30 text-red-400 hover:bg-red-900/40"
                      disabled={actionLoading !== null}
                    >
                      ❌ Отменить квест
                    </Button>
                  )}

                  {quest.status === "confirmed" && (isClient || isAssigned) && reviewTargetId && (
                    <div className="rounded-xl border border-amber-900/30 bg-amber-950/10 p-4 space-y-3">
                      <div>
                        <div className="text-xs uppercase tracking-wider text-amber-400 mb-1">После завершения</div>
                        <div className="text-sm text-gray-300">
                          {hasReviewed
                            ? `Вы уже оставили отзыв для ${reviewTargetName}.`
                            : `Оцените работу ${reviewTargetName} и помогите прокачать репутацию.`}
                        </div>
                      </div>
                      {hasReviewed ? (
                        <div className="rounded-lg border border-green-900/40 bg-green-950/20 px-4 py-3 text-sm text-green-300 text-center">
                          ✅ Отзыв отправлен
                        </div>
                      ) : (
                        <Button
                          onClick={() => setShowReviewModal(true)}
                          variant="primary"
                          className="w-full font-cinzel tracking-wider"
                          disabled={actionLoading !== null || reviewCheckLoading}
                        >
                          {reviewCheckLoading ? "⏳ Проверка..." : "⭐ Оставить отзыв"}
                        </Button>
                      )}
                    </div>
                  )}

                  {/* Статус для остальных */}
                  {quest.status !== "open" && !isClient && (
                    <div className="text-center text-gray-500 font-mono text-sm py-3 border border-gray-800 bg-gray-900/30 rounded">
                      {quest.status === "draft" && "📝 Черновик"}
                      {quest.status === "assigned" && "📌 Ожидает старта исполнителя"}
                      {quest.status === "in_progress" && "🔵 Квест в работе"}
                      {quest.status === "completed" && "🟣 Ожидает подтверждения"}
                      {quest.status === "revision_requested" && "🛠️ Требуются доработки"}
                      {quest.status === "confirmed" && "🏆 Квест подтверждён"}
                      {quest.status === "cancelled" && "⚫ Квест отменён"}
                    </div>
                  )}
                </div>
              </div>
            </Card>

            {/* Рекомендованные исполнители для клиента */}
            {isClient && quest.status === "open" && quest.skills && quest.skills.length > 0 && (
              <Card className="p-0 border-none bg-transparent">
                <div className="rpg-card p-6 md:p-8">
                  <RecommendedTalentRail
                    questId={quest.id}
                    skills={quest.skills}
                    limit={3}
                    title="Подходящие исполнители"
                  />
                </div>
              </Card>
            )}

            {/* Повторный найм — после подтверждения контракта */}
            {isClient && quest.status === "confirmed" && (
              <RepeatHireCard quest={quest} freelancerId={quest.assigned_to} />
            )}
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

      {showReviewModal && reviewTargetId && (
        <ReviewModal
          questId={quest.id}
          revieweeId={reviewTargetId}
          revieweeName={reviewTargetName}
          onClose={() => setShowReviewModal(false)}
          onSubmitted={handleReviewSubmitted}
        />
      )}

      {showDisputeModal && quest && (
        <DisputeModal
          questId={quest.id}
          questTitle={quest.title}
          onClose={() => setShowDisputeModal(false)}
          onSubmitted={(_dispute) => {
            setShowDisputeModal(false);
            setQuest((prev) => prev ? { ...prev, status: "disputed" } : prev);
          }}
        />
      )}
    </main>
  );
}
