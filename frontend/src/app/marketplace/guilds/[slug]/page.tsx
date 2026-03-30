"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "@/lib/motion";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import LevelBadge from "@/components/rpg/LevelBadge";
import {
  getGuildProfile,
  getApiErrorMessage,
  GuildActivityEntry,
  GuildDetailResponse,
  GuildLeaderboardEntry,
  GuildPublicBadge,
  GuildPublicMember,
  GuildRewardCard,
  GuildSeasonalSet,
  UserGrade,
} from "@/lib/api";
import { getXpDisplay } from "@/lib/xp";

const GRADE_COLORS: Record<UserGrade, string> = {
  novice: "text-green-300 border-green-500/40 bg-green-500/10",
  junior: "text-cyan-300 border-cyan-500/40 bg-cyan-500/10",
  middle: "text-amber-300 border-amber-500/40 bg-amber-500/10",
  senior: "text-fuchsia-300 border-fuchsia-500/40 bg-fuchsia-500/10",
};

const ROLE_LABELS: Record<GuildPublicMember["role"], string> = {
  leader: "Leader",
  officer: "Officer",
  member: "Member",
};

function formatStamp(value: string) {
  return new Date(value).toLocaleString("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

import { formatMoney } from "@/lib/format";

function formatRoleTone(role: GuildPublicMember["role"]) {
  if (role === "leader") {
    return "border-amber-500/40 bg-amber-500/10 text-amber-200";
  }
  if (role === "officer") {
    return "border-cyan-500/40 bg-cyan-500/10 text-cyan-200";
  }
  return "border-white/10 bg-white/5 text-stone-300";
}

function formatRarityTone(rarity: GuildRewardCard["rarity"]) {
  if (rarity === "legendary") {
    return "border-amber-400/50 bg-amber-400/12 text-amber-100";
  }
  if (rarity === "epic") {
    return "border-fuchsia-400/40 bg-fuchsia-500/12 text-fuchsia-100";
  }
  if (rarity === "rare") {
    return "border-cyan-400/40 bg-cyan-500/12 text-cyan-100";
  }
  return "border-white/10 bg-white/5 text-stone-200";
}

function formatTierTone(tier: GuildDetailResponse["progression_snapshot"]["current_tier"]) {
  if (tier === "platinum") {
    return "border-cyan-400/40 bg-cyan-500/12 text-cyan-100";
  }
  if (tier === "gold") {
    return "border-amber-400/40 bg-amber-500/12 text-amber-100";
  }
  if (tier === "silver") {
    return "border-slate-300/30 bg-slate-200/10 text-slate-100";
  }
  return "border-orange-500/30 bg-orange-500/10 text-orange-100";
}

function formatTierLabel(tier: GuildDetailResponse["progression_snapshot"]["current_tier"]) {
  if (tier === "platinum") {
    return "Platinum";
  }
  if (tier === "gold") {
    return "Gold";
  }
  if (tier === "silver") {
    return "Silver";
  }
  return "Bronze";
}

function getAccentStyle(accent: GuildRewardCard["accent"]) {
  if (accent === "gold") {
    return "linear-gradient(90deg, #f59e0b, #fde68a)";
  }
  if (accent === "amber") {
    return "linear-gradient(90deg, #f59e0b, #fb923c)";
  }
  if (accent === "violet") {
    return "linear-gradient(90deg, #8b5cf6, #d946ef)";
  }
  if (accent === "cyan") {
    return "linear-gradient(90deg, #06b6d4, #67e8f9)";
  }
  if (accent === "emerald") {
    return "linear-gradient(90deg, #10b981, #6ee7b7)";
  }
  return "linear-gradient(90deg, #64748b, #cbd5e1)";
}

function MemberCard({ member }: { member: GuildPublicMember }) {
  const xpDisplay = getXpDisplay(member.xp, member.xp_to_next);

  return (
    <Link href={`/users/${member.id}`} className="block">
      <Card className="h-full border-white/10 bg-[linear-gradient(145deg,rgba(14,18,32,0.96),rgba(26,16,34,0.92))] p-5 hover:border-violet-400/40">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="relative h-12 w-12 overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-violet-700/40 to-slate-950">
              <div className="flex h-full w-full items-center justify-center font-cinzel text-lg font-bold text-white">
                {member.username.charAt(0).toUpperCase()}
              </div>
              <div className="absolute -bottom-1 -right-1 scale-75">
                <LevelBadge level={member.level} grade={member.grade} showGradeText={false} />
              </div>
            </div>
            <div>
              <div className="font-cinzel text-lg font-bold text-white">{member.username}</div>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] ${GRADE_COLORS[member.grade]}`}>
                  {member.grade}
                </span>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] ${formatRoleTone(member.role)}`}>
                  {ROLE_LABELS[member.role]}
                </span>
              </div>
            </div>
          </div>

          <div className="text-right text-xs text-stone-400">
            <div>Contribution</div>
            <div className="mt-1 font-cinzel text-xl font-bold text-violet-200">{member.contribution.toLocaleString("ru-RU")}</div>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <div className="xp-bar-track h-2 flex-1 overflow-hidden">
            <div className="xp-bar-fill h-full" style={{ width: `${xpDisplay.percent}%` }} />
          </div>
          <span className="text-[11px] uppercase tracking-[0.15em] text-stone-400">{member.xp.toLocaleString("ru-RU")} XP</span>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 text-center font-mono">
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

        <div className="mt-4 flex flex-wrap gap-2">
          {member.skills.length > 0 ? member.skills.slice(0, 4).map((skill) => (
            <span key={skill} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-stone-300">
              {skill}
            </span>
          )) : <span className="text-sm text-stone-500">Навыки ещё не опубликованы.</span>}
        </div>

        <div className="mt-4 text-xs text-stone-500">
          В составе с {new Date(member.joined_at).toLocaleDateString("ru-RU")}
          <span className="mx-2">•</span>
          {member.avg_rating ? `${member.avg_rating.toFixed(1)} рейтинг` : "Без рейтинга"}
          <span className="mx-2">•</span>
          {member.review_count} отзывов
        </div>
      </Card>
    </Link>
  );
}

function ActivityCard({ entry }: { entry: GuildActivityEntry }) {
  return (
    <Card className="border-white/10 bg-black/20 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.22em] text-violet-300/70">{entry.event_type.replaceAll("_", " ")}</div>
          <div className="mt-2 text-sm leading-6 text-stone-200">{entry.summary}</div>
          <div className="mt-2 text-xs text-stone-500">
            {entry.actor_username ?? "System"}
            {entry.quest_id && (
              <>
                <span className="mx-2">•</span>
                Quest {entry.quest_id}
              </>
            )}
          </div>
        </div>

        <div className="text-right text-xs text-stone-400">
          <div>{formatStamp(entry.created_at)}</div>
          <div className="mt-2 flex flex-wrap justify-end gap-2">
            {entry.treasury_delta > 0 && (
              <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-amber-200">
                +{formatMoney(entry.treasury_delta, { decimals: 2 })} treasury
              </span>
            )}
            {entry.guild_tokens_delta > 0 && (
              <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-cyan-200">
                +{entry.guild_tokens_delta} tokens
              </span>
            )}
            {entry.contribution_delta > 0 && (
              <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-violet-200">
                +{entry.contribution_delta} contribution
              </span>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

function TrophyCard({ trophy }: { trophy: GuildRewardCard }) {
  const categoryLabel =
    trophy.item_category === "cosmetic"
      ? "Косметика"
      : trophy.item_category === "equipable"
      ? "Артефакт"
      : "Коллекция";

  return (
    <Card className="overflow-hidden border-white/10 bg-[linear-gradient(145deg,rgba(16,20,34,0.96),rgba(8,10,18,0.98))] p-0">
      <div className="h-1.5 w-full" style={{ background: getAccentStyle(trophy.accent) }} />
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.24em] text-stone-500">{trophy.family}</div>
            <div className="mt-2 font-cinzel text-xl font-bold text-white">{trophy.name}</div>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            <span className={`rounded-full border px-2 py-1 text-[10px] uppercase tracking-[0.18em] ${formatRarityTone(trophy.rarity)}`}>
              {trophy.rarity}
            </span>
            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[9px] uppercase tracking-[0.14em] text-stone-400">
              {categoryLabel}
            </span>
          </div>
        </div>

        <p className="mt-3 text-sm leading-6 text-stone-300">{trophy.description}</p>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-stone-400">
          <span>{formatStamp(trophy.dropped_at)}</span>
          {trophy.awarded_to_username && (
            <>
              <span>•</span>
              <span>{trophy.awarded_to_username}</span>
            </>
          )}
          <span>•</span>
          <span>Quest {trophy.source_quest_id}</span>
        </div>
      </div>
    </Card>
  );
}

function LeaderboardCard({
  entry,
}: {
  entry: GuildLeaderboardEntry;
}) {
  const { rank, member, trophy_count, family_label } = entry;

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-amber-500/30 bg-amber-500/10 font-cinzel text-lg font-bold text-amber-100">
            {rank}
          </div>
          <div>
            <div className="font-cinzel text-lg font-bold text-white">{member.username}</div>
            <div className="mt-1 flex flex-wrap gap-2">
              <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] ${formatRoleTone(member.role)}`}>
                {ROLE_LABELS[member.role]}
              </span>
              <span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] ${GRADE_COLORS[member.grade]}`}>
                lvl {member.level}
              </span>
            </div>
          </div>
        </div>

        <div className="text-right">
          <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">Contribution</div>
          <div className="mt-1 font-cinzel text-2xl font-bold text-violet-100">{member.contribution.toLocaleString("ru-RU")}</div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-xs text-stone-300">
        <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-cyan-100">
          {trophy_count} trophies
        </span>
        <span className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1">
          {family_label ? `${family_label} focus` : "no family chain yet"}
        </span>
      </div>
    </div>
  );
}

function SeasonalSetCard({ seasonalSet }: { seasonalSet: GuildSeasonalSet }) {
  return (
    <Card className="overflow-hidden border-white/10 bg-[linear-gradient(145deg,rgba(14,18,32,0.96),rgba(18,14,26,0.92))] p-0">
      <div className="h-1.5 w-full" style={{ background: getAccentStyle(seasonalSet.accent) }} />
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-stone-500">{seasonalSet.season_code}</div>
            <div className="mt-2 font-cinzel text-xl font-bold text-white">{seasonalSet.label}</div>
          </div>
          <span className={`rounded-full border px-2 py-1 text-[10px] uppercase tracking-[0.18em] ${seasonalSet.rarity ? formatRarityTone(seasonalSet.rarity) : "border-white/10 bg-white/5 text-stone-300"}`}>
            {seasonalSet.rarity ?? "unstarted"}
          </span>
        </div>

        <div className="mt-4 flex items-center justify-between text-xs text-stone-400">
          <span>{seasonalSet.collected_cards}/{seasonalSet.target_cards} cards</span>
          <span>{seasonalSet.progress_percent}%</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full" style={{ width: `${seasonalSet.progress_percent}%`, background: getAccentStyle(seasonalSet.accent) }} />
        </div>

        <div className="mt-4 flex flex-wrap gap-2 text-xs text-stone-300">
          <span className={`rounded-full border px-2.5 py-1 ${seasonalSet.completed ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100" : "border-white/10 bg-white/5 text-stone-300"}`}>
            {seasonalSet.completed ? "set completed" : `${seasonalSet.missing_cards} to go`}
          </span>
          <span className="rounded-full border border-white/10 bg-black/20 px-2.5 py-1">
            family {seasonalSet.family}
          </span>
        </div>

        <div className="mt-4 rounded-2xl border border-amber-500/15 bg-black/20 p-3 text-xs text-stone-300">
          <div className="text-[10px] uppercase tracking-[0.18em] text-amber-300/70">Set reward</div>
          <div className="mt-2 font-cinzel text-lg text-white">{seasonalSet.reward_badge_name}</div>
          <div className="mt-1 text-stone-400">{seasonalSet.reward_label}</div>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-amber-100">
              +{formatMoney(seasonalSet.reward_treasury_bonus, { decimals: 2 })} treasury
            </span>
            <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-cyan-100">
              +{seasonalSet.reward_guild_tokens_bonus} tokens
            </span>
          </div>
          <div
            className={`mt-3 rounded-full border px-2.5 py-1 text-center text-[10px] uppercase tracking-[0.16em] ${seasonalSet.reward_claimed ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100" : "border-white/10 bg-white/5 text-stone-400"}`}
          >
            {seasonalSet.reward_claimed
              ? `claimed ${seasonalSet.reward_claimed_at ? formatStamp(seasonalSet.reward_claimed_at) : ""}`.trim()
              : seasonalSet.completed
                ? "ready on next confirmed quest"
                : "locked"}
          </div>
        </div>
      </div>
    </Card>
  );
}

function GuildBadgeCard({ badge }: { badge: GuildPublicBadge }) {
  return (
    <Card className="overflow-hidden border-white/10 bg-[linear-gradient(145deg,rgba(20,16,28,0.94),rgba(10,12,20,0.98))] p-0">
      <div className="h-1.5 w-full" style={{ background: getAccentStyle(badge.accent) }} />
      <div className="p-4">
        <div className="text-[10px] uppercase tracking-[0.22em] text-stone-500">Guild badge</div>
        <div className="mt-2 font-cinzel text-xl font-bold text-white">{badge.name}</div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-stone-300">
          {badge.family && (
            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1">family {badge.family}</span>
          )}
          {badge.season_code && (
            <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-cyan-100">{badge.season_code}</span>
          )}
        </div>
        <div className="mt-3 text-xs text-stone-500">Awarded {formatStamp(badge.awarded_at)}</div>
      </div>
    </Card>
  );
}

export default function GuildPublicPage() {
  const params = useParams();
  const slug = typeof params.slug === "string" ? params.slug.trim() : "";

  const [data, setData] = useState<GuildDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadGuild = useCallback(async () => {
    if (!slug) {
      setError("Некорректный slug гильдии.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await getGuildProfile(slug);
      setData(response);
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось загрузить страницу гильдии."));
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    loadGuild();
  }, [loadGuild]);

  const guild = data?.guild;
  const members = useMemo(() => data?.members ?? [], [data?.members]);
  const activity = data?.activity ?? [];
  const trophies = data?.trophies ?? [];
  const seasonalSets = data?.seasonal_sets ?? [];
  const badges = data?.badges ?? [];
  const progressionSnapshot = data?.progression_snapshot;

  const stats = useMemo(() => {
    const avgLevel = members.length > 0
      ? (members.reduce((sum, member) => sum + member.level, 0) / members.length).toFixed(1)
      : "0.0";
    return [
      { label: "Состав", value: guild ? `${guild.member_count}/${guild.member_limit}` : "0/20", note: "активные участники", tone: "amber" as const },
      { label: "Treasury", value: formatMoney(guild?.treasury_balance ?? 0, { decimals: 2 }), note: "казна гильдии", tone: "gold" as const },
      { label: "Guild tokens", value: guild?.guild_tokens ?? 0, note: "внутренний ресурс", tone: "cyan" as const },
      { label: "Avg level", value: avgLevel, note: "средняя сила состава", tone: "purple" as const },
    ];
  }, [guild, members]);

  const leaderboard = progressionSnapshot?.leaderboard ?? [];
  const completedSeasonalSets = progressionSnapshot?.completed_sets ?? 0;
  const tierBenefits = progressionSnapshot?.tier_benefits ?? [];
  const currentTier = progressionSnapshot?.current_tier ?? "bronze";
  const milestones = progressionSnapshot?.milestones ?? [];
  const topContributors = progressionSnapshot?.top_contributors ?? [];

  if (loading) {
    return (
      <main className="min-h-screen bg-[var(--bg-primary)]">
        <Header />
        <div className="container mx-auto px-4 py-12">
          <Card className="p-12 text-center">
            <div className="mx-auto mb-4 h-16 w-16 animate-spin rounded-full border-4 border-violet-500 border-t-transparent" />
            <p className="text-stone-400">Загрузка страницы гильдии...</p>
          </Card>
        </div>
      </main>
    );
  }

  if (error || !guild) {
    return (
      <main className="min-h-screen bg-[var(--bg-primary)]">
        <Header />
        <div className="container mx-auto max-w-lg px-4 py-12">
          <Card className="border-red-500/30 p-8 text-center">
            <div className="mb-4 text-5xl">⚠️</div>
            <h2 className="text-xl font-bold text-red-300">{error ?? "Гильдия не найдена"}</h2>
            <div className="mt-6 flex justify-center gap-3">
              <Button variant="secondary" onClick={loadGuild}>Повторить</Button>
              <Button href="/marketplace" variant="primary">К рынку</Button>
            </div>
          </Card>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--bg-primary)] text-stone-100">
      <Header />

      <div className="container mx-auto px-4 py-8">
        <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
          <Link href="/marketplace?mode=top-guilds" className="text-sm text-stone-400 transition-colors hover:text-amber-300">
            ← Назад к top guilds
          </Link>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.03 }} className="mt-6">
          <GuildStatusStrip
            mode="guild"
            eyebrow="Public guild page"
            title={`${guild.name} получила собственную публичную страницу`}
            description={guild.description || "Теперь гильдия видна как отдельная публичная сущность: состав, экономика, квестовая история и след прогрессии собраны в одном месте."}
            stats={stats}
            signals={[
              { label: `Rating ${guild.rating}`, tone: "amber" },
              { label: guild.season_position ? `Season #${guild.season_position}` : "Season unranked", tone: "purple" },
              { label: `${guild.confirmed_quests} confirmed quests`, tone: "cyan" },
            ]}
          />
        </motion.div>

        <motion.section initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.06 }} className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_420px]">
          <Card className="border-amber-500/20 bg-[linear-gradient(145deg,rgba(28,18,12,0.92),rgba(10,12,20,0.98))] p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-[10px] uppercase tracking-[0.26em] text-amber-400/80">Guild dossier</div>
                <h1 className="mt-2 font-cinzel text-4xl font-bold text-white">{guild.name}</h1>
                <div className="mt-3 flex flex-wrap gap-2">
                  {guild.top_skills.map((skill) => (
                    <span key={skill} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-right">
                <div className="text-[10px] uppercase tracking-[0.18em] text-amber-200/70">Leader</div>
                <div className="mt-1 font-cinzel text-xl font-bold text-amber-100">{guild.leader_username ?? "не назначен"}</div>
              </div>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Card variant="stat" className="p-4"><div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">XP</div><div className="mt-2 font-cinzel text-2xl font-bold text-white">{guild.total_xp.toLocaleString("ru-RU")}</div></Card>
              <Card variant="stat" className="p-4"><div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">Rating</div><div className="mt-2 font-cinzel text-2xl font-bold text-white">{guild.rating}</div></Card>
              <Card variant="stat" className="p-4"><div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">Avg review</div><div className="mt-2 font-cinzel text-2xl font-bold text-white">{guild.avg_rating ? guild.avg_rating.toFixed(1) : "n/a"}</div></Card>
              <Card variant="stat" className="p-4"><div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">Confirmed quests</div><div className="mt-2 font-cinzel text-2xl font-bold text-white">{guild.confirmed_quests}</div></Card>
            </div>
          </Card>

          <Card className="border-white/10 bg-black/20 p-6">
            <div className="text-[10px] uppercase tracking-[0.24em] text-stone-500">Progress rails</div>
            <div className="mt-4 space-y-4">
              <div>
                <div className="mb-2 flex items-center justify-between text-xs text-stone-400">
                  <span>Member occupancy</span>
                  <span>{guild.member_count}/{guild.member_limit}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-gradient-to-r from-amber-500 to-orange-400" style={{ width: `${Math.min(100, (guild.member_count / guild.member_limit) * 100)}%` }} />
                </div>
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between text-xs text-stone-400">
                  <span>Quest reputation</span>
                  <span>{guild.confirmed_quests}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-violet-400" style={{ width: `${Math.min(100, guild.confirmed_quests * 5)}%` }} />
                </div>
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between text-xs text-stone-400">
                  <span>Treasury pressure</span>
                  <span>{formatMoney(guild.treasury_balance, { decimals: 2 })}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-amber-300" style={{ width: `${Math.min(100, guild.treasury_balance / 10)}%` }} />
                </div>
              </div>
            </div>
          </Card>
        </motion.section>

        <motion.section initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.09 }} className="mt-8 grid gap-8 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
          <div>
            <div className="mb-4">
              <h2 className="font-cinzel text-3xl font-bold text-white">Состав гильдии</h2>
              <p className="mt-2 text-sm text-stone-400">Публичный roster показывает роли, contribution и специализацию каждого активного участника.</p>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              {members.map((member) => (
                <MemberCard key={member.id} member={member} />
              ))}
            </div>
          </div>

          <div>
            <div className="mb-6">
              <h2 className="font-cinzel text-3xl font-bold text-white">Seasonal tier</h2>
              <p className="mt-2 text-sm text-stone-400">Гильдия теперь качается как сезонная сущность: tier, XP до следующего ранга и активные бонусы видны прямо на публичной странице.</p>
            </div>

            <Card className="border-white/10 bg-black/20 p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.22em] text-stone-500">Current season</div>
                  <div className="mt-2 font-cinzel text-3xl font-bold text-white">{progressionSnapshot?.season_code ?? "n/a"}</div>
                </div>
                <div className={`rounded-full border px-3 py-1 text-xs uppercase tracking-[0.18em] ${formatTierTone(currentTier)}`}>
                  {formatTierLabel(currentTier)} tier
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">Seasonal XP</div>
                  <div className="mt-2 font-cinzel text-2xl font-bold text-white">{(progressionSnapshot?.seasonal_xp ?? 0).toLocaleString("ru-RU")}</div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">Season rank</div>
                  <div className="mt-2 font-cinzel text-2xl font-bold text-white">{progressionSnapshot?.season_rank ? `#${progressionSnapshot.season_rank}` : "unranked"}</div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-stone-500">Tier XP bonus</div>
                  <div className="mt-2 font-cinzel text-2xl font-bold text-white">+{progressionSnapshot?.xp_bonus_percent ?? 0}%</div>
                </div>
              </div>

              <div className="mt-5">
                <div className="mb-2 flex items-center justify-between text-xs text-stone-400">
                  <span>{progressionSnapshot?.next_tier ? `Progress to ${formatTierLabel(progressionSnapshot.next_tier)}` : "Max tier reached"}</span>
                  <span>
                    {progressionSnapshot?.next_tier_xp
                      ? `${(progressionSnapshot?.seasonal_xp ?? 0).toLocaleString("ru-RU")}/${progressionSnapshot.next_tier_xp.toLocaleString("ru-RU")}`
                      : `${(progressionSnapshot?.seasonal_xp ?? 0).toLocaleString("ru-RU")} XP`}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-gradient-to-r from-amber-500 via-cyan-400 to-violet-400" style={{ width: `${progressionSnapshot?.progress_percent ?? 0}%` }} />
                </div>
                <div className="mt-2 text-xs text-stone-500">
                  {progressionSnapshot?.next_tier
                    ? `${(progressionSnapshot?.xp_to_next_tier ?? 0).toLocaleString("ru-RU")} XP to next tier`
                    : "Guild reached the highest seasonal tier."}
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-2">
                {tierBenefits.map((benefit) => (
                  <span key={benefit} className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-xs text-violet-100">
                    {benefit}
                  </span>
                ))}
              </div>
            </Card>

            <div className="mb-6 mt-8">
              <h2 className="font-cinzel text-3xl font-bold text-white">Contribution ladder</h2>
              <p className="mt-2 text-sm text-stone-400">Лидерборд связывает вклад в гильдию с реальными trophy drops и показывает, кто сейчас тянет progression loop.</p>
            </div>

            <Card className="border-white/10 bg-black/20 p-5">
              <div className="space-y-3">
                {leaderboard.map((entry) => (
                  <LeaderboardCard key={entry.member.id} entry={entry} />
                ))}
              </div>

              <div className="mt-5 border-t border-white/10 pt-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-[10px] uppercase tracking-[0.22em] text-stone-500">Seasonal collection status</div>
                  <div className="text-xs text-stone-500">{completedSeasonalSets}/{seasonalSets.length} completed</div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {seasonalSets.length > 0 ? seasonalSets.slice(0, 4).map((seasonalSet) => (
                    <span key={seasonalSet.family} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-stone-300">
                      {seasonalSet.family} {seasonalSet.collected_cards}/{seasonalSet.target_cards}
                    </span>
                  )) : (
                    <span className="text-sm text-stone-500">Сезонные наборы появятся после первых card drops.</span>
                  )}
                </div>
              </div>
            </Card>

            {milestones.length > 0 && (
              <>
                <div className="mb-4 mt-8">
                  <h2 className="font-cinzel text-3xl font-bold text-white">Milestone progress</h2>
                  <p className="mt-2 text-sm text-stone-400">Общие milestone&apos;ы гильдии — открываются по мере набора seasonal XP. Каждый порог несёт свою награду.</p>
                </div>
                <div className="space-y-2">
                  {milestones.map((ms) => (
                    <div
                      key={ms.milestone_code}
                      className={`flex items-center gap-3 rounded-xl border p-3 ${
                        ms.unlocked
                          ? "border-emerald-500/30 bg-emerald-500/5"
                          : "border-white/10 bg-black/20 opacity-60"
                      }`}
                    >
                      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm ${
                        ms.unlocked ? "bg-emerald-500/20 text-emerald-300" : "bg-white/5 text-stone-500"
                      }`}>
                        {ms.unlocked ? "✓" : "○"}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-semibold ${ms.unlocked ? "text-emerald-200" : "text-stone-400"}`}>
                            {ms.label}
                          </span>
                          <span className="text-[10px] text-stone-500">{ms.threshold_xp.toLocaleString("ru-RU")} XP</span>
                        </div>
                        <div className="text-xs text-stone-500">{ms.description}</div>
                      </div>
                      <div className="shrink-0 text-xs text-stone-500">{ms.reward_description}</div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {topContributors.length > 0 && (
              <>
                <div className="mb-4 mt-8">
                  <h2 className="font-cinzel text-3xl font-bold text-white">Top contributors</h2>
                  <p className="mt-2 text-sm text-stone-400">Участники с наибольшим вкладом в гильдию — ранжированы по contribution points.</p>
                </div>
                <Card className="border-white/10 bg-black/20 p-5">
                  <div className="space-y-2">
                    {topContributors.map((tc) => (
                      <div key={tc.user_id} className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] p-3">
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-500/20 font-cinzel text-sm font-bold text-violet-200">
                          {tc.rank}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-semibold text-white">{tc.username}</div>
                          <div className="text-[10px] uppercase tracking-[0.14em] text-stone-500">{tc.role}</div>
                        </div>
                        <div className="text-right">
                          <div className="font-cinzel text-lg font-bold text-violet-200">{tc.contribution.toLocaleString("ru-RU")}</div>
                          <div className="text-[10px] text-stone-500">contribution</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </>
            )}

            <div className="mb-4 mt-8">
              <h2 className="font-cinzel text-3xl font-bold text-white">История прогрессии</h2>
              <p className="mt-2 text-sm text-stone-400">Последние события из guild activity: создание, вступления, выходы и подтверждённые квесты.</p>
            </div>
            <div className="space-y-3">
              {activity.length > 0 ? activity.map((entry) => (
                <ActivityCard key={entry.id} entry={entry} />
              )) : (
                <Card className="border-white/10 bg-black/20 p-6 text-sm text-stone-500">
                  История пока пуста. Она начнёт наполняться с новыми участниками и подтверждёнными квестами.
                </Card>
              )}
            </div>
          </div>
        </motion.section>

        <motion.section initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.12 }} className="mt-8">
          <div className="mb-8">
            <div className="mb-4 flex items-end justify-between gap-4">
              <div>
                <h2 className="font-cinzel text-3xl font-bold text-white">Guild badges</h2>
                <p className="mt-2 text-sm text-stone-400">Публичные знаки отличия гильдии теперь живут как отдельная серверная сущность, а не только как seasonal reward metadata.</p>
              </div>
              <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.18em] text-stone-400">
                {badges.length} total badges
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {badges.length > 0 ? badges.map((badge) => (
                <GuildBadgeCard key={badge.id} badge={badge} />
              )) : (
                <Card className="border-white/10 bg-black/20 p-6 text-sm text-stone-500 md:col-span-2 xl:col-span-3">
                  Публичные guild badges появятся после первого закрытого seasonal set reward.
                </Card>
              )}
            </div>
          </div>

          <div className="mb-8">
            <div className="mb-4 flex items-end justify-between gap-4">
              <div>
                <h2 className="font-cinzel text-3xl font-bold text-white">Seasonal collections</h2>
                <p className="mt-2 text-sm text-stone-400">Серверный seasonal set summary по guild families: видно, какие серии уже собираются и какие ещё не закрыты.</p>
              </div>
              <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.18em] text-stone-400">
                {completedSeasonalSets} completed sets
              </div>
            </div>

            {seasonalSets.length > 0 ? (
              <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
                {seasonalSets.map((seasonalSet) => (
                  <SeasonalSetCard key={seasonalSet.family} seasonalSet={seasonalSet} />
                ))}
              </div>
            ) : (
              <Card className="border-white/10 bg-black/20 p-6 text-sm text-stone-500">
                Сезонные наборы пока пусты. Они начнут заполняться, когда гильдия накопит первые трофеи по families.
              </Card>
            )}
          </div>

          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <h2 className="font-cinzel text-3xl font-bold text-white">Trophy feed</h2>
              <p className="mt-2 text-sm text-stone-400">Публичная витрина card drops, полученных за подтверждённые guild quests.</p>
            </div>
            <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-[0.18em] text-stone-400">
              {trophies.length} recent drops
            </div>
          </div>

          {trophies.length > 0 ? (
            <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
              {trophies.map((trophy) => (
                <TrophyCard key={trophy.id} trophy={trophy} />
              ))}
            </div>
          ) : (
            <Card className="border-white/10 bg-black/20 p-6 text-sm text-stone-500">
              У этой гильдии пока нет трофеев. Первый drop появится после следующего подтверждённого квеста.
            </Card>
          )}
        </motion.section>
      </div>
    </main>
  );
}