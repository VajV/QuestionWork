/**
 * QuestStatusBadge - Цветной бейдж статуса квеста
 * 
 * Отображает текущий статус квеста с иконкой и понятным описанием
 */

"use client";

import { QuestStatus } from "@/lib/api";

interface QuestStatusBadgeProps {
  status: QuestStatus;
  size?: 'sm' | 'md' | 'lg';
  showDescription?: boolean;
}

/**
 * Конфигурация стилей для каждого статуса
 */
const statusConfig: Record<QuestStatus, {
  color: string;
  icon: string;
  label: string;
  description: string;
}> = {
  open: {
    color: 'border-green-600 bg-green-950/40 text-green-400 shadow-[0_0_10px_rgba(22,163,74,0.3)]',
    icon: '⚔️',
    label: 'Открыт',
    description: 'Ожидает героя',
  },
  in_progress: {
    color: 'border-blue-600 bg-blue-950/40 text-blue-400 shadow-[0_0_10px_rgba(37,99,235,0.3)]',
    icon: '⏳',
    label: 'В работе',
    description: 'Герой в пути',
  },
  completed: {
    color: 'border-purple-600 bg-purple-950/40 text-purple-400 shadow-[0_0_10px_rgba(147,51,234,0.3)]',
    icon: '🏆',
    label: 'Завершён',
    description: 'Слава получена',
  },
  cancelled: {
    color: 'border-gray-600 bg-gray-900/40 text-gray-400 shadow-[0_0_10px_rgba(75,85,99,0.3)]',
    icon: '💀',
    label: 'Отменён',
    description: 'Контракт сожжён',
  },
};

/**
 * Размеры бейджа
 */
const sizeStyles = {
  sm: 'text-[10px] px-2 py-0.5',
  md: 'text-xs px-3 py-1',
  lg: 'text-sm px-4 py-1.5',
};

export default function QuestStatusBadge({
  status,
  size = 'md',
  showDescription = false,
}: QuestStatusBadgeProps) {
  const config = statusConfig[status];
  const sizeStyle = sizeStyles[size];

  return (
    <div className="inline-flex flex-col items-start font-cinzel tracking-wider uppercase font-bold">
      <span
        className={`inline-flex items-center gap-1.5 rounded border ${config.color} ${sizeStyle}`}
      >
        <span>{config.icon}</span>
        <span>{config.label}</span>
      </span>
      {showDescription && (
        <span className="text-[10px] font-mono normal-case tracking-normal text-gray-500 mt-1">
          {config.description}
        </span>
      )}
    </div>
  );
}
