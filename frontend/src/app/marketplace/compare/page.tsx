"use client";

import { Suspense, useCallback, useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion } from "@/lib/motion";
import { ArrowLeft, CheckCircle, ShieldCheck, Sparkles, Star } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  getRecommendedFreelancers,
  getUserProfile,
  inviteFreelancerToQuest,
  type FreelancerRecommendation,
  type PublicUserProfile,
  getApiErrorMessage,
} from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import LevelBadge from "@/components/rpg/LevelBadge";
import { trackAnalyticsEvent } from "@/lib/analytics";

const GRADE_COLORS: Record<string, string> = {
  novice: "text-slate-300 border-slate-500/30",
  junior: "text-emerald-300 border-emerald-500/30",
  middle: "text-sky-300 border-sky-500/30",
  senior: "text-amber-300 border-amber-500/30",
};

const GRADE_RANK: Record<string, number> = {
  novice: 1,
  junior: 2,
  middle: 3,
  senior: 4,
};

const BUDGET_BAND_LABELS: Record<string, string> = {
  up_to_15k: "До 15k",
  "15k_to_50k": "15k-50k",
  "50k_to_150k": "50k-150k",
  "150k_plus": "150k+",
};

const AVAILABILITY_LABELS: Record<string, string> = {
  available: "Доступен",
  limited: "Ограниченно доступен",
  busy: "Загружен",
};

const BREAKDOWN_LABELS: Record<string, string> = {
  skill_overlap: "совпадают навыки",
  grade_fit: "грейд в допуске",
  trust_score: "сильный trust-сигнал",
  availability: "можно стартовать быстро",
  budget_fit: "комфортный бюджетный диапазон",
};

type CandidateInsight = {
  candidate: PublicUserProfile;
  recommendation?: FreelancerRecommendation;
  matchedSkills: string[];
  taskFitPercent: number | null;
  hintChips: string[];
  reliabilityScore: number;
  availabilityScore: number;
  experienceScore: number;
};

type DecisionCard = {
  title: string;
  description: string;
  winner: CandidateInsight;
  note: string;
  accent: string;
  icon: ReactNode;
};

function normalizeSkill(value: string) {
  return value.trim().toLowerCase();
}

function parseSkillContext(raw: string | null) {
  return (raw ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function getMatchedSkills(
  candidate: PublicUserProfile,
  requiredSkills: string[],
  recommendation?: FreelancerRecommendation,
) {
  if (recommendation?.matched_skills?.length) {
    return recommendation.matched_skills;
  }

  if (requiredSkills.length === 0) {
    return [];
  }

  const required = new Set(requiredSkills.map(normalizeSkill));
  return candidate.skills.filter((skill) => required.has(normalizeSkill(skill)));
}

function getTaskFitPercent(
  requiredSkills: string[],
  matchedSkills: string[],
  recommendation?: FreelancerRecommendation,
) {
  if (recommendation) {
    return Math.round(recommendation.match_score * 100);
  }
  if (requiredSkills.length === 0) {
    return null;
  }
  return Math.round((matchedSkills.length / requiredSkills.length) * 100);
}

function getBreakdownLabels(recommendation?: FreelancerRecommendation) {
  if (!recommendation?.match_breakdown) {
    return [];
  }

  return Object.entries(recommendation.match_breakdown)
    .sort((left, right) => right[1] - left[1])
    .filter(([, value]) => value >= 0.55)
    .slice(0, 2)
    .map(([key]) => BREAKDOWN_LABELS[key] ?? key);
}

function getReliabilityScore(candidate: PublicUserProfile) {
  const trustScore = candidate.trust_score ?? 0;
  const ratingScore = (candidate.avg_rating ?? 0) / 5;
  const completionScore = (candidate.completion_rate ?? 0) / 100;
  const reviewScore = Math.min((candidate.review_count ?? 0) / 10, 1);
  return trustScore * 0.45 + ratingScore * 0.25 + completionScore * 0.2 + reviewScore * 0.1;
}

function getAvailabilityScore(candidate: PublicUserProfile) {
  const status = candidate.availability_status?.toLowerCase() ?? "";
  let baseScore = 0.45;
  if (status.includes("available")) {
    baseScore = 1;
  } else if (status.includes("limited")) {
    baseScore = 0.6;
  } else if (status.includes("busy")) {
    baseScore = 0.25;
  }

  const responseHint = candidate.response_time_hint?.toLowerCase() ?? "";
  if (responseHint.includes("рабочего дня")) {
    return Math.min(1, baseScore + 0.1);
  }
  if (responseHint.includes("выборочно") || responseHint.includes("активных задач")) {
    return Math.max(0, baseScore - 0.15);
  }
  return baseScore;
}

function getExperienceScore(candidate: PublicUserProfile) {
  const gradeScore = (GRADE_RANK[candidate.grade] ?? 1) / 4;
  const confirmedScore = Math.min((candidate.confirmed_quest_count ?? 0) / 12, 1);
  const xpScore = Math.min(candidate.xp / 20000, 1);
  return gradeScore * 0.4 + confirmedScore * 0.4 + xpScore * 0.2;
}

function getHiringHintChips(
  candidate: PublicUserProfile,
  requiredSkills: string[],
  matchedSkills: string[],
  recommendation?: FreelancerRecommendation,
) {
  const chips: string[] = [];

  if (requiredSkills.length > 0 && matchedSkills.length > 0) {
    chips.push(`${matchedSkills.length}/${requiredSkills.length} ключевых навыков`);
  }

  chips.push(...getBreakdownLabels(recommendation));

  if (chips.length === 0) {
    if ((candidate.avg_rating ?? 0) >= 4.7 && (candidate.review_count ?? 0) >= 3) {
      chips.push("сильный рейтинг по отзывам");
    }
    if ((candidate.completion_rate ?? 0) >= 90) {
      chips.push("высокая завершаемость");
    }
    if ((candidate.trust_score ?? 0) >= 0.75) {
      chips.push("сильный trust-сигнал");
    }
    if (candidate.availability_status === "available") {
      chips.push("доступен для нового слота");
    }
    if ((candidate.confirmed_quest_count ?? 0) >= 8) {
      chips.push("богатая история delivery");
    }
  }

  return chips.slice(0, 3);
}

function pickInsight(items: CandidateInsight[], scorer: (item: CandidateInsight) => number) {
  const ranked = [...items].sort((left, right) => scorer(right) - scorer(left));
  return ranked[0] ?? null;
}

function CompareInner() {
  const params = useSearchParams();
  const { loading: authLoading } = useAuth();
  const [candidates, setCandidates] = useState<PublicUserProfile[]>([]);
  const [recommendationMap, setRecommendationMap] = useState<Record<string, FreelancerRecommendation>>({});
  const [recommendationNote, setRecommendationNote] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inviteStatus, setInviteStatus] = useState<Record<string, "idle" | "loading" | "sent" | "already_sent" | "error">>({});

  const rawIds = params.get("ids");
  const source = params.get("source") ?? "unknown";
  const questId = params.get("questId");
  const questTitle = params.get("questTitle")?.trim() || null;
  const rawSkills = params.get("skills");
  const requiredSkills = parseSkillContext(rawSkills);

  const loadCandidates = useCallback(async () => {
    if (!rawIds) {
      setError("Не указаны кандидаты для сравнения.");
      setLoading(false);
      return;
    }

    const ids = Array.from(new Set(rawIds.split(",").filter(Boolean))).slice(0, 4);
    if (ids.length < 2) {
      setError("Для сравнения нужно минимум 2 кандидата.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setRecommendationMap({});
    setRecommendationNote(null);
    trackAnalyticsEvent("compare_started", {
      source,
      candidate_ids: ids,
      candidate_count: ids.length,
      quest_id: questId ?? undefined,
      skill_context: requiredSkills,
    });

    try {
      const recommendationPromise = questId
        ? getRecommendedFreelancers(questId, 20)
        : Promise.resolve(null);
      const [profilesResult, recommendationResult] = await Promise.allSettled([
        Promise.all(ids.map((id) => getUserProfile(id))),
        recommendationPromise,
      ]);

      if (profilesResult.status === "rejected") {
        throw profilesResult.reason;
      }

      const profiles = profilesResult.value;
      setCandidates(profiles);

      let hasRecommendationContext = false;
      if (recommendationResult.status === "fulfilled" && recommendationResult.value) {
        const nextRecommendationMap = Object.fromEntries(
          recommendationResult.value.recommendations.map((item) => [item.freelancer.id, item]),
        );
        setRecommendationMap(nextRecommendationMap);
        const comparedCandidatesWithContext = ids.filter((id) => nextRecommendationMap[id]);
        hasRecommendationContext = comparedCandidatesWithContext.length > 0;
        if (comparedCandidatesWithContext.length > 0) {
          setRecommendationNote("Для fit и matched skills ниже используется backend matching по этому квесту.");
        } else if (questId) {
          setRecommendationNote("Сравнение открылось из квеста, но для этих кандидатов пока нет match hints. Оставили рыночные сигналы и shortlist-proof.");
        }
      } else if (questId) {
        setRecommendationNote("Подсказки совпадения по квесту временно недоступны. Сравнение работает по публичному proof и загрузке.");
      }

      trackAnalyticsEvent("compare_completed", {
        source,
        candidate_ids: ids,
        candidate_count: profiles.length,
        quest_id: questId ?? undefined,
        has_recommendation_context: hasRecommendationContext,
      });
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось загрузить профили."));
    } finally {
      setLoading(false);
    }
  }, [questId, rawIds, requiredSkills, source]);

  useEffect(() => {
    if (!authLoading) loadCandidates();
  }, [authLoading, loadCandidates]);

  async function handleInvite(freelancerId: string) {
    if (!questId) return;
    setInviteStatus((prev) => ({ ...prev, [freelancerId]: "loading" }));
    try {
      const result = await inviteFreelancerToQuest(questId, freelancerId);
      const nextStatus = result.already_sent ? "already_sent" : "sent";
      setInviteStatus((prev) => ({ ...prev, [freelancerId]: nextStatus }));
      trackAnalyticsEvent("quest_invite_sent", {
        quest_id: questId,
        freelancer_id: freelancerId,
        already_sent: result.already_sent,
        source,
      });
    } catch (err) {
      setInviteStatus((prev) => ({ ...prev, [freelancerId]: "error" }));
      console.error("Invite failed:", getApiErrorMessage(err));
    }
  }

  if (loading) {
    return (
      <div className="text-center py-20">
        <div className="w-12 h-12 border-4 border-violet-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-gray-400">Загрузка кандидатов...</p>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="p-8 text-center max-w-md mx-auto">
        <p className="text-red-400 mb-4">{error}</p>
        <Link href="/marketplace" className="text-amber-400 hover:underline text-sm">
          ← Вернуться на биржу
        </Link>
      </Card>
    );
  }

  const candidateInsights: CandidateInsight[] = candidates.map((candidate) => {
    const recommendation = recommendationMap[candidate.id];
    const matchedSkills = getMatchedSkills(candidate, requiredSkills, recommendation);
    return {
      candidate,
      recommendation,
      matchedSkills,
      taskFitPercent: getTaskFitPercent(requiredSkills, matchedSkills, recommendation),
      hintChips: getHiringHintChips(candidate, requiredSkills, matchedSkills, recommendation),
      reliabilityScore: getReliabilityScore(candidate),
      availabilityScore: getAvailabilityScore(candidate),
      experienceScore: getExperienceScore(candidate),
    };
  });

  const showTaskFit = questId !== null || requiredSkills.length > 0;
  const bestTaskFit = pickInsight(candidateInsights, (item) => {
    if (item.recommendation) {
      return item.recommendation.match_score * 0.65 + item.reliabilityScore * 0.2 + item.availabilityScore * 0.15;
    }
    if (item.taskFitPercent != null) {
      return item.taskFitPercent / 100 * 0.6 + item.reliabilityScore * 0.25 + item.availabilityScore * 0.15;
    }
    return item.reliabilityScore * 0.5 + item.experienceScore * 0.3 + item.availabilityScore * 0.2;
  });
  const mostReliable = pickInsight(candidateInsights, (item) => item.reliabilityScore * 0.7 + item.experienceScore * 0.3);
  const fastestStart = pickInsight(candidateInsights, (item) => item.availabilityScore * 0.8 + item.reliabilityScore * 0.2);
  const bestTaskFitPercent = Math.max(...candidateInsights.map((item) => item.taskFitPercent ?? 0), 0);

  const decisionCards: DecisionCard[] = [];

  if (bestTaskFit) {
    decisionCards.push({
      title: "Лучший fit",
      description: questTitle
        ? `Считаем совпадение не только по рейтингу, а в контексте квеста «${questTitle}».`
        : showTaskFit
          ? "Сначала смотрим на совпадение по навыкам, потом на надёжность и доступность."
          : "Если квест не задан, берём лучший общий hiring-сигнал рынка.",
      winner: bestTaskFit,
      note: bestTaskFit.taskFitPercent != null
        ? `${bestTaskFit.taskFitPercent}% fit${bestTaskFit.hintChips[0] ? ` • ${bestTaskFit.hintChips[0]}` : ""}`
        : bestTaskFit.hintChips[0] ?? "сильный общий рыночный сигнал",
      accent: "border-cyan-500/30 bg-cyan-500/10 text-cyan-100",
      icon: <Sparkles size={16} className="text-cyan-300" />,
    });
  }

  if (mostReliable) {
    decisionCards.push({
      title: "Самый надёжный",
      description: "Для снижения риска найма важнее всего история delivery: trust, рейтинг, завершаемость и число подтверждённых работ.",
      winner: mostReliable,
      note: `${mostReliable.candidate.avg_rating != null ? `${mostReliable.candidate.avg_rating.toFixed(1)} рейтинг` : "новый профиль"}${mostReliable.candidate.completion_rate != null ? ` • ${Math.round(mostReliable.candidate.completion_rate)}% завершаемость` : ""}`,
      accent: "border-emerald-500/30 bg-emerald-500/10 text-emerald-100",
      icon: <ShieldCheck size={16} className="text-emerald-300" />,
    });
  }

  if (fastestStart) {
    decisionCards.push({
      title: "Самый быстрый старт",
      description: "Когда нужен быстрый kickoff, смотрим на доступность и на косвенный SLA по отклику.",
      winner: fastestStart,
      note: `${fastestStart.candidate.availability_status ? AVAILABILITY_LABELS[fastestStart.candidate.availability_status] ?? fastestStart.candidate.availability_status : "статус не указан"}${fastestStart.candidate.response_time_hint ? ` • ${fastestStart.candidate.response_time_hint}` : ""}`,
      accent: "border-amber-500/30 bg-amber-500/10 text-amber-100",
      icon: <CheckCircle size={16} className="text-amber-300" />,
    });
  }

  const backHref = questId ? `/quests/${questId}` : "/marketplace";
  const backLabel = questId
    ? "Вернуться к квесту"
    : source === "marketplace"
      ? "Вернуться к шортлисту"
      : "Вернуться на биржу";
  const contextTitle = questTitle
    ? `Найм под квест «${questTitle}»`
    : showTaskFit
      ? "Сравнение под конкретную задачу"
      : "Shortlist compare без контекста квеста";
  const contextDescription = showTaskFit
    ? "Сверху собраны decision hints, а в таблице ниже видно, кто сильнее по fit, proof и стартовой скорости."
    : "Когда квест ещё не задан, сравнение помогает отсеять риск: кто надёжнее, кто свободнее и у кого лучше накопленный proof.";

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
      <Link
        href={backHref}
        className="inline-flex items-center gap-2 text-sm text-stone-400 hover:text-amber-300 transition-colors mb-6"
      >
        <ArrowLeft size={15} /> {backLabel}
      </Link>

      <h1 className="text-3xl font-cinzel text-amber-400 mb-2">Сравнение кандидатов</h1>
      <p className="text-gray-400 mb-8">
        Сравните до 4 кандидатов по ключевым показателям: рейтинг, опыт, навыки, подтверждённый delivery и сигнал по отклику.
      </p>

      <div className="grid gap-4 mb-8 xl:grid-cols-[1.2fr_1.8fr]">
        <Card className="border-white/10 bg-[linear-gradient(145deg,rgba(11,16,28,0.96),rgba(18,16,34,0.92))] p-6">
          <p className="text-[11px] uppercase tracking-[0.3em] text-cyan-300/80">Hiring guide</p>
          <h2 className="mt-3 font-cinzel text-2xl text-white">{contextTitle}</h2>
          <p className="mt-3 text-sm leading-6 text-stone-400">{contextDescription}</p>

          {requiredSkills.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {requiredSkills.map((skill) => (
                <span key={skill} className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-[11px] text-cyan-200">
                  {skill}
                </span>
              ))}
            </div>
          )}

          <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-stone-300">
            {recommendationNote ?? "Используйте этот экран, когда shortlist уже собран и нужно быстро понять, кого вести в следующий шаг найма."}
          </div>
        </Card>

        <div className="grid gap-3 md:grid-cols-3">
          {decisionCards.map((card) => (
            <Card key={card.title} className={`p-5 ${card.accent}`}>
              <div className="flex items-center gap-2 text-sm font-medium">
                {card.icon}
                <span>{card.title}</span>
              </div>
              <p className="mt-4 font-cinzel text-2xl text-white">{card.winner.candidate.username}</p>
              <p className="mt-2 text-sm text-stone-300">{card.note}</p>
              <p className="mt-3 text-xs leading-5 text-stone-400">{card.description}</p>
            </Card>
          ))}
        </div>
      </div>

      {/* Comparison grid */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[600px] border-collapse">
          <thead>
            <tr>
              <th className="text-left text-xs uppercase tracking-wider text-stone-500 pb-4 pr-4 w-40">
                Показатель
              </th>
              {candidates.map((c) => (
                <th key={c.id} className="text-center pb-4 px-3">
                  <Link href={`/users/${c.id}`} className="group">
                    <div className="flex flex-col items-center gap-2">
                      <div className="w-14 h-14 rounded-xl border border-white/10 bg-gradient-to-br from-violet-700/40 to-slate-950 flex items-center justify-center font-cinzel text-xl text-white font-bold">
                        {c.username.charAt(0).toUpperCase()}
                      </div>
                      <span className="font-cinzel text-sm text-white group-hover:text-amber-300 transition-colors">
                        {c.username}
                      </span>
                      <LevelBadge level={c.level} grade={c.grade} size="sm" />
                    </div>
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="text-sm">
            {/* Grade */}
            <CompareRow label="Грейд">
              {candidates.map((c) => (
                <td key={c.id} className="text-center py-3 px-3">
                  <span className={`inline-block rounded-full border px-3 py-1 text-xs uppercase tracking-wider ${GRADE_COLORS[c.grade] ?? "text-gray-400 border-gray-600"}`}>
                    {c.grade}
                  </span>
                </td>
              ))}
            </CompareRow>

            {showTaskFit && (
              <CompareRow label="Fit под задачу" icon={<Sparkles size={14} className="text-cyan-400" />}>
                {candidateInsights.map((item) => {
                  const isBest = item.taskFitPercent != null && item.taskFitPercent === bestTaskFitPercent && bestTaskFitPercent > 0;
                  return (
                    <td key={item.candidate.id} className={`text-center py-3 px-3 ${isBest ? "text-cyan-300 font-bold" : "text-stone-300"}`}>
                      {item.taskFitPercent != null ? `${item.taskFitPercent}%` : "—"}
                    </td>
                  );
                })}
              </CompareRow>
            )}

            {showTaskFit && (
              <CompareRow label="Совпавшие навыки">
                {candidateInsights.map((item) => (
                  <td key={item.candidate.id} className="text-center py-3 px-3">
                    <div className="flex flex-wrap justify-center gap-1">
                      {item.matchedSkills.length > 0 ? item.matchedSkills.slice(0, 4).map((skill) => (
                        <span key={skill} className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2 py-0.5 text-[10px] text-cyan-200">
                          {skill}
                        </span>
                      )) : <span className="text-stone-600 text-xs">—</span>}
                    </div>
                  </td>
                ))}
              </CompareRow>
            )}

            {/* Rating */}
            <CompareRow label="Рейтинг" icon={<Star size={14} className="text-amber-400" />}>
              {candidates.map((c) => {
                const best = Math.max(...candidates.map((x) => x.avg_rating ?? 0));
                const isBest = (c.avg_rating ?? 0) === best && best > 0;
                return (
                  <td key={c.id} className={`text-center py-3 px-3 ${isBest ? "text-amber-300 font-bold" : "text-stone-300"}`}>
                    {c.avg_rating != null ? c.avg_rating.toFixed(1) : "—"}
                    {(c.review_count ?? 0) > 0 && (
                      <span className="text-stone-500 text-xs ml-1">({c.review_count})</span>
                    )}
                  </td>
                );
              })}
            </CompareRow>

            {/* Completed quests */}
            <CompareRow label="Завершённых квестов" icon={<CheckCircle size={14} className="text-emerald-400" />}>
              {candidates.map((c) => {
                const best = Math.max(...candidates.map((x) => x.confirmed_quest_count ?? 0));
                const isBest = (c.confirmed_quest_count ?? 0) === best && best > 0;
                return (
                  <td key={c.id} className={`text-center py-3 px-3 ${isBest ? "text-emerald-300 font-bold" : "text-stone-300"}`}>
                    {c.confirmed_quest_count ?? 0}
                  </td>
                );
              })}
            </CompareRow>

            {/* Completion rate */}
            <CompareRow label="Завершаемость" icon={<ShieldCheck size={14} className="text-violet-400" />}>
              {candidates.map((c) => (
                <td key={c.id} className="text-center py-3 px-3 text-stone-300">
                  {c.completion_rate != null ? `${Math.round(c.completion_rate)}%` : "—"}
                </td>
              ))}
            </CompareRow>

            <CompareRow label="Типичный бюджет">
              {candidates.map((c) => (
                <td key={c.id} className="text-center py-3 px-3 text-stone-300">
                  {c.typical_budget_band ? BUDGET_BAND_LABELS[c.typical_budget_band] ?? c.typical_budget_band : "—"}
                </td>
              ))}
            </CompareRow>

            <CompareRow label="Доступность">
              {candidates.map((c) => (
                <td key={c.id} className="text-center py-3 px-3 text-stone-300">
                  {c.availability_status ? AVAILABILITY_LABELS[c.availability_status] ?? c.availability_status : "—"}
                </td>
              ))}
            </CompareRow>

            <CompareRow label="Сигнал по отклику">
              {candidates.map((c) => (
                <td key={c.id} className="text-center py-3 px-3 text-stone-300">
                  {c.response_time_hint ?? "—"}
                </td>
              ))}
            </CompareRow>

            {/* XP */}
            <CompareRow label="Опыт (XP)">
              {candidates.map((c) => {
                const best = Math.max(...candidates.map((x) => x.xp));
                const isBest = c.xp === best;
                return (
                  <td key={c.id} className={`text-center py-3 px-3 ${isBest ? "text-violet-300 font-bold" : "text-stone-300"}`}>
                    {c.xp.toLocaleString("ru-RU")}
                  </td>
                );
              })}
            </CompareRow>

            {/* Stats */}
            <CompareRow label="INT / DEX / CHA">
              {candidates.map((c) => (
                <td key={c.id} className="text-center py-3 px-3 font-mono text-xs">
                  <span className="text-blue-300">{c.stats.int}</span>
                  {" / "}
                  <span className="text-emerald-300">{c.stats.dex}</span>
                  {" / "}
                  <span className="text-amber-300">{c.stats.cha}</span>
                </td>
              ))}
            </CompareRow>

            {/* Skills */}
            <CompareRow label="Навыки">
              {candidates.map((c) => (
                <td key={c.id} className="text-center py-3 px-3">
                  <div className="flex flex-wrap justify-center gap-1">
                    {c.skills.slice(0, 5).map((s) => (
                      <span key={s} className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-stone-300">
                        {s}
                      </span>
                    ))}
                    {c.skills.length === 0 && <span className="text-stone-600 text-xs">—</span>}
                  </div>
                </td>
              ))}
            </CompareRow>

            {/* Badges */}
            <CompareRow label="Бейджи">
              {candidates.map((c) => (
                <td key={c.id} className="text-center py-3 px-3 text-stone-300">
                  {c.badges.length}
                </td>
              ))}
            </CompareRow>

            {/* Class */}
            <CompareRow label="Класс">
              {candidates.map((c) => (
                <td key={c.id} className="text-center py-3 px-3 text-stone-300 capitalize">
                  {c.character_class ?? "—"}
                </td>
              ))}
            </CompareRow>

            <CompareRow label="Подсказка к найму">
              {candidateInsights.map((item) => (
                <td key={item.candidate.id} className="text-center py-3 px-3">
                  <div className="flex flex-wrap justify-center gap-1">
                    {item.hintChips.length > 0 ? item.hintChips.map((chip) => (
                      <span key={chip} className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-stone-300">
                        {chip}
                      </span>
                    )) : <span className="text-stone-600 text-xs">Нужен живой созвон</span>}
                  </div>
                </td>
              ))}
            </CompareRow>

            {/* Action */}
            <tr>
              <td className="py-4 pr-4" />
              {candidates.map((c) => (
                <td key={c.id} className="text-center py-4 px-3">
                  <div className="flex flex-col items-center gap-2">
                    <Link
                      href={`/users/${c.id}`}
                      className="inline-block rounded-lg bg-violet-500/20 border border-violet-500/30 px-4 py-2 text-xs text-violet-200 hover:bg-violet-500/30 transition-colors"
                    >
                      Открыть профиль
                    </Link>
                    {questId && (() => {
                      const status = inviteStatus[c.id] ?? "idle";
                      if (status === "sent") {
                        return (
                          <span className="text-[11px] text-emerald-400 font-medium">
                            ✓ Приглашение отправлено
                          </span>
                        );
                      }
                      if (status === "already_sent") {
                        return (
                          <span className="text-[11px] text-stone-400">
                            Уже приглашён
                          </span>
                        );
                      }
                      if (status === "error") {
                        return (
                          <button
                            onClick={() => handleInvite(c.id)}
                            className="text-[11px] text-red-400 hover:text-red-300 underline"
                          >
                            Ошибка — повторить
                          </button>
                        );
                      }
                      return (
                        <button
                          onClick={() => handleInvite(c.id)}
                          disabled={status === "loading"}
                          className="inline-block rounded-lg bg-amber-500/20 border border-amber-500/30 px-4 py-2 text-xs text-amber-200 hover:bg-amber-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {status === "loading" ? "Отправка…" : "Пригласить"}
                        </button>
                      );
                    })()}
                  </div>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}

function CompareRow({
  label,
  icon,
  children,
}: {
  label: string;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <tr className="border-t border-white/5">
      <td className="py-3 pr-4 text-xs text-stone-500 whitespace-nowrap">
        <span className="flex items-center gap-1.5">
          {icon}
          {label}
        </span>
      </td>
      {children}
    </tr>
  );
}

export default function ComparePage() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Header />
      <main className="max-w-5xl mx-auto px-4 py-10">
        <Suspense
          fallback={
            <div className="text-center py-20">
              <div className="w-12 h-12 border-4 border-violet-500 border-t-transparent rounded-full animate-spin mx-auto" />
            </div>
          }
        >
          <CompareInner />
        </Suspense>
      </main>
    </div>
  );
}
