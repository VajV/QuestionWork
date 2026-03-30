"use client";

import React from 'react';
import { Brain, Zap, MessageCircle, Swords, Shield, Hammer, Star, Flame } from 'lucide-react';
import type { ReputationStats } from "@/lib/api";

interface UserStats {
  int: number;
  dex: number;
  cha: number;
}

interface StatsPanelProps {
  stats: UserStats;
  reputationStats?: ReputationStats | null;
}

const REP_STAT_CONFIG = [
  {
    key: "reliability" as keyof ReputationStats,
    label: "Надёжность",
    icon: Shield,
    colorClass: "text-sky-400",
    borderColor: "border-sky-500/30",
    bgColor: "bg-sky-950/20",
    shadowHover: "group-hover:shadow-[0_0_15px_rgba(14,165,233,0.4)]",
    shadowDefault: "shadow-[0_0_10px_rgba(14,165,233,0.2)]",
    barClass: "bg-sky-500",
    barGlow: "shadow-[0_0_10px_rgba(14,165,233,0.5)]",
  },
  {
    key: "craft" as keyof ReputationStats,
    label: "Мастерство",
    icon: Hammer,
    colorClass: "text-violet-400",
    borderColor: "border-violet-500/30",
    bgColor: "bg-violet-950/20",
    shadowHover: "group-hover:shadow-[0_0_15px_rgba(139,92,246,0.4)]",
    shadowDefault: "shadow-[0_0_10px_rgba(139,92,246,0.2)]",
    barClass: "bg-violet-500",
    barGlow: "shadow-[0_0_10px_rgba(139,92,246,0.5)]",
  },
  {
    key: "influence" as keyof ReputationStats,
    label: "Влияние",
    icon: Star,
    colorClass: "text-yellow-400",
    borderColor: "border-yellow-500/30",
    bgColor: "bg-yellow-950/20",
    shadowHover: "group-hover:shadow-[0_0_15px_rgba(234,179,8,0.4)]",
    shadowDefault: "shadow-[0_0_10px_rgba(234,179,8,0.2)]",
    barClass: "bg-yellow-500",
    barGlow: "shadow-[0_0_10px_rgba(234,179,8,0.5)]",
  },
  {
    key: "resolve" as keyof ReputationStats,
    label: "Стойкость",
    icon: Flame,
    colorClass: "text-rose-400",
    borderColor: "border-rose-500/30",
    bgColor: "bg-rose-950/20",
    shadowHover: "group-hover:shadow-[0_0_15px_rgba(244,63,94,0.4)]",
    shadowDefault: "shadow-[0_0_10px_rgba(244,63,94,0.2)]",
    barClass: "bg-rose-500",
    barGlow: "shadow-[0_0_10px_rgba(244,63,94,0.5)]",
  },
];

function StatsPanelInner({ stats, reputationStats }: StatsPanelProps) {
  const maxStat = 20;

  return (
    <div className="space-y-6">
      {/* ── Combat stats ── */}
      <div className="rpg-card p-6">
        <h3 className="text-xl font-cinzel text-amber-500 mb-6 border-b border-amber-900/30 pb-2 flex items-center gap-2">
          <Swords className="text-amber-500" size={24} /> Характеристики
        </h3>

        <div className="space-y-6">
          <div className="flex items-center gap-4 group">
            <div className="w-12 h-12 rounded-lg border border-blue-500/30 bg-blue-950/20 flex items-center justify-center shadow-[0_0_10px_rgba(59,130,246,0.2)] group-hover:shadow-[0_0_15px_rgba(59,130,246,0.4)] transition-shadow">
              <Brain className="text-blue-400" size={24} />
            </div>
            <div className="flex-1">
              <div className="flex justify-between items-center mb-1">
                <span className="text-sm font-cinzel text-gray-300 uppercase tracking-wider">Интеллект</span>
                <span className="text-lg font-mono text-blue-400 font-bold">{stats.int}</span>
              </div>
              <div className="stat-bar mt-2">
                <div className="stat-bar-fill stat-bar-fill-int h-full shadow-[0_0_10px_rgba(59,130,246,0.5)]" style={{ width: `${Math.min((stats.int / maxStat) * 100, 100)}%` }}></div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4 group">
            <div className="w-12 h-12 rounded-lg border border-emerald-500/30 bg-emerald-950/20 flex items-center justify-center shadow-[0_0_10px_rgba(16,185,129,0.2)] group-hover:shadow-[0_0_15px_rgba(16,185,129,0.4)] transition-shadow">
              <Zap className="text-emerald-400" size={24} />
            </div>
            <div className="flex-1">
              <div className="flex justify-between items-center mb-1">
                <span className="text-sm font-cinzel text-gray-300 uppercase tracking-wider">Ловкость</span>
                <span className="text-lg font-mono text-emerald-400 font-bold">{stats.dex}</span>
              </div>
              <div className="stat-bar mt-2">
                <div className="stat-bar-fill stat-bar-fill-dex h-full shadow-[0_0_10px_rgba(16,185,129,0.5)]" style={{ width: `${Math.min((stats.dex / maxStat) * 100, 100)}%` }}></div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4 group">
            <div className="w-12 h-12 rounded-lg border border-amber-500/30 bg-amber-950/20 flex items-center justify-center shadow-[0_0_10px_rgba(245,158,11,0.2)] group-hover:shadow-[0_0_15px_rgba(245,158,11,0.4)] transition-shadow">
              <MessageCircle className="text-amber-400" size={24} />
            </div>
            <div className="flex-1">
              <div className="flex justify-between items-center mb-1">
                <span className="text-sm font-cinzel text-gray-300 uppercase tracking-wider">Харизма</span>
                <span className="text-lg font-mono text-amber-400 font-bold">{stats.cha}</span>
              </div>
              <div className="stat-bar mt-2">
                <div className="stat-bar-fill stat-bar-fill-cha h-full shadow-[0_0_10px_rgba(245,158,11,0.5)]" style={{ width: `${Math.min((stats.cha / maxStat) * 100, 100)}%` }}></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Reputation stats ── */}
      {reputationStats && (
        <div className="rpg-card p-6">
          <h3 className="text-xl font-cinzel text-purple-400 mb-6 border-b border-purple-900/30 pb-2 flex items-center gap-2">
            <Star className="text-purple-400" size={24} /> Репутация
          </h3>
          <div className="space-y-6">
            {REP_STAT_CONFIG.map(({ key, label, icon: Icon, colorClass, borderColor, bgColor, shadowDefault, shadowHover, barClass, barGlow }) => (
              <div key={key} className="flex items-center gap-4 group">
                <div className={`w-12 h-12 rounded-lg border ${borderColor} ${bgColor} flex items-center justify-center ${shadowDefault} ${shadowHover} transition-shadow`}>
                  <Icon className={colorClass} size={24} />
                </div>
                <div className="flex-1">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm font-cinzel text-gray-300 uppercase tracking-wider">{label}</span>
                    <span className={`text-lg font-mono ${colorClass} font-bold`}>{reputationStats[key]}</span>
                  </div>
                  <div className="stat-bar mt-2">
                    <div
                      className={`${barClass} ${barGlow} h-full rounded-full transition-all duration-700`}
                      style={{ width: `${Math.min(reputationStats[key], 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const StatsPanel = React.memo(StatsPanelInner);
export default StatsPanel;
