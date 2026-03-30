"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Compass, Sparkles } from "lucide-react";

import { getRecommendedQuests, type QuestRecommendation } from "@/lib/api";
import Card from "@/components/ui/Card";
import QuestStatusBadge from "@/components/quests/QuestStatusBadge";
import { formatMoney } from "@/lib/format";

interface Props {
  limit?: number;
}

export default function RecommendedQuestPanel({ limit = 4 }: Props) {
  const [recommendations, setRecommendations] = useState<QuestRecommendation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const response = await getRecommendedQuests(limit);
        if (!cancelled) {
          setRecommendations(response.recommendations);
        }
      } catch {
        if (!cancelled) {
          setRecommendations([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [limit]);

  if (loading) {
    return (
      <Card className="mb-8 border-cyan-900/40 bg-cyan-950/10 p-6">
        <div className="flex items-center gap-2 text-cyan-300 font-cinzel uppercase tracking-wider text-sm">
          <Compass size={16} /> Квесты для тебя
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {Array.from({ length: Math.min(limit, 4) }).map((_, index) => (
            <div key={index} className="h-28 rounded-2xl bg-white/5 animate-pulse" />
          ))}
        </div>
      </Card>
    );
  }

  if (recommendations.length === 0) {
    return null;
  }

  return (
    <Card className="mb-8 border-cyan-900/40 bg-gradient-to-br from-cyan-950/30 via-slate-950 to-slate-950 p-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-400/70">Personal feed</p>
          <h2 className="mt-2 font-cinzel text-2xl text-stone-100">Квесты для тебя</h2>
        </div>
        <Link href="/quests" className="text-xs text-cyan-200 hover:text-amber-200 transition-colors uppercase tracking-[0.2em]">
          Вся доска
        </Link>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        {recommendations.map((item) => (
          <Link
            key={item.quest.id}
            href={`/quests/${item.quest.id}`}
            className="group rounded-2xl border border-white/8 bg-black/20 p-4 transition-colors hover:border-cyan-400/30 hover:bg-black/30"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-cinzel text-lg text-stone-100 group-hover:text-cyan-200 transition-colors">
                  {item.quest.title}
                </h3>
                <div className="mt-2 flex items-center gap-2 flex-wrap text-[11px] text-stone-400 uppercase tracking-[0.18em]">
                  <QuestStatusBadge status={item.quest.status} size="sm" />
                  <span>{item.quest.required_grade}</span>
                  <span>{formatMoney(item.quest.budget, { suffix: ` ${item.quest.currency}` })}</span>
                </div>
              </div>
              <div className="shrink-0 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100 flex items-center gap-1.5">
                <Sparkles size={12} /> {Math.round(item.match_score * 100)}%
              </div>
            </div>

            <p className="mt-3 text-sm leading-6 text-stone-400 line-clamp-2">{item.quest.description}</p>

            <div className="mt-4 flex flex-wrap gap-2">
              {item.matched_skills.slice(0, 4).map((skill) => (
                <span key={skill} className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2.5 py-1 text-[11px] text-cyan-100">
                  {skill}
                </span>
              ))}
              {item.matched_skills.length === 0 && item.quest.skills.slice(0, 3).map((skill) => (
                <span key={skill} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-stone-300">
                  {skill}
                </span>
              ))}
            </div>
          </Link>
        ))}
      </div>
    </Card>
  );
}