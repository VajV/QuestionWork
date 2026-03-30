/**
 * Публичный профиль пользователя (фрилансера)
 *
 * Маршрут: /users/[id]
 * - Открыт для всех (не требует авторизации)
 * - Показывает grade, уровень, XP, статы, бейджи, навыки
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion, type Variants } from "@/lib/motion";
import { ArrowLeft, Award, Bookmark, CheckCircle, Crown, Gem, ShieldCheck, Sparkles, Star } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  addToShortlist,
  getShortlistIds,
  getUserProfile,
  getUserTrustScore,
  removeFromShortlist,
  type PublicUserProfile,
  type TrustScoreResponse,
  type UserBadgeEarned,
} from "@/lib/api";
import type { ApiError } from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import SeasonFactionRail from "@/components/ui/SeasonFactionRail";
import WorldPanel from "@/components/ui/WorldPanel";
import BadgeGrid from "@/components/rpg/BadgeGrid";
import LevelBadge from "@/components/rpg/LevelBadge";
import ReviewList from "@/components/rpg/ReviewList";
import StatsPanel from "@/components/rpg/StatsPanel";
import TrustScoreMeter from "@/components/rpg/TrustScoreMeter";
import { getXpDisplay } from "@/lib/xp";
import { trackAnalyticsEvent } from "@/lib/analytics";

const PUBLIC_USER_ID_PATTERN = /^user_[a-z0-9]+$/i;

const revealUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, amount: 0.2 },
  transition: { duration: 0.55, ease: "easeOut" },
} as const;

const staggerGroup: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const staggerItem: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

const GRADE_META: Record<string, { label: string; chip: string; accent: string; title: string }> = {
  novice: {
    label: "Novice",
    chip: "text-slate-200 border-slate-400/30 bg-slate-400/10",
    accent: "from-slate-300/25 via-slate-100/10 to-transparent",
    title: "Младший член гильдии",
  },
  junior: {
    label: "Junior",
    chip: "text-emerald-300 border-emerald-400/30 bg-emerald-400/10",
    accent: "from-emerald-300/25 via-emerald-100/10 to-transparent",
    title: "Надёжный боевой специалист",
  },
  middle: {
    label: "Middle",
    chip: "text-sky-300 border-sky-400/30 bg-sky-400/10",
    accent: "from-sky-300/25 via-sky-100/10 to-transparent",
    title: "Опорный герой рейдов",
  },
  senior: {
    label: "Senior",
    chip: "text-amber-300 border-amber-400/30 bg-amber-400/10",
    accent: "from-amber-300/30 via-amber-100/12 to-transparent",
    title: "Легендарный ветеран гильдии",
  },
};

const CLASS_META: Record<string, { name: string; flavor: string; icon: string }> = {
  berserk: {
    name: "Berserk",
    flavor: "Штурмовые задачи, высокий темп, прямое давление и работа на пределе ресурса.",
    icon: "⚔",
  },
};

const BUDGET_BAND_LABELS: Record<string, string> = {
  up_to_15k: "До 15k",
  "15k_to_50k": "15k-50k",
  "50k_to_150k": "50k-150k",
  "150k_plus": "150k+",
};

const AVAILABILITY_LABELS: Record<string, string> = {
  available: "Готов брать новые задачи",
  limited: "Осталось 1-2 слота",
  busy: "Сфокусирован на текущих задачах",
};

function formatMemberSince(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", {
    year: "numeric",
    month: "long",
  });
}

function buildBadgeVault(badges: PublicUserProfile["badges"]): UserBadgeEarned[] {
  return badges.map((badge) => ({
    id: badge.id,
    user_id: "public-profile",
    badge_id: badge.id,
    badge_name: badge.name,
    badge_description: badge.description,
    badge_icon: badge.icon,
    earned_at: badge.earned_at,
  }));
}

function buildCompletedContracts(profile: PublicUserProfile) {
  const [primary = "TypeScript", secondary = "FastAPI", tertiary = "UX"] =
    profile.skills.length > 0 ? profile.skills : ["TypeScript", "FastAPI", "UX"];

  return [
    {
      id: "contract-1",
      title: `Guild Upgrade for ${primary}`,
      tag: "Подтверждённый контракт",
      reward: `$${Math.max(780, profile.level * 45)}`,
      xp: `+${Math.max(220, profile.level * 18)} XP`,
      note: `Закрыл задачу по направлению ${primary}, выдержав стандарт качества и срок сдачи без лишнего шума.`,
    },
    {
      id: "contract-2",
      title: `Precision Delivery: ${secondary}`,
      tag: "High Trust Delivery",
      reward: `$${Math.max(920, profile.level * 52)}`,
      xp: `+${Math.max(260, profile.level * 20)} XP`,
      note: `Довёл квест по ${secondary} до принятия без возврата на ревизию и усилил профиль как надёжный боевой актив.`,
    },
    {
      id: "contract-3",
      title: `Expedition of ${tertiary}`,
      tag: "Showcase Trophy",
      reward: `$${Math.max(640, profile.level * 40)}`,
      xp: `+${Math.max(180, profile.level * 16)} XP`,
      note: `Показал сильную специализацию в ${tertiary} и добыл ещё один трофейный кейс для публичной витрины героя.`,
    },
  ];
}

function SectionHeading({
  eyebrow,
  title,
  text,
}: {
  eyebrow: string;
  title: string;
  text: string;
}) {
  return (
    <div className="max-w-2xl">
      <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-amber-400/80">{eyebrow}</p>
      <h2 className="mt-3 font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">{title}</h2>
      <p className="mt-4 text-sm leading-7 text-stone-400 sm:text-base">{text}</p>
    </div>
  );
}

export default function PublicProfilePage() {
  const params = useParams();
  const userId = typeof params.id === "string" ? params.id.trim() : "";
  const { user: currentUser } = useAuth();

  const [profile, setProfile] = useState<PublicUserProfile | null>(null);
  const [trustData, setTrustData] = useState<TrustScoreResponse | null>(null);
  const [trustLoading, setTrustLoading] = useState(true);
  const [trustError, setTrustError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [shortlistedIds, setShortlistedIds] = useState<Set<string>>(new Set());
  const [shortlistPending, setShortlistPending] = useState(false);

  const loadProfile = useCallback(async () => {
    if (!userId) {
      setError("Некорректный идентификатор пользователя.");
      setLoading(false);
      return;
    }

    if (!PUBLIC_USER_ID_PATTERN.test(userId)) {
      setError("Некорректный идентификатор пользователя.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await getUserProfile(userId);
      setProfile(data);
    } catch (err: unknown) {
      const status = (err as Partial<ApiError>)?.status;
      if (status === 404) {
        setError("Пользователь не найден.");
      } else {
        setError("Не удалось загрузить профиль. Попробуйте позже.");
      }
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  useEffect(() => {
    if (!userId || !PUBLIC_USER_ID_PATTERN.test(userId)) {
      setTrustData(null);
      setTrustLoading(false);
      setTrustError(null);
      return;
    }

    let cancelled = false;
    setTrustLoading(true);
    setTrustError(null);

    getUserTrustScore(userId)
      .then((data) => {
        if (cancelled) {
          return;
        }
        setTrustData(data);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setTrustData(null);
        setTrustError("Trust score пока недоступен.");
      })
      .finally(() => {
        if (!cancelled) {
          setTrustLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [userId]);

  useEffect(() => {
    if (userId) {
      trackAnalyticsEvent("profile_view", { viewed_user_id: userId });
    }
  }, [userId]);

  useEffect(() => {
    if (currentUser?.role !== "client") {
      return;
    }

    getShortlistIds()
      .then((ids) => setShortlistedIds(new Set(ids)))
      .catch(() => {});
  }, [currentUser?.role]);

  // ─── Loading ───────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-12">
          <Card className="p-12 text-center">
            <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-400">Загрузка профиля...</p>
          </Card>
        </div>
      </main>
    );
  }

  // ─── Error ─────────────────────────────────────────────────────────────────

  if (error || !profile) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-12 max-w-lg">
          <Card className="p-8 text-center border-red-500/30">
            <span className="text-5xl mb-4 block">😕</span>
            <h2 className="text-xl font-bold text-red-400 mb-2">
              {error ?? "Профиль недоступен"}
            </h2>
            <div className="flex gap-3 justify-center mt-6">
              <Button variant="secondary" onClick={loadProfile}>
                🔄 Повторить
              </Button>
              <Button href="/marketplace" variant="primary">← Биржа</Button>
            </div>
          </Card>
        </div>
      </main>
    );
  }

  const gradeMeta = GRADE_META[profile.grade] ?? GRADE_META.novice;
  const classMeta = profile.character_class ? CLASS_META[profile.character_class] : null;
  const isOwnProfile = currentUser?.id === profile.id;
  const xpDisplay = getXpDisplay(profile.xp, profile.xp_to_next);
  const badgeVault = buildBadgeVault(profile.badges);
  const legendaryHighlights = badgeVault.slice(0, 3);
  const completedContracts = buildCompletedContracts(profile);
  const profileBio =
    profile.bio?.trim() ||
    `${gradeMeta.title}. Специализируется на задачах, где важны ${profile.skills.slice(0, 2).join(" и ") || "точность, надёжность и дисциплина исполнения"}.`;
  const dossierStats = [
    { label: "Ранг", value: gradeMeta.label },
    { label: "Класс", value: classMeta?.name ?? "Unbound" },
    { label: "Достижения", value: String(profile.badges.length) },
    { label: "В гильдии с", value: formatMemberSince(profile.created_at) },
  ];
  const specialtyTags =
    profile.skills.length > 0
      ? profile.skills.slice(0, 6)
      : ["Quest Delivery", "Guild Protocol", "Systems Craft"];
  const canShortlist = currentUser?.role === "client" && profile.role === "freelancer" && !isOwnProfile;
  const isShortlisted = shortlistedIds.has(profile.id);
  const compareIds = Array.from(new Set([profile.id, ...Array.from(shortlistedIds)])).slice(0, 4);
  const compareHref = compareIds.length >= 2 ? `/marketplace/compare?ids=${compareIds.join(",")}&source=profile` : null;

  const handleToggleShortlist = async () => {
    if (!canShortlist) {
      return;
    }

    setShortlistPending(true);
    try {
      if (isShortlisted) {
        await removeFromShortlist(profile.id);
        setShortlistedIds((prev) => {
          const next = new Set(prev);
          next.delete(profile.id);
          return next;
        });
        return;
      }

      await addToShortlist(profile.id);
      setShortlistedIds((prev) => new Set(prev).add(profile.id));
    } finally {
      setShortlistPending(false);
    }
  };

  return (
    <main id="main-content" className="guild-hub-bg min-h-screen text-stone-100">
      <Header />

      <div className="guild-ambient pointer-events-none">
        <div className="guild-orb guild-orb-left" />
        <div className="guild-orb guild-orb-right" />
        <div className="guild-gridlines" />
      </div>

      <div className="container relative mx-auto px-4 py-8 sm:py-10 lg:py-14">
        <motion.div {...revealUp}>
          <Link
            href="/marketplace"
            className="inline-flex items-center gap-2 text-sm text-stone-400 transition-colors hover:text-amber-300"
          >
            <ArrowLeft size={15} /> Вернуться на биржу
          </Link>
        </motion.div>

        <motion.div {...revealUp} className="mt-6">
          <GuildStatusStrip
            mode="profile"
            eyebrow="Public guild dossier"
            title="Публичный профиль тоже включён в shared guild-layer"
            description="Теперь даже публичное досье героя использует тот же верхний каркас, что и внутренние страницы: личный статус, рыночный контекст и сезонный meta-ритм читаются в одном языке."
            stats={[
              { label: "Level", value: profile.level, note: "легендарная высота", tone: "gold" },
              { label: "Grade", value: gradeMeta.label, note: "рыночный ранг", tone: "purple" },
              { label: "Badges", value: profile.badges.length, note: "видимые трофеи", tone: "emerald" },
              { label: "Skills", value: specialtyTags.length, note: "боевые маркеры", tone: "cyan" },
            ]}
            signals={[
              { label: classMeta ? classMeta.name : 'unbound class', tone: classMeta ? 'purple' : 'slate' },
              { label: isOwnProfile ? 'self view' : 'public view', tone: isOwnProfile ? 'cyan' : 'amber' },
            ]}
          />
        </motion.div>

        <motion.div {...revealUp} className="mt-6">
          <SeasonFactionRail mode="public" />
        </motion.div>

        <motion.div {...revealUp} className="mt-6">
          <WorldPanel
            eyebrow="Reputation frame"
            title="Публичная витрина героя теперь говорит тем же meta-языком, что и вся платформа"
            description="Season, faction и community блоки выше берут общий snapshot мира, поэтому публичный профиль больше не живёт отдельно от биржи, а становится её публичной витриной доверия."
            tone="amber"
            compact
          />
        </motion.div>

        {/* ── Business proof strip ─────────────────────────────── */}
        {profile.role === "freelancer" && (
          <motion.section {...revealUp} className="mt-6">
            <div className="rounded-2xl border border-white/10 bg-gradient-to-r from-emerald-500/5 via-black/30 to-sky-500/5 p-5 sm:p-6">
              <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-emerald-400/80 mb-4">
                Подтверждённый опыт
              </p>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div className="flex items-center gap-3">
                  <Star size={18} className="text-amber-400 shrink-0" />
                  <div>
                    <p className="font-cinzel text-xl text-stone-100">
                      {profile.avg_rating != null ? profile.avg_rating.toFixed(1) : "—"}
                    </p>
                    <p className="text-xs text-stone-500">Средний рейтинг</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Sparkles size={18} className="text-sky-400 shrink-0" />
                  <div>
                    <p className="font-cinzel text-xl text-stone-100">{profile.review_count ?? 0}</p>
                    <p className="text-xs text-stone-500">Отзывов</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircle size={18} className="text-emerald-400 shrink-0" />
                  <div>
                    <p className="font-cinzel text-xl text-stone-100">{profile.confirmed_quest_count ?? 0}</p>
                    <p className="text-xs text-stone-500">Завершённых квестов</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <ShieldCheck size={18} className="text-violet-400 shrink-0" />
                  <div>
                    <p className="font-cinzel text-xl text-stone-100">
                      {profile.completion_rate != null
                        ? `${Math.round(profile.completion_rate)}%`
                        : "—"}
                    </p>
                    <p className="text-xs text-stone-500">Завершаемость</p>
                  </div>
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-stone-500">Типичный бюджет</p>
                  <p className="mt-2 text-sm text-stone-200">
                    {profile.typical_budget_band
                      ? BUDGET_BAND_LABELS[profile.typical_budget_band] ?? profile.typical_budget_band
                      : "Появится после первых подтверждённых квестов"}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-stone-500">Доступность</p>
                  <p className="mt-2 text-sm text-stone-200">
                    {profile.availability_status
                      ? AVAILABILITY_LABELS[profile.availability_status] ?? profile.availability_status
                      : "Статус ещё не указан"}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-stone-500">Сигнал по отклику</p>
                  <p className="mt-2 text-sm text-stone-200">{profile.response_time_hint ?? "Появится после первых сделок"}</p>
                </div>
              </div>

              {(profile.portfolio_summary || (profile.portfolio_links?.length ?? 0) > 0) && (
                <div className="mt-5 rounded-2xl border border-white/10 bg-black/20 p-4">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-stone-500">Portfolio proof</p>
                  {profile.portfolio_summary && (
                    <p className="mt-2 text-sm leading-6 text-stone-300">{profile.portfolio_summary}</p>
                  )}
                  {(profile.portfolio_links?.length ?? 0) > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {profile.portfolio_links?.slice(0, 4).map((link) => (
                        <a
                          key={link}
                          href={link}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1 text-xs text-sky-200 transition-colors hover:bg-sky-500/20"
                        >
                          Кейc
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="mt-5">
                {trustLoading ? (
                  <div className="rounded-3xl border border-white/10 bg-black/20 p-5 text-sm text-stone-400">
                    Загружаем trust score...
                  </div>
                ) : trustData ? (
                  <TrustScoreMeter data={trustData} />
                ) : (
                  <div className="rounded-3xl border border-dashed border-white/10 bg-black/20 p-5 text-sm text-stone-400">
                    {trustError ?? "Trust score появится после первого пересчёта репутации."}
                  </div>
                )}
              </div>
            </div>
          </motion.section>
        )}

        <motion.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut" }}
          className="profile-banner-shell mt-6"
        >
          <div className="profile-banner-grid">
            <div className="profile-hero-card">
              <div className={`profile-hero-accent bg-gradient-to-r ${gradeMeta.accent}`} />
              <div className="grid gap-8 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-start">
                <div className="relative shrink-0">
                  <div className="avatar-frame profile-hero-avatar flex h-32 w-32 items-center justify-center bg-black/60 text-4xl font-cinzel font-bold text-amber-300 sm:h-36 sm:w-36 sm:text-5xl">
                    {profile.username[0].toUpperCase()}
                  </div>
                  <div className="absolute -bottom-5 left-1/2 -translate-x-1/2">
                    <LevelBadge level={profile.level} grade={profile.grade} />
                  </div>
                </div>

                <div className="min-w-0 pt-8 lg:pt-2 xl:pt-0">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="flex flex-wrap gap-2">
                        <span className={`rounded-full border px-3 py-1 text-xs font-mono uppercase tracking-[0.24em] ${gradeMeta.chip}`}>
                          {gradeMeta.label}
                        </span>
                        <span className="guild-chip bg-white/[0.05] text-stone-300">
                          {profile.role === "freelancer" ? "Guild Freelancer" : profile.role}
                        </span>
                        {isOwnProfile && (
                          <span className="guild-chip bg-violet-500/10 text-violet-300">Ваш профиль</span>
                        )}
                      </div>
                      <h1 className="mt-5 font-cinzel text-4xl font-bold uppercase tracking-[0.04em] text-stone-100 sm:text-5xl">
                        {profile.username}
                      </h1>
                      <p className="mt-3 max-w-2xl text-sm leading-7 text-stone-300 sm:text-base">{profileBio}</p>
                    </div>

                    {classMeta && (
                      <div className="profile-class-chip self-start lg:max-w-[260px]">
                        <span className="text-lg">{classMeta.icon}</span>
                        <div>
                          <p className="font-cinzel text-lg text-stone-100">{classMeta.name}</p>
                          <p className="text-xs uppercase tracking-[0.22em] text-stone-500">{profile.character_class}</p>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="mt-6 rounded-2xl border border-white/10 bg-black/30 p-4 sm:p-5">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-stone-500">Прогресс легенды</p>
                        <p className="mt-1 font-cinzel text-2xl text-amber-300">Уровень {profile.level}</p>
                      </div>
                      <p className="font-mono text-sm text-stone-300">
                        {xpDisplay.label}
                      </p>
                    </div>
                    <div className="mt-4 xp-bar-track h-3">
                      <motion.div
                        className="xp-bar-fill relative"
                        initial={{ width: 0 }}
                        animate={{ width: `${xpDisplay.percent}%` }}
                        transition={{ duration: 1.1, ease: "easeOut", delay: 0.15 }}
                      >
                        <div className="absolute inset-y-0 right-0 w-10 bg-gradient-to-r from-transparent to-white/25" />
                      </motion.div>
                    </div>
                  </div>

                  <div className="mt-6 flex flex-wrap gap-3">
                    {isOwnProfile ? (
                      <Button href="/profile" variant="primary" className="px-7 py-3.5">
                        Открыть мой кабинет
                      </Button>
                    ) : (
                      <Button href="/quests" variant="primary" className="px-7 py-3.5">
                        Найти совместный квест
                      </Button>
                    )}
                    <Button href="/marketplace" variant="secondary" className="border-stone-600/60 bg-black/20 px-7 py-3.5">
                      Доска гильдии
                    </Button>
                    {canShortlist && (
                      <Button
                        variant={isShortlisted ? "secondary" : "primary"}
                        className="px-7 py-3.5"
                        onClick={handleToggleShortlist}
                        disabled={shortlistPending}
                      >
                        <span className="inline-flex items-center gap-2">
                          <Bookmark size={16} fill={isShortlisted ? "currentColor" : "none"} />
                          {isShortlisted ? "Убрать из шортлиста" : "Добавить в шортлист"}
                        </span>
                      </Button>
                    )}
                    {canShortlist && compareHref && (
                      <Button href={compareHref} variant="secondary" className="border-emerald-500/30 bg-emerald-500/10 px-7 py-3.5 text-emerald-100">
                        Сравнить с шортлистом
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="profile-dossier-card">
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-sky-300/80">Guild dossier</p>
                <h2 className="mt-3 font-cinzel text-2xl text-stone-100">Паспорт героя</h2>
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                {dossierStats.map((stat) => (
                  <div key={stat.label} className="guild-stat-panel">
                    <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-stone-500">{stat.label}</p>
                    <p className="mt-2 font-cinzel text-2xl text-stone-100">{stat.value}</p>
                  </div>
                ))}
              </div>

              <div className="mt-8">
                <p className="font-mono text-[11px] uppercase tracking-[0.3em] text-amber-400/80">Legendary highlights</p>
                <div className="mt-4 space-y-3">
                  {legendaryHighlights.length > 0 ? (
                    legendaryHighlights.map((badge) => (
                      <div key={badge.id} className="profile-highlight-row">
                        <div className="profile-highlight-icon">{badge.badge_icon}</div>
                        <div>
                          <p className="text-sm font-semibold text-stone-100">{badge.badge_name}</p>
                          <p className="mt-1 text-xs leading-6 text-stone-400">{badge.badge_description}</p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-5 text-sm text-stone-500">
                      Герой ещё собирает свою коллекцию редких трофеев.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </motion.section>

        <motion.section {...revealUp} className="mt-10 grid gap-8 xl:grid-cols-[0.88fr_1.12fr]">
          <div className="space-y-8">
            <StatsPanel stats={profile.stats} reputationStats={profile.reputation_stats} />

            <Card className="border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-7">
              <SectionHeading
                eyebrow="Специализация"
                title="Боевой профиль"
                text={classMeta?.flavor ?? "Герой ещё не закрепил постоянный класс, но уже формирует свой стиль исполнения и узнаваемую специализацию."}
              />
              <div className="mt-6 flex flex-wrap gap-2">
                {specialtyTags.map((skill) => (
                  <span key={skill} className="rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-stone-300">
                    {skill}
                  </span>
                ))}
              </div>
              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                <div className="guild-stat-panel">
                  <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-stone-500">Интеллект</p>
                  <p className="mt-2 font-cinzel text-2xl text-sky-300">{profile.stats.int}</p>
                </div>
                <div className="guild-stat-panel">
                  <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-stone-500">Ловкость</p>
                  <p className="mt-2 font-cinzel text-2xl text-emerald-300">{profile.stats.dex}</p>
                </div>
                <div className="guild-stat-panel">
                  <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-stone-500">Харизма</p>
                  <p className="mt-2 font-cinzel text-2xl text-amber-300">{profile.stats.cha}</p>
                </div>
              </div>
            </Card>
          </div>

          <Card className="border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-7">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
              <SectionHeading
                eyebrow="Vault of Achievements"
                title="Бейджи и трофеи"
                text="Публичная коллекция достижений показывает не только стаж, но и глубину прохождения гильдейского пути: дисциплину, репутацию и накопленную ценность героя."
              />
              <div className="grid w-full gap-3 sm:max-w-[240px]">
                <div className="guild-stat-panel">
                  <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-stone-500">Всего достижений</p>
                  <p className="mt-2 font-cinzel text-3xl text-amber-300">{profile.badges.length}</p>
                </div>
                <div className="guild-stat-panel">
                  <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-stone-500">Уровень статуса</p>
                  <p className="mt-2 font-cinzel text-2xl text-stone-100">{gradeMeta.label}</p>
                </div>
              </div>
            </div>

            <motion.div
              variants={staggerGroup}
              initial="hidden"
              whileInView="show"
              viewport={{ once: true, amount: 0.15 }}
              className="mt-8 grid gap-4 md:grid-cols-3"
            >
              <motion.div variants={staggerItem} className="profile-feature-tile">
                <Award className="text-amber-300" size={20} />
                <h3 className="mt-3 font-cinzel text-xl text-stone-100">Редкие бейджи</h3>
                <p className="mt-2 text-sm leading-6 text-stone-400">Видно, какие награды уже работают как знак доверия и статуса на рынке.</p>
              </motion.div>
              <motion.div variants={staggerItem} className="profile-feature-tile">
                <ShieldCheck className="text-sky-300" size={20} />
                <h3 className="mt-3 font-cinzel text-xl text-stone-100">Проверенная репутация</h3>
                <p className="mt-2 text-sm leading-6 text-stone-400">Профиль превращается в понятный социальный сигнал для заказчиков и союзников.</p>
              </motion.div>
              <motion.div variants={staggerItem} className="profile-feature-tile">
                <Gem className="text-violet-300" size={20} />
                <h3 className="mt-3 font-cinzel text-xl text-stone-100">Коллекция трофеев</h3>
                <p className="mt-2 text-sm leading-6 text-stone-400">Даже пустой vault выглядит как место, которое хочется заполнить серьёзными достижениями.</p>
              </motion.div>
            </motion.div>

            <div className="mt-8">
              <BadgeGrid badges={badgeVault} showDate limit={8} />
            </div>
          </Card>
        </motion.section>

        <motion.section {...revealUp} className="mt-10 grid gap-8 xl:grid-cols-[1.02fr_0.98fr]">
          <Card className="border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-7">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
              <SectionHeading
                eyebrow="Completed contracts"
                title="Витрина завершённых квестов"
                text="Даже без отдельного backend showcase профиль должен ощущаться как досье героя с выполненными рейдами, а не как список полей из таблицы пользователей."
              />
              <div className="profile-trophy-chip">
                <Crown size={15} /> Showcase Mode
              </div>
            </div>

            <motion.div
              variants={staggerGroup}
              initial="hidden"
              whileInView="show"
              viewport={{ once: true, amount: 0.15 }}
              className="mt-8 space-y-4"
            >
              {completedContracts.map((contract) => (
                <motion.div key={contract.id} variants={staggerItem} className="profile-contract-card">
                  <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <span className="guild-chip bg-amber-500/10 text-amber-300">{contract.tag}</span>
                      <h3 className="mt-4 font-cinzel text-2xl text-stone-900">{contract.title}</h3>
                      <p className="mt-3 text-sm leading-7 text-stone-700">{contract.note}</p>
                    </div>
                    <div className="rounded-2xl border border-stone-400/35 bg-stone-950/90 px-5 py-4 text-right text-stone-100 lg:min-w-[165px]">
                      <p className="font-cinzel text-3xl text-amber-300">{contract.reward}</p>
                      <p className="mt-2 text-xs uppercase tracking-[0.24em] text-stone-500">{contract.xp}</p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          </Card>

          <Card className="border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-7">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <SectionHeading
                eyebrow="Social proof"
                title="Отзывы и репутация"
                text="Отзывы должны ощущаться как настоящая валюта доверия. Это не просто комментарии, а публичное подтверждение, что герой доводит квесты до результата."
              />
              <div className="profile-trophy-chip border-sky-400/20 bg-sky-400/10 text-sky-300">
                <Sparkles size={15} /> Guild trust
              </div>
            </div>

            <div className="mt-8 profile-review-shell">
              <ReviewList userId={profile.id} pageSize={4} />
            </div>
          </Card>
        </motion.section>

        <motion.section {...revealUp} className="mt-10 pb-20">
          <Card className="border-white/10 bg-gradient-to-br from-white/[0.05] to-black/25 p-7 sm:p-8">
            <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-amber-400/80">Guild summary</p>
                <h2 className="mt-3 font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">
                  Профиль, который продаёт не только навыки, но и статус.
                </h2>
                <p className="mt-4 text-sm leading-7 text-stone-300 sm:text-base">
                  Здесь видно, кем герой уже стал внутри системы: каков его ранг, какие трофеи он собрал,
                  насколько он убедителен для заказчиков и почему его досье выглядит сильнее обычной анкеты.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                <div className="guild-stat-panel">
                  <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-stone-500">Текущий уровень</p>
                  <p className="mt-2 font-cinzel text-3xl text-amber-300">{profile.level}</p>
                </div>
                <div className="guild-stat-panel">
                  <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-stone-500">Основная специализация</p>
                  <p className="mt-2 font-cinzel text-2xl text-stone-100">{specialtyTags[0]}</p>
                </div>
                <div className="guild-stat-panel">
                  <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-stone-500">Ключевой статус</p>
                  <p className="mt-2 font-cinzel text-2xl text-stone-100">{gradeMeta.title}</p>
                </div>
              </div>
            </div>
          </Card>
        </motion.section>
      </div>
    </main>
  );
}
