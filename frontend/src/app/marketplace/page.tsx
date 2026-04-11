"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useSWRFetch } from "@/hooks/useSWRFetch";
import { motion } from "@/lib/motion";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import {
  addToShortlist,
  createGuild,
  getApiErrorMessage,
  getShortlistIds,
  getTalentMarket,
  GuildCard,
  joinGuild,
  leaveGuild,
  removeFromShortlist,
  TalentMarketMember,
  TalentMarketMode,
  TalentMarketResponse,
  UserGrade,
} from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import LevelBadge from "@/components/rpg/LevelBadge";
import TrustScoreBadge from "@/components/rpg/TrustScoreBadge";
import { getXpDisplay } from "@/lib/xp";
import { Bookmark } from "lucide-react";
import { trackAnalyticsEvent } from "@/lib/analytics";
import SavedSearchForm from "@/components/growth/SavedSearchForm";

const PAGE_SIZE = 20;
const RANK_ICONS = ["🥇", "🥈", "🥉"];

const MODE_OPTIONS: { value: TalentMarketMode; label: string; note: string }[] = [
  { value: "all", label: "Все", note: "Общий рынок" },
  { value: "solo", label: "Solo", note: "Независимые исполнители" },
  { value: "guild", label: "Guild", note: "Участники гильдий" },
  { value: "top-guilds", label: "Top Guilds", note: "Карточки лучших гильдий" },
];

const GRADE_FILTERS: { value: UserGrade | "all"; label: string; note: string }[] = [
  { value: "all", label: "Все", note: "Все грейды" },
  { value: "novice", label: "Novice", note: "Входной пул" },
  { value: "junior", label: "Junior", note: "Исполнители роста" },
  { value: "middle", label: "Middle", note: "Основной костяк" },
  { value: "senior", label: "Senior", note: "Ведущие бойцы" },
];

const SORT_OPTIONS = [
  { value: "xp", label: "XP" },
  { value: "level", label: "Уровень" },
  { value: "rating", label: "Рейтинг" },
  { value: "trust", label: "Trust" },
  { value: "username", label: "Имя" },
] as const;

type MarketplaceSort = (typeof SORT_OPTIONS)[number]["value"];

const GRADE_COLORS: Record<UserGrade, string> = {
  novice: "text-green-300 border-green-500/40 bg-green-500/10",
  junior: "text-cyan-300 border-cyan-500/40 bg-cyan-500/10",
  middle: "text-amber-300 border-amber-500/40 bg-amber-500/10",
  senior: "text-fuchsia-300 border-fuchsia-500/40 bg-fuchsia-500/10",
};

const BUDGET_BAND_LABELS: Record<string, string> = {
  up_to_15k: "До 15k",
  "15k_to_50k": "15k-50k",
  "50k_to_150k": "50k-150k",
  "150k_plus": "150k+",
};

import { formatMoney } from "@/lib/format";

const AVAILABILITY_LABELS: Record<string, string> = {
  available: "Доступен",
  limited: "1-2 слота",
  busy: "Загружен",
};

function getModeCopy(mode: TalentMarketMode) {
  switch (mode) {
    case "solo":
      return {
        title: "Solo market",
        description: "Независимые специалисты без гильдейского щита. Подходит, когда нужен точечный эксперт под короткий контракт.",
      };
    case "guild":
      return {
        title: "Guild roster",
        description: "Исполнители, которые уже встроены в командную структуру. Здесь важнее стабильность состава и репутация гильдии.",
      };
    case "top-guilds":
      return {
        title: "Top guilds",
        description: "Отдельный слой рынка для заказчиков, которые хотят выбирать не одного фрилансера, а сильную командную среду и бренд гильдии.",
      };
    default:
      return {
        title: "Talent market",
        description: "Рынок разделён на solo и guild. Можно быстро переключиться между независимыми исполнителями, участниками гильдий и топ-гильдиями.",
      };
  }
}

function MarketplaceMemberRow({
  member,
  rank,
  isShortlisted,
  onToggleShortlist,
}: {
  member: TalentMarketMember;
  rank: number;
  isShortlisted?: boolean;
  onToggleShortlist?: (id: string) => void;
}) {
  const xpDisplay = getXpDisplay(member.xp, member.xp_to_next);
  const rankIcon = rank <= 3 ? RANK_ICONS[rank - 1] : null;

  return (
    <motion.div
      initial={{ opacity: 0, x: -18 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: rank * 0.03 }}
    >
      <Link href={`/users/${member.id}`} className="block">
        <Card className="overflow-hidden border-white/10 bg-[linear-gradient(135deg,rgba(11,16,28,0.96),rgba(21,16,34,0.92))] p-0 hover:border-violet-400/40">
          <div className="grid gap-4 p-4 lg:grid-cols-[auto_auto_minmax(0,1fr)_auto_auto] lg:items-center">
            <div className="w-10 text-center text-lg font-bold text-stone-400">
              {rankIcon ?? `#${rank}`}
            </div>

            <div className="relative h-12 w-12 overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-violet-700/40 to-slate-950">
              <div className="flex h-full w-full items-center justify-center font-cinzel text-lg font-bold text-white">
                {member.username.charAt(0).toUpperCase()}
              </div>
              <div className="absolute -bottom-1 -right-1 scale-75">
                <LevelBadge level={member.level} grade={member.grade} showGradeText={false} />
              </div>
            </div>

            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate font-cinzel text-lg font-bold text-white">{member.username}</span>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] ${GRADE_COLORS[member.grade]}`}>
                  {member.grade}
                </span>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] ${member.market_kind === "guild" ? "border-amber-500/40 bg-amber-500/10 text-amber-300" : "border-slate-600/50 bg-slate-500/10 text-slate-300"}`}>
                  {member.market_kind === "guild" ? "Guild" : "Solo"}
                </span>
                {member.guild && (
                  <span className="rounded-full border border-violet-500/40 bg-violet-500/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-violet-200">
                    {member.guild.name}
                  </span>
                )}
              </div>

              <div className="mt-2 flex items-center gap-3 text-xs text-stone-400">
                <span>{member.avg_rating ? `${member.avg_rating.toFixed(1)} рейтинг` : "Новый профиль"}</span>
                <span>{member.review_count} отзывов</span>
                <span>{member.badges_count} бейджей</span>
                {member.character_class && <span>{member.character_class}</span>}
                <TrustScoreBadge score={member.trust_score} size="sm" />
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-stone-400">
                {member.typical_budget_band && (
                  <span className="rounded-full border border-sky-500/20 bg-sky-500/10 px-2 py-1 text-sky-200">
                    {BUDGET_BAND_LABELS[member.typical_budget_band] ?? member.typical_budget_band}
                  </span>
                )}
                {member.availability_status && (
                  <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-1 text-emerald-200">
                    {AVAILABILITY_LABELS[member.availability_status] ?? member.availability_status}
                  </span>
                )}
                {member.response_time_hint && <span>{member.response_time_hint}</span>}
              </div>

              <div className="mt-3 flex items-center gap-3">
                <div className="xp-bar-track h-2 flex-1 overflow-hidden">
                  <div className="xp-bar-fill h-full" style={{ width: `${xpDisplay.percent}%` }} />
                </div>
                <span className="text-[11px] uppercase tracking-[0.15em] text-stone-400">{member.xp.toLocaleString("ru-RU")} XP</span>
              </div>

              {member.skills.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {member.skills.slice(0, 4).map((skill) => (
                    <span key={skill} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-stone-300">
                      {skill}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="grid grid-cols-3 gap-2 text-center font-mono lg:min-w-[168px]">
              <div className="rounded-xl border border-blue-900/40 bg-blue-950/20 p-2">
                <div className="text-[10px] text-blue-400/80">INT</div>
                <div className="text-sm font-bold text-blue-300">{member.stats.int}</div>
              </div>
              <div className="rounded-xl border border-emerald-900/40 bg-emerald-950/20 p-2">
                <div className="text-[10px] text-emerald-400/80">DEX</div>
                <div className="text-sm font-bold text-emerald-300">{member.stats.dex}</div>
              </div>
              <div className="rounded-xl border border-amber-900/40 bg-amber-950/20 p-2">
                <div className="text-[10px] text-amber-400/80">CHA</div>
                <div className="text-sm font-bold text-amber-300">{member.stats.cha}</div>
              </div>
            </div>

            {onToggleShortlist && (
              <button
                type="button"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggleShortlist(member.id); }}
                className={`shrink-0 p-2 rounded-lg border transition-colors ${
                  isShortlisted
                    ? "border-amber-500/40 bg-amber-500/15 text-amber-400"
                    : "border-white/10 bg-white/5 text-stone-500 hover:text-amber-300 hover:border-amber-500/30"
                }`}
                title={isShortlisted ? "Убрать из шортлиста" : "В шортлист"}
              >
                <Bookmark size={16} fill={isShortlisted ? "currentColor" : "none"} />
              </button>
            )}

            <div className="space-y-2 text-right lg:min-w-[120px]">
              <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">Почему в подборке</div>
              {member.rank_signals && member.rank_signals.length > 0 && (
                <div className="flex flex-wrap justify-end gap-1">
                  {member.rank_signals.map((s) => (
                    <span
                      key={s}
                      className="rounded-full bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 text-[10px] text-violet-300"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              )}
              {member.guild?.season_position && (
                <div className="text-xs text-amber-300">Guild #{member.guild.season_position}</div>
              )}
            </div>
          </div>
        </Card>
      </Link>
    </motion.div>
  );
}

function GuildCardPanel({
  guild,
  canJoin,
  canLeave,
  actionLoading,
  onJoin,
  onLeave,
}: {
  guild: GuildCard;
  canJoin: boolean;
  canLeave: boolean;
  actionLoading: boolean;
  onJoin: () => void;
  onLeave: () => void;
}) {
  return (
    <Card className="h-full border-amber-500/20 bg-[linear-gradient(145deg,rgba(28,18,12,0.92),rgba(10,12,20,0.98))] p-6 hover:border-amber-400/40">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.28em] text-amber-400/80">
            {guild.season_position ? `Season #${guild.season_position}` : "Guild card"}
          </div>
          <h3 className="mt-2 font-cinzel text-2xl font-bold text-white">{guild.name}</h3>
          <p className="mt-2 text-sm leading-6 text-stone-400">
            {guild.description || "Гильдия уже на рынке: виден размер состава, рейтинг, подтверждённые квесты и ключевые навыки."}
          </p>
        </div>
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-right">
          <div className="text-[10px] uppercase tracking-[0.18em] text-amber-200/70">Rating</div>
          <div className="font-cinzel text-2xl font-bold text-amber-200">{guild.rating}</div>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <GuildStat label="Состав" value={`${guild.member_count}/${guild.member_limit}`} />
        <GuildStat label="Квесты" value={guild.confirmed_quests} />
        <GuildStat label="XP" value={guild.total_xp.toLocaleString("ru-RU")} />
        <GuildStat label="Казна" value={formatMoney(guild.treasury_balance, { decimals: 2 })} />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em] ${
          guild.total_xp >= 50000
            ? "border-fuchsia-500/40 bg-fuchsia-500/10 text-fuchsia-200"
            : guild.total_xp >= 20000
              ? "border-amber-500/40 bg-amber-500/10 text-amber-200"
              : guild.total_xp >= 5000
                ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-200"
                : "border-white/10 bg-white/5 text-stone-400"
        }`}>
          {guild.total_xp >= 50000
            ? "Platinum progression"
            : guild.total_xp >= 20000
              ? "Gold progression"
              : guild.total_xp >= 5000
                ? "Silver progression"
                : "Bronze progression"}
        </span>
        {guild.confirmed_quests >= 10 && (
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em] text-emerald-300">
            Active guild
          </span>
        )}
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {guild.top_skills.length > 0 ? guild.top_skills.map((skill) => (
          <span key={skill} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
            {skill}
          </span>
        )) : (
          <span className="text-sm text-stone-500">Навыки появятся после первых подтверждённых квестов.</span>
        )}
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4">
        <div className="text-sm text-stone-400">
          <span className="text-stone-500">Лидер:</span> {guild.leader_username ?? "не назначен"}
          <span className="mx-2 text-stone-600">•</span>
          <span className="text-stone-500">Avg rating:</span> {guild.avg_rating ? guild.avg_rating.toFixed(1) : "n/a"}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button href={`/marketplace/guilds/${guild.slug}`} variant="ghost">
            Профиль гильдии
          </Button>
          {canJoin && (
            <Button variant="primary" onClick={onJoin} loading={actionLoading} loadingLabel="Вступаем...">
              Вступить
            </Button>
          )}
          {canLeave && (
            <Button variant="secondary" onClick={onLeave} loading={actionLoading} loadingLabel="Выходим...">
              Покинуть
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}

function GuildStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
      <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">{label}</div>
      <div className="mt-2 font-cinzel text-xl font-bold text-white">{value}</div>
    </div>
  );
}

export default function MarketplacePage() {
  const { isAuthenticated, user } = useAuth();

  const [mode, setMode] = useState<TalentMarketMode>("all");
  const [gradeFilter, setGradeFilter] = useState<UserGrade | "all">("all");
  const [sortBy, setSortBy] = useState<MarketplaceSort>("xp");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  const swrKey = `market:${mode}:${gradeFilter}:${search}:${sortBy}:${offset}`;
  const { data: market, isLoading: loading, error: marketError, mutate: mutateMarket } = useSWRFetch<TalentMarketResponse>(
    swrKey,
    () => getTalentMarket({
      skip: offset,
      limit: PAGE_SIZE,
      mode,
      grade: gradeFilter === "all" ? undefined : gradeFilter,
      search,
      sortBy,
    }),
    { keepPreviousData: true },
  );
  const error = marketError ? getApiErrorMessage(marketError, "Не удалось загрузить talent market.") : null;
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionGuildId, setActionGuildId] = useState<string | null>(null);
  const [showCreateGuild, setShowCreateGuild] = useState(false);
  const [guildName, setGuildName] = useState("");
  const [guildDescription, setGuildDescription] = useState("");
  const [guildEmblem, setGuildEmblem] = useState("ember");
  const [shortlistedIds, setShortlistedIds] = useState<Set<string>>(new Set());

  // Track page visit
  useEffect(() => {
    trackAnalyticsEvent("marketplace_view");
  }, []);

  // Load shortlist IDs for clients
  useEffect(() => {
    if (isAuthenticated && user?.role === "client") {
      getShortlistIds()
        .then((ids) => setShortlistedIds(new Set(ids)))
        .catch((e) => console.warn("Failed to load shortlist IDs", e));
    }
  }, [isAuthenticated, user?.role]);

  const handleToggleShortlist = useCallback(async (freelancerId: string) => {
    const isIn = shortlistedIds.has(freelancerId);
    try {
      if (isIn) {
        await removeFromShortlist(freelancerId);
        setShortlistedIds((prev) => { const n = new Set(prev); n.delete(freelancerId); return n; });
      } else {
        await addToShortlist(freelancerId);
        setShortlistedIds((prev) => new Set(prev).add(freelancerId));
      }
    } catch {
      // silent — optimistic UI
    }
  }, [shortlistedIds]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setOffset(0);
    }, 250);

    return () => window.clearTimeout(timeoutId);
  }, [searchInput]);


  const modeCopy = getModeCopy(mode);
  const summary = market?.summary;
  const members = useMemo(() => market?.members ?? [], [market?.members]);
  const guilds = market?.guilds ?? [];

  const currentGuildId = useMemo(() => {
    if (!user) {
      return null;
    }

    const selfInMembers = members.find((member) => member.id === user.id);
    if (selfInMembers?.guild) {
      return selfInMembers.guild.id;
    }

    return null;
  }, [members, user]);

  const titleStats = useMemo(
    () => [
      {
        label: "Всего фрилансеров",
        value: summary?.total_freelancers ?? 0,
        note: "всех героев рынка",
        tone: "slate" as const,
      },
      {
        label: "Solo",
        value: summary?.solo_freelancers ?? 0,
        note: "играют в одиночку",
        tone: "cyan" as const,
      },
      {
        label: "Guild",
        value: summary?.guild_freelancers ?? 0,
        note: "в составе гильдий",
        tone: "amber" as const,
      },
      {
        label: "Top Guild Rating",
        value: summary?.top_guild_rating ?? 0,
        note: "максимум сезона",
        tone: "purple" as const,
      },
    ],
    [summary],
  );

  const resetFeedback = () => {
    setActionError(null);
    setActionSuccess(null);
  };

  const refreshMarket = () => mutateMarket();

  const handleGuildJoin = async (guildId: string) => {
    resetFeedback();
    setActionGuildId(guildId);
    try {
      const result = await joinGuild(guildId);
      setActionSuccess(result.message);
      await refreshMarket();
    } catch (err) {
      setActionError(getApiErrorMessage(err, "Не удалось вступить в гильдию."));
    } finally {
      setActionGuildId(null);
    }
  };

  const handleGuildLeave = async (guildId: string) => {
    resetFeedback();
    setActionGuildId(guildId);
    try {
      const result = await leaveGuild(guildId);
      setActionSuccess(result.message);
      await refreshMarket();
    } catch (err) {
      setActionError(getApiErrorMessage(err, "Не удалось покинуть гильдию."));
    } finally {
      setActionGuildId(null);
    }
  };

  const handleCreateGuild = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    resetFeedback();
    setActionGuildId("create");
    try {
      const result = await createGuild({
        name: guildName,
        description: guildDescription.trim() || undefined,
        emblem: guildEmblem.trim() || undefined,
      });
      setActionSuccess(result.message);
      setGuildName("");
      setGuildDescription("");
      setGuildEmblem("ember");
      setShowCreateGuild(false);
      setMode("guild");
      setOffset(0);
      await refreshMarket();
    } catch (err) {
      setActionError(getApiErrorMessage(err, "Не удалось создать гильдию."));
    } finally {
      setActionGuildId(null);
    }
  };

  const canManageGuilds = isAuthenticated && user?.role === "freelancer";

  return (
    <main className="min-h-screen bg-[var(--bg-primary)]">
      <Header />

      <div className="container mx-auto px-4 py-8">
        <GuildStatusStrip
          mode="market"
          eyebrow="Talent market"
          title="Рынок теперь разделён на solo и guild"
          description={modeCopy.description}
          stats={titleStats}
          signals={[
            { label: `Mode: ${MODE_OPTIONS.find((item) => item.value === mode)?.label ?? mode}`, tone: "purple" },
            { label: `Sort: ${SORT_OPTIONS.find((item) => item.value === sortBy)?.label ?? sortBy}`, tone: "cyan" },
            { label: gradeFilter === "all" ? "Все грейды" : `Grade: ${gradeFilter}`, tone: "amber" },
            { label: search ? `Поиск: ${search}` : "Поиск не ограничен", tone: "slate" },
          ]}
          className="mb-8"
        />

        <motion.section
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
        >
          <div className="mb-8 flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.32em] text-violet-300/80">{modeCopy.title}</p>
              <h1 className="mt-3 font-cinzel text-4xl font-bold text-white sm:text-5xl">
                Solo, Guild и Top Guilds в одной витрине
              </h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-stone-400">
                Теперь вкладка не притворяется гильдией. Здесь отдельно виден рынок одиночек, рынок участников гильдий и слой карточек самих гильдий.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button href="/quests" variant="primary">Смотреть квесты</Button>
              {canManageGuilds && (
                <Button variant="secondary" onClick={() => setShowCreateGuild((value) => !value)}>
                  {showCreateGuild ? "Скрыть форму" : "Создать гильдию"}
                </Button>
              )}
            </div>
          </div>

          <Card className="mb-6 border-violet-500/20 bg-[linear-gradient(135deg,rgba(14,18,31,0.98),rgba(34,18,44,0.92))] p-5">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
              <div className="grid gap-4">
                <div className="grid gap-2 md:grid-cols-4">
                  {MODE_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        setMode(option.value);
                        setOffset(0);
                        resetFeedback();
                      }}
                      className={`rounded-2xl border px-4 py-3 text-left transition-colors ${
                        mode === option.value
                          ? "border-violet-400/50 bg-violet-500/15 text-white"
                          : "border-white/10 bg-black/20 text-stone-400 hover:border-white/20 hover:text-stone-200"
                      }`}
                    >
                      <div className="font-cinzel text-sm font-bold uppercase tracking-[0.18em]">{option.label}</div>
                      <div className="mt-1 text-xs text-stone-500">{option.note}</div>
                    </button>
                  ))}
                </div>

                <div className="grid gap-2 md:grid-cols-5">
                  {GRADE_FILTERS.map((filter) => (
                    <button
                      key={filter.value}
                      type="button"
                      onClick={() => {
                        setGradeFilter(filter.value);
                        setOffset(0);
                      }}
                      className={`rounded-2xl border px-4 py-3 text-left transition-colors ${
                        gradeFilter === filter.value
                          ? "border-amber-400/50 bg-amber-500/10 text-white"
                          : "border-white/10 bg-black/20 text-stone-400 hover:border-white/20 hover:text-stone-200"
                      }`}
                    >
                      <div className="font-cinzel text-sm font-bold uppercase tracking-[0.18em]">{filter.label}</div>
                      <div className="mt-1 text-xs text-stone-500">{filter.note}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] lg:grid-cols-1">
                <div>
                  <label htmlFor="market-search" className="mb-2 block text-[11px] uppercase tracking-[0.22em] text-stone-500">
                    Поиск по имени или навыкам
                  </label>
                  <input
                    id="market-search"
                    value={searchInput}
                    onChange={(event) => setSearchInput(event.target.value)}
                    placeholder="Например: React, Python, DevOps"
                    className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition-colors placeholder:text-stone-600 focus:border-violet-400/40"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-4">
                  {SORT_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        setSortBy(option.value);
                        setOffset(0);
                      }}
                      className={`rounded-2xl border px-3 py-3 text-xs uppercase tracking-[0.2em] transition-colors ${
                        sortBy === option.value
                          ? "border-cyan-400/50 bg-cyan-500/10 text-cyan-100"
                          : "border-white/10 bg-black/20 text-stone-400 hover:border-white/20 hover:text-stone-200"
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </Card>

          {/* Save current search */}
          {isAuthenticated && (
            <div className="mb-2 flex items-center gap-4 rounded-xl border border-purple-500/20 bg-purple-950/10 px-5 py-3">
              <span className="text-xs text-purple-400 uppercase tracking-widest">Сохранить поиск</span>
              <SavedSearchForm
                searchType="talent"
                filtersJson={{ mode, grade: gradeFilter, sort: sortBy, search }}
              />
            </div>
          )}

          {/* Shortlist quick access */}
          {user?.role === "client" && shortlistedIds.size > 0 && (
            <div className="mb-6 flex items-center justify-between rounded-xl border border-amber-500/20 bg-amber-500/5 px-5 py-3">
              <div className="flex items-center gap-2 text-sm text-amber-300">
                <Bookmark size={16} fill="currentColor" />
                В шортлисте: {shortlistedIds.size}
              </div>
              <Link
                href={`/marketplace/compare?ids=${Array.from(shortlistedIds).join(",")}&source=marketplace`}
                className="text-sm text-amber-400 hover:text-amber-300 transition-colors"
              >
                Сравнить →
              </Link>
            </div>
          )}

          {showCreateGuild && canManageGuilds && (
            <Card className="mb-6 border-amber-500/20 bg-[linear-gradient(135deg,rgba(34,22,10,0.96),rgba(12,14,24,0.98))] p-5">
              <form className="grid gap-4" onSubmit={handleCreateGuild}>
                <div>
                  <h2 className="font-cinzel text-2xl font-bold text-white">Создать гильдию</h2>
                  <p className="mt-2 text-sm text-stone-400">
                    Первая итерация даёт базовый фундамент: название, описание, эмблема и вступление в гильдию прямо из market layer.
                  </p>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="grid gap-2 text-sm text-stone-300">
                    Название
                    <input
                      value={guildName}
                      onChange={(event) => setGuildName(event.target.value)}
                      minLength={3}
                      maxLength={80}
                      required
                      className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white outline-none transition-colors focus:border-amber-400/40"
                    />
                  </label>

                  <label className="grid gap-2 text-sm text-stone-300">
                    Emblem slug
                    <input
                      value={guildEmblem}
                      onChange={(event) => setGuildEmblem(event.target.value)}
                      maxLength={24}
                      className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white outline-none transition-colors focus:border-amber-400/40"
                    />
                  </label>
                </div>

                <label className="grid gap-2 text-sm text-stone-300">
                  Описание
                  <textarea
                    value={guildDescription}
                    onChange={(event) => setGuildDescription(event.target.value)}
                    rows={4}
                    maxLength={500}
                    className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white outline-none transition-colors focus:border-amber-400/40"
                  />
                </label>

                <div className="flex flex-wrap gap-3">
                  <Button type="submit" variant="primary" loading={actionGuildId === "create"} loadingLabel="Создаём...">
                    Создать гильдию
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setShowCreateGuild(false)}>
                    Отмена
                  </Button>
                </div>
              </form>
            </Card>
          )}

          {actionSuccess && (
            <Card className="mb-6 border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-200">
              {actionSuccess}
            </Card>
          )}

          {actionError && (
            <Card className="mb-6 border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
              {actionError}
            </Card>
          )}

          {loading && (
            <Card className="p-12 text-center">
              <div className="mx-auto mb-4 h-16 w-16 animate-spin rounded-full border-4 border-violet-500 border-t-transparent" />
              <p className="text-stone-400">Загружаем talent market...</p>
            </Card>
          )}

          {!loading && (
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3 text-sm text-stone-400">
            <div>
              {mode === "top-guilds"
                ? `Найдено гильдий: ${guilds.length}`
                : `Найдено исполнителей: ${members.length}`}
            </div>
            <div>
              Solo XP лидер: <span className="text-white">{summary?.top_solo_xp?.toLocaleString("ru-RU") ?? 0}</span>
              <span className="mx-2 text-stone-600">•</span>
              Гильдий в системе: <span className="text-white">{summary?.total_guilds ?? 0}</span>
            </div>
          </div>
          )}

          {error && !loading && (
            <Card className="border-red-500/30 p-8 text-center">
              <div className="mb-4 text-5xl">⚠️</div>
              <h3 className="text-xl font-bold text-red-300">Ошибка загрузки</h3>
              <p className="mt-2 text-stone-400">{error}</p>
              <div className="mt-5">
                <Button variant="secondary" onClick={refreshMarket}>Повторить</Button>
              </div>
            </Card>
          )}

          {!loading && !error && mode === "top-guilds" && guilds.length > 0 && (
            <div className="grid gap-4 xl:grid-cols-2">
              {guilds.map((guild) => (
                <GuildCardPanel
                  key={guild.id}
                  guild={guild}
                  canJoin={canManageGuilds && currentGuildId === null}
                  canLeave={canManageGuilds && currentGuildId === guild.id}
                  actionLoading={actionGuildId === guild.id}
                  onJoin={() => handleGuildJoin(guild.id)}
                  onLeave={() => handleGuildLeave(guild.id)}
                />
              ))}
            </div>
          )}

          {!loading && !error && mode !== "top-guilds" && members.length > 0 && (
            <div className="space-y-3">
              {members.map((member, index) => (
                <MarketplaceMemberRow
                  key={member.id}
                  member={member}
                  rank={offset + index + 1}
                  isShortlisted={shortlistedIds.has(member.id)}
                  onToggleShortlist={user?.role === "client" ? handleToggleShortlist : undefined}
                />
              ))}
            </div>
          )}

          {!loading && !error && ((mode === "top-guilds" && guilds.length === 0) || (mode !== "top-guilds" && members.length === 0)) && (
            <Card className="p-12 text-center">
              <div className="mb-4 text-6xl">🜂</div>
              <h3 className="font-cinzel text-2xl font-bold text-white">Пока пусто</h3>
              <p className="mt-3 text-stone-400 max-w-md mx-auto">
                Для этой комбинации фильтров пока нет результатов. Попробуйте снять фильтр или воспользуйтесь другими путями:
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-3">
                {search && (
                  <button
                    onClick={() => { setSearch(""); setSearchInput(""); setOffset(0); }}
                    className="rounded-lg border border-violet-500/30 bg-violet-500/10 px-4 py-2 text-sm text-violet-200 hover:bg-violet-500/20 transition-colors"
                  >
                    Сбросить поиск
                  </button>
                )}
                {gradeFilter !== "all" && (
                  <button
                    onClick={() => { setGradeFilter("all"); setOffset(0); }}
                    className="rounded-lg border border-violet-500/30 bg-violet-500/10 px-4 py-2 text-sm text-violet-200 hover:bg-violet-500/20 transition-colors"
                  >
                    Все грейды
                  </button>
                )}
                <Link
                  href="/quests/templates"
                  className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-200 hover:bg-amber-500/20 transition-colors"
                >
                  Шаблоны квестов
                </Link>
                <Link
                  href="/quests/create"
                  className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-200 hover:bg-cyan-500/20 transition-colors"
                >
                  Создать квест
                </Link>
                {shortlistedIds.size > 0 && (
                  <Link
                    href={`/marketplace/compare?ids=${Array.from(shortlistedIds).join(",")}&source=marketplace`}
                    className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-200 hover:bg-emerald-500/20 transition-colors"
                  >
                    Сравнить избранных ({shortlistedIds.size})
                  </Link>
                )}
              </div>
            </Card>
          )}

          {!loading && !error && market?.has_more && mode !== "top-guilds" && (
            <div className="mt-6 text-center">
              <Button variant="secondary" onClick={() => setOffset((value) => value + PAGE_SIZE)}>
                Следующая страница
              </Button>
            </div>
          )}

          {!isAuthenticated && !loading && (
            <Card className="mt-10 border-violet-500/20 bg-violet-500/5 p-8 text-center">
              <div className="mb-4 text-5xl">🚀</div>
              <h3 className="font-cinzel text-2xl font-bold text-white">Зайдите в рынок как исполнитель</h3>
              <p className="mt-3 text-stone-400">
                После входа можно создавать гильдии, вступать в топ-команды и строить свою позицию между solo и guild сегментами.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-3">
                <Button href="/auth/register" variant="rpg-special">Начать путь</Button>
                <Button href="/quests" variant="ghost">Открытые квесты</Button>
              </div>
            </Card>
          )}
        </motion.section>
      </div>
    </main>
  );
}
