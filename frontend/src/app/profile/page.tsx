/**
 * Страница профиля пользователя
 * 
 * Показывает данные авторизованного пользователя
 * Доступна только после входа
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "@/lib/motion";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import LevelBadge from "@/components/rpg/LevelBadge";
import StatsPanel from "@/components/rpg/StatsPanel";
import Button from "@/components/ui/Button";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import SignalChip from "@/components/ui/SignalChip";
import { equipArtifact, getApiErrorMessage, getMyBadges, getMyClass, getPlayerCardDrops, getUserArtifacts, getUserProfile, unequipArtifact } from "@/lib/api";
import type { ArtifactCabinet, PlayerCardCollection, PublicUserProfile, SoloCardDrop, UserArtifact, UserBadgeEarned, UserClassInfo } from "@/lib/api";
import BadgeGrid from "@/components/rpg/BadgeGrid";
import ClassBadge from "@/components/rpg/ClassBadge";
import ClassSelector from "@/components/rpg/ClassSelector";
import { getXpDisplay } from "@/lib/xp";
import { useSWRFetch } from "@/hooks/useSWRFetch";
import { User, Briefcase, Award, Shield, Star } from 'lucide-react';
import dynamic from "next/dynamic";

interface ProfilePageData {
  profile: PublicUserProfile;
  earnedBadges: UserBadgeEarned[];
  classInfo: UserClassInfo | null;
  artifactCabinet: ArtifactCabinet | null;
  playerCards: PlayerCardCollection | null;
}

// Client-only: make API calls → skip SSR to avoid hydration mismatch
const WalletPanel = dynamic(() => import("@/components/rpg/WalletPanel"), { ssr: false });
const ReviewList = dynamic(() => import("@/components/rpg/ReviewList"), { ssr: false });
const ReferralPanel = dynamic(() => import("@/components/growth/ReferralPanel").then(m => ({ default: m.ReferralPanel })), { ssr: false });

const RARITY_TONE: Record<string, string> = {
  legendary: "border-amber-400/50 bg-amber-400/10 text-amber-100",
  epic: "border-fuchsia-400/40 bg-fuchsia-500/10 text-fuchsia-100",
  rare: "border-cyan-400/40 bg-cyan-500/10 text-cyan-100",
  common: "border-white/10 bg-white/5 text-stone-200",
};

const CATEGORY_LABELS: Record<string, string> = {
  cosmetic: "Косметика",
  collectible: "Коллекционное",
  equipable: "Артефакт",
};

const SOLO_RARITY_TONE: Record<string, string> = {
  legendary: "border-amber-400/50 bg-amber-400/10 text-amber-100",
  epic: "border-fuchsia-400/40 bg-fuchsia-500/10 text-fuchsia-100",
  rare: "border-cyan-400/40 bg-cyan-500/10 text-cyan-100",
};

function SoloDropsPanel({ collection }: { collection: PlayerCardCollection }) {
  return (
    <div className="rpg-card p-6 mt-6">
      <h3 className="text-xl font-cinzel text-cyan-400 mb-1 flex items-center gap-2 border-b border-cyan-900/30 pb-2">
        <Shield className="text-cyan-400" size={24} aria-hidden="true" />
        Соло-коллекция
        <span className="ml-auto text-xs font-mono text-stone-400">{collection.total} шт.</span>
      </h3>
      <p className="text-xs text-stone-500 mb-4">{collection.drop_rate_note}</p>

      {collection.drops.length === 0 ? (
        <p className="text-sm text-stone-500 text-center py-4">
          Соло-карточки появятся после подтверждения квестов вне гильдии.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {collection.drops.map((drop: SoloCardDrop) => (
            <div
              key={drop.id}
              className={`rounded-xl border p-4 ${
                SOLO_RARITY_TONE[drop.rarity] ?? "border-white/10 bg-white/5 text-stone-200"
              }`}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="text-sm font-cinzel font-semibold leading-tight">{drop.name}</span>
                <span
                  className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.15em] ${
                    SOLO_RARITY_TONE[drop.rarity] ?? "border-white/10"
                  }`}
                >
                  {drop.rarity}
                </span>
              </div>
              <p className="text-xs text-stone-400 leading-relaxed mb-2">{drop.description}</p>
              <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.12em] text-stone-500">
                <span>{CATEGORY_LABELS[drop.item_category] ?? drop.item_category}</span>
                <span>{new Date(drop.dropped_at).toLocaleDateString("ru-RU")}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ArtifactCabinetPanel({
  cabinet,
  actionError,
  pendingArtifactId,
  onToggleEquip,
}: {
  cabinet: ArtifactCabinet;
  actionError: string | null;
  pendingArtifactId: string | null;
  onToggleEquip: (artifact: UserArtifact) => void;
}) {
  const [activeTab, setActiveTab] = useState<"all" | "cosmetic" | "collectible" | "equipable">("all");

  const allItems = [...cabinet.cosmetics, ...cabinet.collectibles, ...cabinet.equipable];
  const displayed =
    activeTab === "all"
      ? allItems
      : activeTab === "cosmetic"
      ? cabinet.cosmetics
      : activeTab === "collectible"
      ? cabinet.collectibles
      : cabinet.equipable;

  const tabs: { key: typeof activeTab; label: string; count: number }[] = [
    { key: "all", label: "Все", count: cabinet.total },
    { key: "cosmetic", label: "Косметика", count: cabinet.cosmetics.length },
    { key: "collectible", label: "Коллекции", count: cabinet.collectibles.length },
    { key: "equipable", label: "Артефакты", count: cabinet.equipable.length },
  ];

  return (
    <div className="rpg-card p-6 mt-6">
      <h3 className="text-xl font-cinzel text-amber-500 mb-4 flex items-center gap-2 border-b border-amber-900/30 pb-2">
        <Shield className="text-amber-500" size={24} aria-hidden="true" /> Коллекция артефактов
        <span className="ml-auto text-xs font-mono text-stone-400">{cabinet.total} шт.</span>
      </h3>

      {/* Category tabs */}
      <div className="flex flex-wrap gap-2 mb-5">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-full border px-3 py-1 text-xs uppercase tracking-[0.15em] transition-colors ${
              activeTab === tab.key
                ? "border-amber-500/60 bg-amber-500/15 text-amber-200"
                : "border-white/10 bg-white/5 text-stone-400 hover:border-white/20"
            }`}
          >
            {tab.label} {tab.count > 0 && <span className="opacity-70">({tab.count})</span>}
          </button>
        ))}
      </div>

      {actionError && (
        <div className="mb-4 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {actionError}
        </div>
      )}

      {displayed.length === 0 ? (
        <p className="text-sm text-stone-500 text-center py-4">В этой категории пусто.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {displayed.map((item) => (
            <div
              key={item.id}
              className={`rounded-xl border p-4 ${RARITY_TONE[item.rarity] ?? RARITY_TONE.common}`}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="text-sm font-cinzel font-semibold leading-tight">{item.name}</span>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.15em] ${RARITY_TONE[item.rarity] ?? RARITY_TONE.common}`}>
                  {item.rarity}
                </span>
              </div>
              <p className="text-xs text-stone-400 leading-relaxed mb-2">{item.description}</p>
              {item.equipped_effect_summary && (
                <p className="mb-3 text-[11px] leading-relaxed text-amber-200/85">{item.equipped_effect_summary}</p>
              )}
              <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.12em] text-stone-500">
                <span>{CATEGORY_LABELS[item.item_category] ?? item.item_category}</span>
                <span>{new Date(item.dropped_at).toLocaleDateString("ru-RU")}</span>
              </div>
              {item.item_category === "equipable" && (
                <div className="mt-3 flex items-center justify-between gap-3">
                  <span
                    className={`rounded-full border px-2 py-1 text-[10px] uppercase tracking-[0.14em] ${
                      item.is_equipped
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
                        : "border-white/10 bg-black/20 text-stone-400"
                    }`}
                  >
                    {item.is_equipped ? "Equipped" : "Stored"}
                  </span>
                  <button
                    type="button"
                    disabled={pendingArtifactId === item.id}
                    onClick={() => onToggleEquip(item)}
                    className={`rounded-full border px-3 py-1.5 text-[11px] uppercase tracking-[0.14em] transition-colors ${
                      pendingArtifactId === item.id
                        ? "cursor-wait border-white/10 bg-white/5 text-stone-500"
                        : item.is_equipped
                        ? "border-amber-500/40 bg-amber-500/10 text-amber-100 hover:border-amber-400/60"
                        : "border-cyan-500/40 bg-cyan-500/10 text-cyan-100 hover:border-cyan-400/60"
                    }`}
                  >
                    {pendingArtifactId === item.id ? "Saving..." : item.is_equipped ? "Unequip" : "Equip"}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ProfileMetricTile({
  title,
  value,
  hint,
}: {
  title: string;
  value: string | number;
  hint: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/30 p-4 backdrop-blur-sm">
      <div className="text-[11px] uppercase tracking-[0.25em] text-gray-500">{title}</div>
      <div className="mt-2 text-2xl font-bold text-white">{value}</div>
      <div className="mt-1 text-xs text-gray-400">{hint}</div>
    </div>
  );
}

function ProfileActionTile({
  title,
  description,
  icon,
  onClick,
}: {
  title: string;
  description: string;
  icon: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group rounded-2xl border border-white/10 bg-gray-950/60 p-5 text-left transition-all hover:border-amber-500/40 hover:bg-gray-900/80 hover:shadow-[0_0_25px_rgba(217,119,6,0.12)]"
    >
      <div className="text-2xl">{icon}</div>
      <div className="mt-4 text-lg font-cinzel font-bold text-white group-hover:text-amber-200">
        {title}
      </div>
      <div className="mt-2 text-sm leading-relaxed text-gray-400">
        {description}
      </div>
    </button>
  );
}

export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [classModalOpen, setClassModalOpen] = useState(false);
  const [artifactActionError, setArtifactActionError] = useState<string | null>(null);
  const [pendingArtifactId, setPendingArtifactId] = useState<string | null>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [isAuthenticated, authLoading, router]);

  const {
    data,
    error,
    isLoading,
    mutate,
  } = useSWRFetch<ProfilePageData>(
    !authLoading && isAuthenticated && user?.id ? (["profile-page", user.id, user.role] as const) : null,
    async () => {
      if (!user?.id) {
        throw new Error("Не удалось определить пользователя");
      }

      const playerCardsPromise = user.role === "freelancer"
        ? getPlayerCardDrops().catch((err) => { console.warn("Failed to load player cards:", err); return null; })
        : Promise.resolve(null);

      const [profile, badgeData, artifactCabinet, playerCards] = await Promise.all([
        getUserProfile(user.id),
        getMyBadges(),
        getUserArtifacts().catch((err) => { console.warn("Failed to load artifacts:", err); return null; }),
        playerCardsPromise,
      ]);

      let classInfo: UserClassInfo | null = null;

      if (profile.character_class) {
        try {
          const currentClassInfo = await getMyClass();
          classInfo = currentClassInfo.has_class ? currentClassInfo : null;
        } catch (e) {
          console.warn("Failed to load class info", e);
          classInfo = null;
        }
      }

      return {
        profile,
        earnedBadges: badgeData.badges,
        classInfo,
        artifactCabinet,
        playerCards,
      };
    },
    { revalidateOnFocus: false },
  );

  const profile = data?.profile ?? null;
  const earnedBadges = data?.earnedBadges ?? [];
  const classInfo = data?.classInfo ?? null;
  const artifactCabinet = data?.artifactCabinet ?? null;
  const playerCards = data?.playerCards ?? null;
  const errorMessage = error
    ? getApiErrorMessage(error, "Не удалось загрузить профиль. Попробуйте позже.")
    : null;

  const handleArtifactToggle = useCallback(async (artifact: UserArtifact) => {
    setPendingArtifactId(artifact.id);
    setArtifactActionError(null);
    try {
      const result = artifact.is_equipped
        ? await unequipArtifact(artifact.id)
        : await equipArtifact(artifact.id);
      await mutate(
        (current) =>
          current
            ? {
                ...current,
                artifactCabinet: result.cabinet,
              }
            : current,
        { revalidate: false },
      );
    } catch (err) {
      setArtifactActionError(
        getApiErrorMessage(err, artifact.is_equipped ? "Не удалось снять артефакт." : "Не удалось экипировать артефакт."),
      );
    } finally {
      setPendingArtifactId(null);
    }
  }, [mutate]);

  if (authLoading || (isAuthenticated && isLoading)) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto">
            <div className="glass-card p-6 mb-6">
              <div className="animate-pulse space-y-4">
                <div className="h-32 bg-gray-700/50 rounded-full w-32 mx-auto" />
                <div className="h-8 bg-gray-700/50 rounded w-48 mx-auto" />
                <div className="h-4 bg-gray-700/50 rounded w-32 mx-auto" />
              </div>
            </div>
          </div>
        </div>
      </main>
    );
  }

  // Error loading profile — show retry card instead of blank page
  if (errorMessage) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto">
            <div className="glass-card p-6 !border-red-500/50">
              <div className="text-center">
                <span className="text-4xl mb-2 block" aria-hidden="true">⚠️</span>
                <h3 className="text-xl font-bold text-red-400 mb-2">Ошибка загрузки профиля</h3>
                <p className="text-gray-400 mb-4">{errorMessage}</p>
                <Button onClick={() => void mutate()} variant="secondary">
                  🔄 Повторить
                </Button>
              </div>
            </div>
          </div>
        </div>
      </main>
    );
  }

  // If not authenticated, redirect is in progress
  if (!isAuthenticated || !profile) {
    return null;
  }

  const xpDisplay = getXpDisplay(profile.xp, profile.xp_to_next);
  const statSum = profile.stats.int + profile.stats.dex + profile.stats.cha;
  const careerMoments = [
    {
      title: "Вступление в гильдию",
      detail: new Date(profile.created_at).toLocaleDateString("ru-RU"),
      tone: "slate" as const,
    },
    {
      title: "Текущий грейд",
      detail: profile.grade.toUpperCase(),
      tone: "gold" as const,
    },
    {
      title: "Классовая идентичность",
      detail: classInfo?.name_ru ?? profile.character_class ?? "Класс еще не выбран",
      tone: classInfo ? ("purple" as const) : ("slate" as const),
    },
    {
      title: "Собрано трофеев",
      detail: `${earnedBadges.length} достижений`,
      tone: earnedBadges.length > 0 ? ("emerald" as const) : ("slate" as const),
    },
  ];
  const identitySignals = [
    { label: `${profile.role === "client" ? "Клиент" : profile.role === "admin" ? "Админ" : "Фрилансер"} mode`, tone: "slate" as const },
    { label: `${profile.skills?.length ?? 0} skill markers`, tone: "cyan" as const },
    { label: `${earnedBadges.length} trophy markers`, tone: earnedBadges.length > 0 ? ("gold" as const) : ("slate" as const) },
    { label: classInfo ? "Class memory active" : "Class memory locked", tone: classInfo ? ("purple" as const) : ("amber" as const) },
  ];
  const profileActions = [
    {
      title: "Dashboard",
      description: "Сводка активности, бюджетов и прогресса по контрактам.",
      icon: "📊",
      onClick: () => router.push("/profile/dashboard"),
    },
    {
      title: "Мои квесты",
      description: "Открыть журнал активных и завершённых контрактов.",
      icon: "📋",
      onClick: () => router.push("/profile/quests"),
    },
    {
      title: profile.role === "freelancer" ? "Класс и перки" : "Биржа заказов",
      description:
        profile.role === "freelancer"
          ? "Управляйте классом, бонусами и развитием персонажа."
          : "Смотрите лучших исполнителей и собирайте команду.",
      icon: profile.role === "freelancer" ? "🔮" : "💼",
      onClick: () =>
        router.push(profile.role === "freelancer" ? "/profile/class" : "/marketplace"),
    },
    {
      title: "Доска заданий",
      description: "Перейти к новым контрактам и возможностям платформы.",
      icon: "⚔️",
      onClick: () => router.push("/quests"),
    },
  ];

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-4xl mx-auto"
        >
          {/* Заголовок страницы */}
          <div className="mb-8 text-center">
            <p className="text-xs uppercase tracking-[0.35em] text-amber-500/80">Guild Hub</p>
            <h1 className="mt-3 text-4xl font-bold text-center text-white">
              👤 Личное дело героя
            </h1>
            <p className="mt-3 text-sm text-gray-400">
              Прогресс, репутация, класс, достижения и активность — в одном штабе.
            </p>
          </div>

          <GuildStatusStrip
            mode="profile"
            eyebrow="Hero dossier"
            title="Личное дело теперь выглядит как живая карьерная карта"
            description="Профиль показывает не только XP и уровень. Здесь собраны идентичность игрока, память о ключевых этапах, трофеи и текущий статус внутри мира гильдии."
            stats={[
              { label: "Уровень", value: profile.level, note: "текущая высота", tone: "gold" },
              { label: "Грейд", value: profile.grade.toUpperCase(), note: "ранг внутри гильдии", tone: "purple" },
              { label: "Статов", value: statSum, note: "INT + DEX + CHA", tone: "cyan" },
              { label: "Трофеи", value: earnedBadges.length, note: "собранные достижения", tone: earnedBadges.length > 0 ? "emerald" : "slate" },
            ]}
            signals={identitySignals}
            className="mb-6"
          />

          {/* Onboarding nudge for freelancers with incomplete profile */}
          {profile.role === "freelancer" &&
            !profile.onboarding_completed && (
              <Link
                href="/profile/setup"
                className="mb-6 flex items-center justify-between rounded-xl border border-amber-500/20 bg-amber-500/5 px-5 py-4 transition-colors hover:bg-amber-500/10"
              >
                <div>
                  <p className="text-sm font-medium text-amber-300">
                    Завершите настройку профиля
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Готовность профиля: {profile.profile_completeness_percent ?? 0}%. Добавьте доступность, portfolio и proof signals, чтобы стать hireable быстрее.
                  </p>
                </div>
                <span className="text-amber-400 text-sm">Настроить →</span>
              </Link>
            )}

          {/* Основная карточка профиля */}
          <div className="rpg-card p-8 flex flex-col gap-8 relative overflow-hidden mb-6">
            <div className="absolute top-0 right-0 w-64 h-64 bg-purple-600 rounded-full blur-[100px] opacity-20 pointer-events-none"></div>
            <div className="absolute bottom-0 left-10 w-48 h-48 bg-amber-600 rounded-full blur-[100px] opacity-10 pointer-events-none"></div>

            <div className="flex flex-col lg:flex-row gap-8 items-start lg:items-center relative z-10">
              <div className="avatar-frame relative z-10 shrink-0">
                <div className="w-full h-full rounded-full flex items-center justify-center bg-gradient-to-br from-purple-700 to-purple-950">
                  <span className="text-5xl font-bold text-white select-none">
                    {profile.username[0].toUpperCase()}
                  </span>
                </div>
                {/* Level badge — small corner overlay */}
                <div className="absolute -bottom-1 -right-1 bg-amber-500 text-black text-xs font-bold rounded-full w-8 h-8 flex items-center justify-center border-2 border-gray-900 z-20">
                  {profile.level}
                </div>
              </div>

              <div className="flex-1 w-full relative z-10">
                <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <h1 className="text-4xl font-cinzel text-gray-100 font-bold tracking-wider mb-2 drop-shadow-md">
                      {profile.username}
                    </h1>
                    <p className="text-amber-600/80 font-inter uppercase tracking-[0.2em] text-sm mb-3 flex items-center gap-2">
                      {profile.role === 'client' ? <Briefcase size={14} /> : <User size={14} />}
                      {profile.role === 'client'
                        ? 'Клиент'
                        : profile.role === 'admin'
                        ? 'Администратор'
                        : 'Фрилансер'}
                    </p>
                    <p className="max-w-2xl text-sm leading-relaxed text-gray-400">
                      {profile.bio?.trim()
                        ? profile.bio
                        : "Пока без биографии. Заполните профиль, чтобы клиенты и союзники быстрее понимали ваш стиль работы."}
                    </p>
                  </div>
                  <LevelBadge level={profile.level} grade={profile.grade} size="lg" showGradeText={true} />
                </div>

                {/* Интегрированный XP бар */}
                <div className="mt-4">
                  <div className="flex justify-between font-mono text-sm text-gray-400 mb-2">
                    <span>ОПЫТ</span>
                    <span className="text-purple-400">{xpDisplay.label}</span>
                  </div>
                  <div className="xp-bar-track relative overflow-hidden">
                     <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${xpDisplay.percent}%` }}
                        transition={{ duration: 1, delay: 0.3 }}
                        className="xp-bar-fill h-full absolute top-0 left-0" 
                     />
                  </div>
                </div>

                <div className="mt-6 grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <ProfileMetricTile title="Грейд" value={profile.grade.toUpperCase()} hint="Текущий ранг в гильдии" />
                  <ProfileMetricTile title="Достижения" value={earnedBadges.length} hint="Получено значков и трофеев" />
                  <ProfileMetricTile title="Навыки" value={profile.skills?.length ?? 0} hint="Заявлено компетенций" />
                  <ProfileMetricTile title="Сумма статов" value={statSum} hint="INT + DEX + CHA" />
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3 mb-6">
            {profileActions.map((action) => (
              <ProfileActionTile
                key={action.title}
                title={action.title}
                description={action.description}
                icon={action.icon}
                onClick={action.onClick}
              />
            ))}
          </div>

          {/* Статы */}
          <StatsPanel stats={profile.stats} reputationStats={profile.reputation_stats} />

          {/* Faction Alignment */}
          {profile.faction_alignment && profile.faction_alignment.faction_id !== "none" && (
            <div className="rpg-card p-6 mt-6">
              <h3 className="text-xl font-cinzel text-amber-500 mb-4 flex items-center gap-2 border-b border-amber-900/30 pb-2">
                ⚔️ Faction Alignment
              </h3>
              <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-lg font-semibold text-white">
                      {profile.faction_alignment.faction_name}
                    </span>
                    <SignalChip
                      tone={
                        profile.faction_alignment.faction_id === "vanguard"
                          ? "amber"
                          : profile.faction_alignment.faction_id === "keepers"
                          ? "purple"
                          : "emerald"
                      }
                    >
                      {profile.faction_alignment.rank}
                    </SignalChip>
                  </div>
                  <p className="text-sm text-gray-400">
                    {profile.faction_alignment.alignment_note}
                  </p>
                </div>
                <div className="shrink-0 text-center px-6 py-3 rounded-xl border border-white/10 bg-black/25">
                  <div className="text-2xl font-bold text-white">
                    {profile.faction_alignment.contribution_score}
                  </div>
                  <div className="text-[10px] uppercase tracking-[0.2em] text-gray-500 mt-1">
                    contribution
                  </div>
                </div>
              </div>
              <div className="mt-4">
                <div className="flex justify-between text-xs text-gray-400 mb-1">
                  <span>Contribution score</span>
                  <span>{profile.faction_alignment.contribution_score}/100</span>
                </div>
                <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      profile.faction_alignment.faction_id === "vanguard"
                        ? "bg-amber-500"
                        : profile.faction_alignment.faction_id === "keepers"
                        ? "bg-purple-500"
                        : "bg-emerald-500"
                    }`}
                    style={{ width: `${profile.faction_alignment.contribution_score}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          <div className="grid gap-6 mt-6 lg:grid-cols-[1.15fr_0.85fr]">
            <section className="rpg-card p-6">
              <h3 className="text-xl font-cinzel text-amber-500 mb-4 flex items-center gap-2 border-b border-amber-900/30 pb-2">
                🏆 Trophy Room
              </h3>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-black/25 p-5">
                  <p className="text-[11px] uppercase tracking-[0.25em] text-gray-500">Редкие достижения</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {earnedBadges.slice(0, 4).map((badge) => (
                      <SignalChip key={badge.badge_id} tone="gold">{badge.badge_name}</SignalChip>
                    ))}
                    {earnedBadges.length === 0 && <p className="text-sm text-gray-500">Трофейная стена пока пуста — первые значки появятся после ключевых шагов в гильдии.</p>}
                  </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-black/25 p-5">
                  <p className="text-[11px] uppercase tracking-[0.25em] text-gray-500">Signature markers</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <SignalChip tone="purple">{profile.grade.toUpperCase()}</SignalChip>
                    {profile.character_class && <SignalChip tone="cyan">{profile.character_class}</SignalChip>}
                    {(profile.skills ?? []).slice(0, 3).map((skill) => (
                      <SignalChip key={skill} tone="slate">{skill}</SignalChip>
                    ))}
                  </div>
                </div>
              </div>
            </section>

            <section className="rpg-card p-6">
              <h3 className="text-xl font-cinzel text-amber-500 mb-4 flex items-center gap-2 border-b border-amber-900/30 pb-2">
                📜 Career Timeline
              </h3>
              <div className="space-y-4">
                {careerMoments.map((moment, index) => (
                  <div key={moment.title} className="flex gap-4 rounded-2xl border border-white/8 bg-black/20 p-4">
                    <div className="flex flex-col items-center">
                      <div className={`h-3 w-3 rounded-full ${moment.tone === "gold" ? "bg-amber-400" : moment.tone === "purple" ? "bg-violet-400" : moment.tone === "emerald" ? "bg-emerald-400" : "bg-gray-500"}`} />
                      {index < careerMoments.length - 1 && <div className="mt-2 h-full w-px bg-white/10" />}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-white">{moment.title}</div>
                      <div className="mt-1 text-sm text-gray-400">{moment.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>

          {/* Класс персонажа */}
          {profile.role === 'freelancer' && (
            <div className="rpg-card p-6 mt-6">
              <h3 className="text-xl font-cinzel text-amber-500 mb-4 flex items-center gap-2 border-b border-amber-900/30 pb-2">
                <Shield className="text-amber-500" size={24} aria-hidden="true" /> Класс
              </h3>
              {classInfo ? (
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <ClassBadge classInfo={classInfo} size="md" />
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => router.push("/profile/class")}
                        className="text-sm text-gray-400 hover:text-red-400 transition-colors border border-gray-700/50 hover:border-red-500/50 px-3 py-1 rounded"
                      >
                        🔮 Перки
                      </button>
                      <button
                        onClick={() => setClassModalOpen(true)}
                        className="text-sm text-gray-400 hover:text-amber-400 transition-colors border border-gray-700/50 hover:border-amber-500/50 px-3 py-1 rounded"
                      >
                        Управление
                      </button>
                    </div>
                  </div>
                  
                  {/* Phase 2: Show active bonuses directly on profile */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm mt-4">
                    {classInfo.active_bonuses?.length > 0 && (
                      <div className="bg-emerald-900/10 border border-emerald-900/30 rounded p-3">
                        <strong className="text-emerald-400 block mb-1">Активные бонусы:</strong>
                        <ul className="text-gray-300 space-y-1 list-disc list-inside ml-2">
                          {classInfo.active_bonuses.map(b => (
                            <li key={b.key}>{b.label}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {classInfo.weaknesses?.length > 0 && (
                      <div className="bg-red-900/10 border border-red-900/30 rounded p-3">
                        <strong className="text-red-400 block mb-1">Ограничения класса:</strong>
                        <ul className="text-gray-400 space-y-1 list-disc list-inside ml-2">
                          {classInfo.weaknesses.map(b => (
                            <li key={b.key}>{b.label}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center py-4">
                  <p className="text-gray-400 mb-3">
                    {profile.level >= 5
                      ? "Вы можете выбрать класс персонажа!"
                      : `Система классов доступна с уровня 5 (ваш: ${profile.level})`}
                  </p>
                  {profile.level >= 5 && (
                    <button
                      onClick={() => setClassModalOpen(true)}
                      className="px-4 py-2 bg-gradient-to-r from-amber-700 to-amber-900 text-white font-cinzel rounded border border-amber-500/50 shadow-[0_0_15px_rgba(217,119,6,0.3)] hover:scale-105 transition-all"
                    >
                      ⚔️ Выбрать класс
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          <ClassSelector
            isOpen={classModalOpen}
            onClose={() => setClassModalOpen(false)}
            userLevel={profile.level}
            currentClass={profile.character_class}
            onClassSelected={() => void mutate()}
          />

          {/* Кошелёк */}
          <WalletPanel />

          {/* Реферальная программа (фрилансеры) */}
          {profile.role === "freelancer" && (
            <div className="mt-6">
              <ReferralPanel />
            </div>
          )}

          {/* Бейджи */}
          <div className="rpg-card p-6 mt-6">
            <h3 className="text-xl font-cinzel text-amber-500 mb-4 flex items-center gap-2 border-b border-amber-900/30 pb-2">
              <Award className="text-amber-500" size={24} aria-hidden="true" focusable="false" /> Достижения
              <Link href="/badges" className="text-xs text-amber-500/70 hover:text-amber-400 transition-colors ml-auto">
                Все достижения →
              </Link>
            </h3>
            <BadgeGrid badges={earnedBadges} />
          </div>

          {/* Отзывы (только для фрилансеров) */}
          {profile.role === "freelancer" && (
            <div className="rpg-card p-6 mt-6">
              <h3 className="text-xl font-cinzel text-amber-500 mb-4 flex items-center gap-2 border-b border-amber-900/30 pb-2">
                <Star className="text-amber-500" size={24} aria-hidden="true" /> Отзывы
              </h3>
              <ReviewList userId={profile.id} />
            </div>
          )}

          {/* Артефакты и косметика (гильдейские трофеи) */}
          {artifactCabinet && artifactCabinet.total > 0 && (
            <ArtifactCabinetPanel
              cabinet={artifactCabinet}
              actionError={artifactActionError}
              pendingArtifactId={pendingArtifactId}
              onToggleEquip={handleArtifactToggle}
            />
          )}

          {/* Соло-карточки (план 11) */}
          {playerCards && (
            <SoloDropsPanel collection={playerCards} />
          )}

          {/* Навигация */}
          <div className="flex flex-wrap gap-4 mt-6">
            <Button variant="secondary" onClick={() => router.push("/profile/quests")}>
              📋 Мои квесты
            </Button>
            <Button variant="secondary" onClick={() => router.push("/quests")}>
              🔍 Найти квест
            </Button>
            <Button variant="secondary" onClick={() => router.push("/marketplace")}>
              💼 Биржа заказов
            </Button>
          </div>
        </motion.div>
      </div>
    </main>
  );
}



