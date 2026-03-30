"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Star, Users, ArrowRight, Sparkles } from "lucide-react";
import { getRecommendedFreelancers, getTalentMarket, type RecommendedFreelancerCard } from "@/lib/api";
import LevelBadge from "@/components/rpg/LevelBadge";
import TrustScoreBadge from "@/components/rpg/TrustScoreBadge";

interface Props {
  /** Existing quest ID to fetch backend recommendations */
  questId?: string;
  /** Skills to match against talent market (quest skills) */
  skills?: string[];
  /** Maximum number of recommendations to show */
  limit?: number;
  /** Optional title override */
  title?: string;
}

export default function RecommendedTalentRail({
  questId,
  skills = [],
  limit = 3,
  title = "Подходящие исполнители",
}: Props) {
  const [members, setMembers] = useState<Array<RecommendedFreelancerCard & { matchedSkills: string[]; matchScore?: number }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        if (questId) {
          const response = await getRecommendedFreelancers(questId, limit);
          if (cancelled) return;
          setMembers(
            response.recommendations.map((item) => ({
              ...item.freelancer,
              matchedSkills: item.matched_skills,
              matchScore: item.match_score,
            })),
          );
          return;
        }

        const search = skills.length > 0 ? skills[0] : undefined;
        const res = await getTalentMarket({
          limit: limit * 3,
          sortBy: "rating",
          search,
        });

        if (cancelled) return;

        const scored = res.members.map((member) => {
          const matchedSkills = member.skills.filter((skill) =>
            skills.some((requiredSkill) => requiredSkill.trim().toLowerCase() === skill.trim().toLowerCase()),
          );
          return {
            ...member,
            matchedSkills,
            matchScore: matchedSkills.length,
          };
        });

        scored.sort((a, b) => (b.matchScore ?? 0) - (a.matchScore ?? 0));
        setMembers(scored.slice(0, limit));
      } catch {
        if (!cancelled) {
          setMembers([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [questId, skills, limit]);

  if (loading) {
    return (
      <div className="space-y-3">
        <h3 className="text-sm font-cinzel text-cyan-400 flex items-center gap-2">
          <Users size={14} /> {title}
        </h3>
        {Array.from({ length: limit }).map((_, i) => (
          <div key={i} className="h-16 rounded-lg bg-white/5 animate-pulse" />
        ))}
      </div>
    );
  }

  if (members.length === 0) {
    return (
      <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4 text-center">
        <p className="text-xs text-stone-500 mb-2">Пока нет подходящих исполнителей</p>
        <Link
          href="/marketplace"
          className="text-xs text-amber-400 hover:underline"
        >
          Открыть биржу талантов →
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-cinzel text-cyan-400 flex items-center gap-2">
        <Users size={14} /> {title}
      </h3>

      {members.map((m) => (
        <Link
          key={m.id}
          href={`/users/${m.id}`}
          className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] p-3 hover:bg-white/[0.05] transition-colors group"
        >
          <div className="w-10 h-10 rounded-lg border border-white/10 bg-gradient-to-br from-violet-700/40 to-slate-950 flex items-center justify-center font-cinzel text-sm text-white font-bold shrink-0">
            {m.username.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm text-white group-hover:text-amber-300 transition-colors truncate">
                {m.username}
              </span>
              <LevelBadge level={m.level} grade={m.grade} size="sm" />
              <TrustScoreBadge score={m.trust_score} size="sm" />
            </div>
            <div className="mt-1 flex items-center gap-2 text-[10px] text-stone-500 flex-wrap">
              {m.avg_rating != null && (
                <span className="flex items-center gap-0.5">
                  <Star size={10} className="text-amber-400" />
                  {m.avg_rating.toFixed(1)}
                </span>
              )}
              {typeof m.matchScore === "number" && m.matchScore > 0 && (
                <span className="flex items-center gap-1 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-1.5 py-px text-cyan-200">
                  <Sparkles size={10} /> {Math.round(m.matchScore * 100)}%
                </span>
              )}
              {(m.matchedSkills.length > 0 ? m.matchedSkills : m.skills.slice(0, 2)).slice(0, 3).map((s) => (
                <span key={s} className="rounded-full border border-white/10 bg-white/5 px-1.5 py-px">
                  {s}
                </span>
              ))}
            </div>
            {m.response_time_hint && (
              <div className="mt-1 text-[10px] text-stone-500 truncate">{m.response_time_hint}</div>
            )}
          </div>
        </Link>
      ))}

      <Link
        href={`/marketplace${skills.length > 0 ? `?search=${encodeURIComponent(skills[0])}` : ""}`}
        className="flex items-center justify-center gap-1.5 text-xs text-stone-400 hover:text-amber-300 transition-colors py-2"
      >
        Все исполнители <ArrowRight size={12} />
      </Link>
    </div>
  );
}
