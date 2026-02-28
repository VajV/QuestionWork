"use client";

import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";

interface Stats {
  int: number;
  dex: number;
  cha: number;
}

interface StatsPanelProps {
  stats: Stats;
}

const statIcons = {
  int: '🧠',
  dex: '⚡',
  cha: '💬',
};

const statNames = {
  int: 'Интеллект',
  dex: 'Ловкость',
  cha: 'Харизма',
};

const statColors = {
  int: 'blue' as const,
  dex: 'green' as const,
  cha: 'purple' as const,
};

export default function StatsPanel({ stats }: StatsPanelProps) {
  // Максимальный стат для расчёта процента (база = 10)
  const maxStat = 20;

  return (
    <Card className="p-6">
      <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
        <span>📊</span> Характеристики
      </h3>
      
      <div className="space-y-4">
        {(Object.keys(stats) as Array<keyof Stats>).map((statKey) => (
          <div key={statKey}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xl">{statIcons[statKey]}</span>
              <span className="text-gray-300 flex-1">{statNames[statKey]}</span>
              <span className="text-white font-bold">{stats[statKey]}</span>
            </div>
            <ProgressBar
              value={stats[statKey]}
              max={maxStat}
              showPercent={false}
              color={statColors[statKey]}
            />
          </div>
        ))}
      </div>

      {/* Подсказка */}
      <p className="text-gray-500 text-sm mt-4">
        💡 Статы растут с выполнением квестов и повышением уровня
      </p>
    </Card>
  );
}
