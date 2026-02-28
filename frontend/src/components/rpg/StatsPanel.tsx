"use client";

import Card from "@/components/ui/Card";
import ProgressBar from "@/components/ui/ProgressBar";

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
const statIcons: Record<keyof UserStats, string> = {
  int: '🧠',
  dex: '⚡',
  cha: '💬',
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
const statColors: Record<keyof UserStats, 'blue' | 'green' | 'purple'> = {
  int: 'blue',
  dex: 'green',
  cha: 'purple',
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
        {(Object.keys(stats) as Array<keyof UserStats>).map((statKey) => (
          <div key={statKey}>
            {/* Заголовок статистики */}
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xl">{statIcons[statKey]}</span>
              <span className="text-gray-300 flex-1">{statNames[statKey]}</span>
              <span className="text-white font-bold">{stats[statKey]}</span>
            </div>
            
            {/* Прогресс-бар статистики */}
            <ProgressBar
              value={stats[statKey]}
              max={maxStat}
              showPercent={false}
              color={statColors[statKey]}
            />
          </div>
        ))}
      </div>

      {/* Подсказка для пользователя */}
      <p className="text-gray-500 text-sm mt-4">
        💡 Статы растут с выполнением квестов и повышением уровня
      </p>
    </Card>
  );
}
