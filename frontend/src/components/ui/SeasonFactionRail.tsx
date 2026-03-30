"use client";

import { motion, useReducedMotion } from "@/lib/motion";
import SignalChip, { type SignalChipTone } from "@/components/ui/SignalChip";
import { useWorldMeta } from "@/context/WorldMetaContext";
import type { WorldMetaSnapshot } from "@/lib/api";

type RailMode = "quests" | "messages" | "notifications" | "profile" | "creation" | "templates" | "dossier" | "public";

interface SeasonFactionRailProps {
  mode: RailMode;
  className?: string;
  seasonLabel?: string;
  factionLabel?: string;
  communityLabel?: string;
  questCount?: number;
  unreadCount?: number;
  snapshot?: WorldMetaSnapshot | null;
  /** Optional: user's aligned faction_id — highlights matching faction card */
  userFactionId?: string;
}

const modeMeta: Record<RailMode, { tone: SignalChipTone; season: string; faction: string; community: string }> = {
  quests: {
    tone: "amber",
    season: "Season of Ember Contracts",
    faction: "Фракция Авангарда держит рынок срочных миссий",
    community: "Еженедельный рейд: закрыть 120 контрактов без срыва сроков",
  },
  messages: {
    tone: "cyan",
    season: "Season of Quiet Signals",
    faction: "Дипломаты гильдии собирают доверие через быстрые ответы",
    community: "Community pact: отвечать на диалоги в пределах одного цикла",
  },
  notifications: {
    tone: "purple",
    season: "Season of Echoes",
    faction: "Хранители хроник отслеживают каждое системное событие",
    community: "Meta goal: удерживать unread поток под контролем без потери сигнала",
  },
  profile: {
    tone: "gold",
    season: "Season of Ascension",
    faction: "Дом ремесленников укрепляет личные репутации",
    community: "Guild path: собирать трофеи, отзывы и длинные streak-цепочки",
  },
  creation: {
    tone: "emerald",
    season: "Season of New Commissions",
    faction: "Картографы фронта публикуют лучшие брифы сезона",
    community: "Challenge: формулировать задачи так, чтобы снижать ревизии по рынку",
  },
  templates: {
    tone: "purple",
    season: "Season of Blueprints",
    faction: "Архивариусы стандартизируют повторяемые победы",
    community: "Collective goal: превратить лучшие кейсы в reusable шаблоны",
  },
  dossier: {
    tone: "cyan",
    season: "Season of Final Checks",
    faction: "Инспекторы рейдов держат качество и прозрачность исполнения",
    community: "Ops rhythm: меньше возвратов на доработку, больше подтверждений с первого прохода",
  },
  public: {
    tone: "gold",
    season: "Season of Reputation",
    faction: "Залы славы продвигают тех, кто закрывает квесты без шума",
    community: "Community board: публичные профили становятся витриной доверия для всей биржи",
  },
};

export default function SeasonFactionRail({
  mode,
  className = "",
  seasonLabel,
  factionLabel,
  communityLabel,
  questCount,
  unreadCount,
  snapshot,
  userFactionId,
}: SeasonFactionRailProps) {
  const reduceMotion = useReducedMotion();
  const { snapshot: globalSnapshot } = useWorldMeta();
  const meta = modeMeta[mode];
  const live = snapshot ?? globalSnapshot;
  const leadFaction = live?.factions.find((faction) => faction.id === live.leading_faction_id) ?? live?.factions[0];
  const effectiveQuestCount = questCount ?? live?.metrics.open_quests;
  const effectiveUnreadCount = unreadCount ?? live?.metrics.unread_notifications;
  const confirmedTrend = live?.trends.find((trend) => trend.id === "confirmed_quests");
  const newQuestTrend = live?.trends.find((trend) => trend.id === "new_quests");
  const notificationTrend = live?.trends.find((trend) => trend.id === "notification_volume");

  const cards = [
    {
      title: seasonLabel ?? live?.season.title ?? meta.season,
      subtitle: live?.season.chapter ?? "Season pulse",
      chip: confirmedTrend ? formatTrendChip(confirmedTrend.delta_value, confirmedTrend.direction) : live ? `${live.season.progress_percent}%` : mode,
      chipTone: confirmedTrend ? trendTone(confirmedTrend.direction, meta.tone) : meta.tone,
      text: live
        ? `${live.season.completed_quests_week} из ${live.season.target_quests_week} недельных закрытий уже собраны. До смены цикла осталось ${live.season.days_left} дн., стадия: ${live.season.stage}.${live.season.next_unlock ? ` ${live.season.next_unlock}` : ""}`
        : effectiveQuestCount !== undefined
          ? `${effectiveQuestCount} активных объектов влияют на ритм сезона прямо сейчас.`
          : "Сезон задаёт ритм выдачи, откликов и качества закрытия контрактов.",
      isUserFaction: false,
    },
    {
      title: factionLabel ?? leadFaction?.name ?? meta.faction,
      subtitle:
        userFactionId && userFactionId === leadFaction?.id
          ? "Your faction · Leading"
          : userFactionId && userFactionId !== leadFaction?.id
          ? `Your faction: ${live?.factions.find((f) => f.id === userFactionId)?.name ?? userFactionId}`
          : "Faction pressure",
      chip: leadFaction?.trend ?? (live ? `${live.season.progress_percent}%` : mode),
      chipTone: leadFaction?.trend === "surging" ? "emerald" : leadFaction?.trend === "recovering" ? "amber" : meta.tone,
      text: live
        ? `${leadFaction?.focus} Лидер держит ${leadFaction?.score ?? 0} очков влияния, тренд: ${leadFaction?.trend ?? "stable"}.`
        : effectiveUnreadCount !== undefined
          ? `${effectiveUnreadCount} непрочитанных сигналов меняют расклад между фракциями внимания.`
          : "Фракции оформляют интерфейс как живой мир со своими приоритетами и давлением.",
      isUserFaction: !!userFactionId,
    },
    {
      title: communityLabel ?? live?.community.headline ?? meta.community,
      subtitle: "Community meta",
      chip: notificationTrend
        ? formatTrendChip(notificationTrend.delta_value, notificationTrend.direction)
        : newQuestTrend
          ? formatTrendChip(newQuestTrend.delta_value, newQuestTrend.direction)
          : live
            ? live.community.momentum
            : mode,
      chipTone: notificationTrend
        ? trendTone(notificationTrend.direction, meta.tone)
        : newQuestTrend
          ? trendTone(newQuestTrend.direction, meta.tone)
          : live?.community.momentum === "under_pressure"
            ? "red"
            : live?.community.momentum === "rising"
              ? "emerald"
              : meta.tone,
      text: live
        ? `${live.community.current_value}/${live.community.target_value} по цели ${live.community.target_label}. Momentum: ${live.community.momentum}. Unread signals: ${live.metrics.unread_notifications}, reviews: ${live.metrics.total_reviews}.`
        : "Общий прогресс и настроение комьюнити становятся частью навигации, а не спрятанным текстом в пустых блоках.",
      isUserFaction: false,
    },
  ];

  return (
    <div className={`grid gap-3 lg:grid-cols-3 ${className}`}>
      {cards.map((card, index) => (
        <motion.div
          key={card.title}
          initial={reduceMotion ? false : { opacity: 0, y: 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: reduceMotion ? 0.01 : 0.38, delay: reduceMotion ? 0 : index * 0.06, ease: "easeOut" }}
          className={`season-card-drift rounded-2xl border backdrop-blur-sm px-4 py-4 ${
            card.isUserFaction
              ? "border-amber-500/40 bg-amber-950/20 shadow-[0_0_18px_rgba(217,119,6,0.08)]"
              : "border-white/10 bg-black/25"
          }`}
        >
          <div className="flex items-center justify-between gap-3">
            <p className="text-[10px] uppercase tracking-[0.24em] text-gray-500">{card.subtitle}</p>
            <SignalChip tone={card.chipTone}>{card.chip}</SignalChip>
          </div>
          <h3 className="mt-3 text-base font-semibold text-white">{card.title}</h3>
          <p className="mt-2 text-sm leading-6 text-gray-400">{card.text}</p>
        </motion.div>
      ))}
    </div>
  );
}

function trendTone(direction: string, fallback: SignalChipTone): SignalChipTone {
  if (direction === "rising") {
    return "emerald";
  }
  if (direction === "falling") {
    return "red";
  }
  return fallback;
}

function formatTrendChip(deltaValue: number, direction: string): string {
  if (direction === "steady" || deltaValue === 0) {
    return "flat";
  }
  return `${deltaValue > 0 ? "+" : ""}${deltaValue}`;
}