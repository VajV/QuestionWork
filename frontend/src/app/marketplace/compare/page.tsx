"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion } from "@/lib/motion";
import { ArrowLeft, Star, CheckCircle, ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  getUserProfile,
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

function CompareInner() {
  const params = useSearchParams();
  const { loading: authLoading } = useAuth();
  const [candidates, setCandidates] = useState<PublicUserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCandidates = useCallback(async () => {
    const rawIds = params.get("ids");
    const source = params.get("source") ?? "unknown";
    if (!rawIds) {
      setError("Не указаны кандидаты для сравнения.");
      setLoading(false);
      return;
    }

    const ids = rawIds.split(",").filter(Boolean).slice(0, 4);
    if (ids.length < 2) {
      setError("Для сравнения нужно минимум 2 кандидата.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    trackAnalyticsEvent("compare_started", {
      source,
      candidate_ids: ids,
      candidate_count: ids.length,
    });

    try {
      const profiles = await Promise.all(
        ids.map((id) => getUserProfile(id)),
      );
      setCandidates(profiles);
      trackAnalyticsEvent("compare_completed", {
        source,
        candidate_ids: ids,
        candidate_count: profiles.length,
      });
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось загрузить профили."));
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => {
    if (!authLoading) loadCandidates();
  }, [authLoading, loadCandidates]);

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

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
      <Link
        href="/marketplace"
        className="inline-flex items-center gap-2 text-sm text-stone-400 hover:text-amber-300 transition-colors mb-6"
      >
        <ArrowLeft size={15} /> Вернуться на биржу
      </Link>

      <h1 className="text-3xl font-cinzel text-amber-400 mb-2">Сравнение кандидатов</h1>
      <p className="text-gray-400 mb-8">
        Сравните до 4 кандидатов по ключевым показателям: рейтинг, опыт, навыки и завершённые квесты.
      </p>

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

            {/* Action */}
            <tr>
              <td className="py-4 pr-4" />
              {candidates.map((c) => (
                <td key={c.id} className="text-center py-4 px-3">
                  <Link
                    href={`/users/${c.id}`}
                    className="inline-block rounded-lg bg-violet-500/20 border border-violet-500/30 px-4 py-2 text-xs text-violet-200 hover:bg-violet-500/30 transition-colors"
                  >
                    Открыть профиль
                  </Link>
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
  icon?: React.ReactNode;
  children: React.ReactNode;
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
