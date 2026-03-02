"use client";

import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";
import { Brain, Zap, MessageCircle } from 'lucide-react';

/**
 * Интерфейс для статистики пользователя
 * Использует те же имена полей что и API (int, dex, cha)
 */
interface UserStats {
  int: number;
  dex: number;
  cha: number;
}

interface StatsPanelProps {
  stats: UserStats;
}

/**
 * Иконки для каждой характеристики
 */
const statIcons = {
  int: Brain,
  dex: Zap,
  cha: MessageCircle,
};

/**
 * Названия характеристик на русском
 */
const statNames: Record<keyof UserStats, string> = {
  int: 'Интеллект',
  dex: 'Ловкость',
  cha: 'Харизма',
};

/**
 * Цвета для прогресс-баров каждой характеристики
 */
const statGradients: Record<keyof UserStats, string> = {
  int: 'from-blue-400 to-cyan-400',
  dex: 'from-emerald-400 to-green-400',
  cha: 'from-amber-400 to-orange-400',
};

const statGlowClass: Record<keyof UserStats, string> = {
  int: 'stat-glow-blue',
  dex: 'stat-glow-emerald',
  cha: 'stat-glow-amber',
};

const statColors: Record<keyof UserStats, 'blue' | 'emerald' | 'amber'> = {
  int: 'blue',
  dex: 'emerald',
  cha: 'amber',
};

/**
 * Компонент панели характеристик
 * 
 * @param props - Пропсы компонента
 * @param props.stats - Объект со статами пользователя из API
 * 
 * @example
 * <StatsPanel stats={{ int: 10, dex: 10, cha: 10 }} />
 */
export default function StatsPanel({ stats }: StatsPanelProps) {
  // Максимальный стат для расчёта процента (база = 10, макс = 20 для начала)
  const maxStat = 20;

  return (
    <Card className="p-6">
      <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
        <span>📊</span> Характеристики
      </h3>
      
      <div className="space-y-4">
        {/* Проходим по всем ключам статистики */}
        {(Object.keys(stats) as Array<keyof UserStats>).map((statKey) => {
          const IconComponent = statIcons[statKey];
          return (
            <div key={statKey} className={`glass-card p-4 flex items-center gap-4 hover:scale-[1.02] transition-transform duration-200 md:gap-6 ${statGlowClass[statKey]}`}>
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-br ${statGradients[statKey]} shadow-lg animate-neon-pulse shrink-0`}>
                <IconComponent size={20} className="text-white drop-shadow-lg" aria-hidden="true" focusable="false" />
              </div>
              
              <div className="flex-1">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm font-semibold text-white/80 uppercase tracking-widest">{statNames[statKey]}</span>
                  <span className={`text-lg font-bold bg-gradient-to-r ${statGradients[statKey]} bg-clip-text text-transparent ml-auto`}>
                    {stats[statKey]}
                  </span>
                </div>
                <ProgressBar
                  value={stats[statKey]}
                  max={maxStat}
                  showPercent={false}
                  color={statColors[statKey]}
                  className="mt-1"
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Подсказка для пользователя */}
      <p className="text-gray-500 text-sm mt-4">
        💡 Статы растут с выполнением квестов и повышением уровня
      </p>
    </Card>
  );
}
