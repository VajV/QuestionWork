"use client";

import { Brain, Zap, MessageCircle, Swords } from 'lucide-react';

interface UserStats {
  int: number;
  dex: number;
  cha: number;
}

interface StatsPanelProps {
  stats: UserStats;
}

export default function StatsPanel({ stats }: StatsPanelProps) {
  // Для начала возьмем макс стат 20 для расчета
  const maxStat = 20;

  return (
    <div className="rpg-card p-6 mt-6">
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
  );
}
