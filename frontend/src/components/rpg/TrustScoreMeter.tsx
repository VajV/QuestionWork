import type { TrustScoreResponse } from "@/lib/api";

type TrustScoreMeterProps = {
  data: TrustScoreResponse;
};

const COMPONENT_LABELS = [
  { key: "avg_rating", label: "Рейтинг", weight: "40%" },
  { key: "completion_rate", label: "Завершаемость", weight: "30%" },
  { key: "on_time_rate", label: "Сроки", weight: "20%" },
  { key: "level_bonus", label: "Grade bonus", weight: "10%" },
] as const;

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "--";
  }
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
}

function formatUpdatedAt(value: string | null): string {
  if (!value) {
    return "Ещё не пересчитан";
  }

  return new Date(value).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function TrustScoreMeter({ data }: TrustScoreMeterProps) {
  const totalPercent = formatPercent(data.trust_score);

  return (
    <div className="rounded-3xl border border-emerald-500/20 bg-[linear-gradient(135deg,rgba(10,20,18,0.96),rgba(6,12,18,0.94))] p-5 shadow-[0_20px_80px_rgba(16,185,129,0.08)]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-emerald-300/70">Trust score</p>
          <div className="mt-3 flex items-end gap-3">
            <span className="font-cinzel text-5xl font-bold text-emerald-200">{totalPercent}</span>
            <span className="pb-1 text-sm text-stone-400">Composite guild trust</span>
          </div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-stone-300">
          <p className="text-[11px] uppercase tracking-[0.18em] text-stone-500">Последний пересчёт</p>
          <p className="mt-1">{formatUpdatedAt(data.updated_at)}</p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {COMPONENT_LABELS.map((item) => {
          const value = data.breakdown[item.key];
          const width = typeof value === "number" ? Math.max(0, Math.min(1, value)) * 100 : 0;

          return (
            <div key={item.key} className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm text-stone-200">{item.label}</p>
                <span className="text-[10px] uppercase tracking-[0.2em] text-stone-500">{item.weight}</span>
              </div>
              <p className="mt-3 font-cinzel text-2xl text-stone-100">{formatPercent(value)}</p>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-sky-300 to-amber-300" style={{ width: `${width}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}