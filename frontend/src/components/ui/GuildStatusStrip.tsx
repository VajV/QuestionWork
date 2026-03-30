"use client";

import React from "react";
import { motion, useReducedMotion } from "@/lib/motion";
import SignalChip from "@/components/ui/SignalChip";
import { useWorldMeta } from "@/context/WorldMetaContext";
import type { WorldTrendMetric } from "@/lib/api";

type StripMode = "guild" | "market" | "profile" | "class" | "ops";
type StripTone = "gold" | "purple" | "cyan" | "emerald" | "amber" | "red" | "slate" | "ops";

interface StripStat {
  label: string;
  value: string | number;
  note?: string;
  tone?: StripTone;
}

interface StripSignal {
  label: string;
  tone?: StripTone;
}

interface GuildStatusStripProps {
  eyebrow: string;
  title: string;
  description: string;
  stats: StripStat[];
  signals?: StripSignal[];
  aside?: React.ReactNode;
  mode?: StripMode;
  className?: string;
  includeWorldState?: boolean;
}

const wrapperStyles: Record<StripMode, string> = {
  guild: "border-amber-500/20 bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.16),_transparent_32%),linear-gradient(135deg,rgba(10,10,15,0.94),rgba(26,17,34,0.92))]",
  market: "border-violet-500/20 bg-[radial-gradient(circle_at_top_left,_rgba(139,92,246,0.18),_transparent_32%),linear-gradient(135deg,rgba(8,10,18,0.94),rgba(21,18,34,0.92))]",
  profile: "border-amber-500/20 bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.14),_transparent_32%),linear-gradient(135deg,rgba(11,15,24,0.94),rgba(29,18,38,0.92))]",
  class: "border-red-500/20 bg-[radial-gradient(circle_at_top_left,_rgba(239,68,68,0.16),_transparent_32%),linear-gradient(135deg,rgba(15,10,14,0.96),rgba(34,14,22,0.94))]",
  ops: "border-sky-500/20 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.16),_transparent_32%),linear-gradient(135deg,rgba(6,10,18,0.98),rgba(11,18,28,0.96))]",
};

const accentStyles: Record<StripMode, string> = {
  guild: "text-amber-300",
  market: "text-violet-300",
  profile: "text-amber-300",
  class: "text-red-300",
  ops: "text-sky-300",
};

const statToneStyles: Record<StripTone, string> = {
  gold: "text-amber-300",
  purple: "text-violet-300",
  cyan: "text-cyan-300",
  emerald: "text-emerald-300",
  amber: "text-orange-300",
  red: "text-red-300",
  slate: "text-stone-100",
  ops: "text-sky-300",
};

export default function GuildStatusStrip({
  eyebrow,
  title,
  description,
  stats,
  signals = [],
  aside,
  mode = "guild",
  className = "",
  includeWorldState = true,
}: GuildStatusStripProps) {
  const reduceMotion = useReducedMotion();
  const { snapshot } = useWorldMeta();
  const leader = snapshot?.factions.find((faction) => faction.id === snapshot.leading_faction_id) ?? snapshot?.factions[0];
  const liveSignals: StripSignal[] = includeWorldState && snapshot
    ? [
        {
          label: `${snapshot.season.stage} ${snapshot.season.progress_percent}%`,
          tone: mode === "ops" ? "ops" : snapshot.season.progress_percent >= 70 ? "gold" : "purple",
        },
        {
          label: `${leader?.name ?? "Faction"} ${leader?.trend ?? "stable"}`,
          tone: leader?.trend === "surging" ? "emerald" : leader?.trend === "recovering" ? "amber" : mode === "ops" ? "ops" : "cyan",
        },
        {
          label: `${snapshot.community.momentum} pulse`,
          tone: snapshot.community.momentum === "rising" ? "emerald" : snapshot.community.momentum === "under_pressure" ? "red" : "slate",
        },
      ]
    : [];
  const mergedSignals = [...signals, ...liveSignals.filter((signal) => !signals.some((item) => item.label === signal.label))];
  const worldTrends = snapshot?.trends.slice(0, 3) ?? [];
  const worldAside = includeWorldState && snapshot ? (
    <div className="rounded-2xl border border-white/10 bg-black/25 p-4 backdrop-blur-sm">
      <p className="text-[10px] uppercase tracking-[0.26em] text-stone-500">World state</p>
      <div className="mt-3 space-y-3">
        <div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-stone-400">Season</span>
            <SignalChip tone={snapshot.season.progress_percent >= 70 ? "gold" : "purple"}>{snapshot.season.progress_percent}% live</SignalChip>
          </div>
          <p className="mt-2 text-sm font-semibold text-stone-100">{snapshot.season.title}</p>
          <p className="mt-1 text-xs text-stone-400">{snapshot.season.completed_quests_week}/{snapshot.season.target_quests_week} weekly confirmations, {snapshot.season.days_left}d left.</p>
        </div>

        <div className="grid gap-2">
          {worldTrends.map((trend) => {
            const maxPoint = Math.max(...trend.points.map((point) => point.value), 1);
            const tone = getTrendTone(trend, mode);
            return (
              <div key={trend.id} className="rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[11px] uppercase tracking-[0.18em] text-stone-500">{trend.label}</span>
                  <SignalChip tone={tone}>{formatTrendDelta(trend)}</SignalChip>
                </div>
                <div className="mt-2 flex items-end gap-1.5">
                  {trend.points.map((point, index) => (
                    <motion.div
                      key={`${trend.id}-${point.label}-${index}`}
                      initial={reduceMotion ? false : { opacity: 0, scaleY: 0.6 }}
                      whileInView={{ opacity: 1, scaleY: 1 }}
                      viewport={{ once: true, amount: 0.7 }}
                      transition={{ duration: reduceMotion ? 0.01 : 0.22, delay: reduceMotion ? 0 : index * 0.02, ease: "easeOut" }}
                      className="flex-1 rounded-full bg-white/8"
                      style={{ height: `${14 + Math.round((point.value / maxPoint) * 26)}px`, transformOrigin: "bottom" }}
                      title={`${point.label}: ${point.value}`}
                    >
                      <div className={`h-full w-full rounded-full ${trendBarClass(trend)}`} />
                    </motion.div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  ) : null;

  return (
    <motion.section
      initial={reduceMotion ? false : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: reduceMotion ? 0.01 : 0.42, ease: "easeOut" }}
      className={`world-panel-hover relative overflow-hidden rounded-3xl border p-6 shadow-2xl shadow-black/20 backdrop-blur ${wrapperStyles[mode]} ${className}`}
    >
      <div className="pointer-events-none absolute inset-0 opacity-40 [background-image:linear-gradient(to_right,rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.04)_1px,transparent_1px)] [background-size:28px_28px]" />
      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <p className={`font-mono text-[11px] uppercase tracking-[0.35em] ${accentStyles[mode]}`}>{eyebrow}</p>
          <h2 className="mt-3 font-cinzel text-3xl font-bold text-stone-100 sm:text-4xl">{title}</h2>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-stone-400 sm:text-base">{description}</p>

          {mergedSignals.length > 0 && (
            <div className="mt-5 flex flex-wrap gap-2">
              {mergedSignals.map((signal, index) => (
                <motion.div
                  key={signal.label}
                  initial={reduceMotion ? false : { opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.5 }}
                  transition={{ duration: reduceMotion ? 0.01 : 0.24, delay: reduceMotion ? 0 : index * 0.04, ease: "easeOut" }}
                >
                  <SignalChip tone={signal.tone ?? (mode === "ops" ? "ops" : "slate")}>
                    {signal.label}
                  </SignalChip>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {(worldAside || aside) && (
          <div className="relative z-10 space-y-3 lg:min-w-[280px]">
            {worldAside}
            {aside}
          </div>
        )}
      </div>

      <div className="relative mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat, index) => (
          <motion.div
            key={stat.label}
            initial={reduceMotion ? false : { opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.5 }}
            transition={{ duration: reduceMotion ? 0.01 : 0.28, delay: reduceMotion ? 0 : index * 0.05, ease: "easeOut" }}
            className="rounded-2xl border border-white/10 bg-black/25 p-4 transition-transform duration-300 hover:-translate-y-1"
          >
            <div className="text-[10px] uppercase tracking-[0.24em] text-stone-500">{stat.label}</div>
            <div className={`mt-2 font-cinzel text-2xl font-bold ${statToneStyles[stat.tone ?? "slate"]}`}>
              {stat.value}
            </div>
            {stat.note && <div className="mt-1 text-xs text-stone-400">{stat.note}</div>}
          </motion.div>
        ))}
      </div>
    </motion.section>
  );
}

function getTrendTone(trend: WorldTrendMetric, mode: StripMode): StripTone {
  if (trend.direction === "rising") {
    return "emerald";
  }
  if (trend.direction === "falling") {
    return "red";
  }
  return mode === "ops" ? "ops" : "cyan";
}

function formatTrendDelta(trend: WorldTrendMetric): string {
  if (trend.delta_value === 0) {
    return "flat vs prev";
  }

  const sign = trend.delta_value > 0 ? "+" : "";
  return `${sign}${trend.delta_value} vs prev`;
}

function trendBarClass(trend: WorldTrendMetric): string {
  if (trend.direction === "rising") {
    return "bg-gradient-to-t from-emerald-500/40 to-emerald-300/90";
  }
  if (trend.direction === "falling") {
    return "bg-gradient-to-t from-red-500/40 to-red-300/90";
  }
  return "bg-gradient-to-t from-cyan-500/35 to-cyan-200/85";
}