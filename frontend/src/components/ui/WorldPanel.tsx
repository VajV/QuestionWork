"use client";

import { motion, useReducedMotion } from "@/lib/motion";
import SignalChip, { type SignalChipTone } from "@/components/ui/SignalChip";
import type { WorldRegion } from "@/lib/api";

type WorldTone = "amber" | "purple" | "cyan" | "emerald" | "slate" | "ops";

interface WorldPanelMetric {
  label: string;
  value: string | number;
  note?: string;
}

interface WorldPanelChip {
  label: string;
  tone?: SignalChipTone;
}

interface WorldPanelProps {
  eyebrow: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
  metrics?: WorldPanelMetric[];
  chips?: WorldPanelChip[];
  className?: string;
  tone?: WorldTone;
  compact?: boolean;
  /** Active season chapter name, e.g. "Глава II: Восхождение" */
  chapter?: string;
  /** Hint shown below chapter — what action unlocks the next stage */
  nextUnlock?: string;
  /** Map regions derived from platform activity signals */
  regions?: WorldRegion[];
}

const toneMap: Record<WorldTone, { shell: string; accent: string; title: string }> = {
  amber: {
    shell: "border-amber-500/20 bg-[linear-gradient(180deg,rgba(120,53,15,0.16)_0%,rgba(3,7,18,0.9)_100%)]",
    accent: "from-amber-400/35 via-amber-200/10 to-transparent",
    title: "text-amber-100",
  },
  purple: {
    shell: "border-violet-500/20 bg-[linear-gradient(180deg,rgba(88,28,135,0.18)_0%,rgba(3,7,18,0.92)_100%)]",
    accent: "from-violet-400/30 via-violet-200/10 to-transparent",
    title: "text-violet-100",
  },
  cyan: {
    shell: "border-cyan-500/20 bg-[linear-gradient(180deg,rgba(8,47,73,0.2)_0%,rgba(3,7,18,0.92)_100%)]",
    accent: "from-cyan-400/30 via-cyan-200/10 to-transparent",
    title: "text-cyan-100",
  },
  emerald: {
    shell: "border-emerald-500/20 bg-[linear-gradient(180deg,rgba(6,78,59,0.18)_0%,rgba(3,7,18,0.92)_100%)]",
    accent: "from-emerald-400/30 via-emerald-200/10 to-transparent",
    title: "text-emerald-100",
  },
  slate: {
    shell: "border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.82)_0%,rgba(2,6,23,0.96)_100%)]",
    accent: "from-slate-300/18 via-slate-100/8 to-transparent",
    title: "text-slate-100",
  },
  ops: {
    shell: "border-sky-500/20 bg-[linear-gradient(180deg,rgba(8,47,73,0.28)_0%,rgba(2,6,23,0.96)_100%)]",
    accent: "from-sky-400/30 via-cyan-200/10 to-transparent",
    title: "text-sky-100",
  },
};

export default function WorldPanel({
  eyebrow,
  title,
  description,
  children,
  metrics,
  chips,
  className = "",
  tone = "slate",
  compact = false,
  chapter,
  nextUnlock,
  regions,
}: WorldPanelProps) {
  const reduceMotion = useReducedMotion();
  const palette = toneMap[tone];

  return (
    <motion.section
      initial={reduceMotion ? false : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: reduceMotion ? 0.01 : 0.45, ease: "easeOut" }}
      className={`world-panel-hover group relative overflow-hidden rounded-[28px] border shadow-[0_24px_80px_rgba(2,6,23,0.45)] ${palette.shell} ${compact ? "p-5" : "p-6 md:p-7"} ${className}`}
    >
      <div className={`pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r ${palette.accent}`} />
      <div className="pointer-events-none absolute -right-16 top-0 h-40 w-40 rounded-full bg-white/5 blur-3xl transition-transform duration-700 group-hover:scale-110" />

      <div className="relative space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-[11px] font-mono uppercase tracking-[0.34em] text-gray-500">{eyebrow}</p>
            <h2 className={`mt-3 font-cinzel text-2xl font-bold sm:text-3xl ${palette.title}`}>{title}</h2>
            {chapter && (
              <div className="mt-2 flex items-center gap-2">
                <span className="rounded-lg border border-white/10 bg-black/25 px-2.5 py-1 text-[11px] font-mono text-gray-300">
                  {chapter}
                </span>
              </div>
            )}
            {description && <p className="mt-3 text-sm leading-7 text-gray-400 sm:text-[15px]">{description}</p>}
            {nextUnlock && (
              <p className="mt-2 text-[12px] italic text-gray-500">{nextUnlock}</p>
            )}
          </div>

          {chips && chips.length > 0 && (
            <div className="flex flex-wrap gap-2 lg:max-w-sm lg:justify-end">
              {chips.map((chip) => (
                <SignalChip key={chip.label} tone={chip.tone ?? "slate"}>{chip.label}</SignalChip>
              ))}
            </div>
          )}
        </div>

        {metrics && metrics.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {metrics.map((metric) => (
              <div key={metric.label} className="rounded-2xl border border-white/10 bg-black/20 px-4 py-4 backdrop-blur-sm transition-transform duration-300 group-hover:-translate-y-0.5">
                <p className="text-[10px] uppercase tracking-[0.22em] text-gray-500">{metric.label}</p>
                <div className="mt-2 text-2xl font-bold text-white">{metric.value}</div>
                {metric.note && <p className="mt-1 text-xs text-gray-400">{metric.note}</p>}
              </div>
            ))}
          </div>
        )}

        {regions && regions.length > 0 && (
          <div className="space-y-2">
            <p className="text-[10px] uppercase tracking-[0.22em] text-gray-500">Map Regions</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {regions.map((region) => {
                const statusStyles = _regionStatusStyles(region.status);
                return (
                  <div
                    key={region.id}
                    className="rounded-xl border border-white/8 bg-black/20 px-3 py-3 backdrop-blur-sm"
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-xs font-semibold text-white">{region.name}</span>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${statusStyles.badge}`}>
                        {region.status}
                      </span>
                    </div>
                    <div className="h-1 w-full rounded-full bg-white/10">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${statusStyles.bar}`}
                        style={{ width: `${region.progress_percent}%` }}
                      />
                    </div>
                    <p className="mt-1.5 text-[11px] text-gray-500">{region.activity_label}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {children}
      </div>
    </motion.section>
  );
}

function _regionStatusStyles(status: string): { badge: string; bar: string } {
  switch (status) {
    case "active":
      return { badge: "border-emerald-500/40 text-emerald-400", bar: "bg-emerald-500" };
    case "contested":
      return { badge: "border-amber-500/40 text-amber-400", bar: "bg-amber-500" };
    case "dormant":
      return { badge: "border-slate-500/40 text-slate-400", bar: "bg-slate-500" };
    case "hostile":
      return { badge: "border-rose-500/40 text-rose-400", bar: "bg-rose-500" };
    default:
      return { badge: "border-white/20 text-gray-400", bar: "bg-gray-500" };
  }
}