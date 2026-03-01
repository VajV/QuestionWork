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
    color: 'from-green-500 to-green-700 text-green-100 border-green-600',
    icon: '🟢',
    label: 'Открыт',
    description: 'Ищет исполнителя',
  },
  in_progress: {
    color: 'from-blue-500 to-blue-700 text-blue-100 border-blue-600',
    icon: '🔵',
    label: 'В работе',
    description: 'Фрилансер выполняет',
  },
  completed: {
    color: 'from-purple-500 to-purple-700 text-purple-100 border-purple-600',
    icon: '🟣',
    label: 'Завершён',
    description: 'Ожидает подтверждения',
  },
  cancelled: {
    color: 'from-gray-500 to-gray-700 text-gray-100 border-gray-600',
    icon: '⚫',
    label: 'Отменён',
    description: 'Квест отменён',
  },
};

/**
 * Размеры бейджа
 */
const sizeStyles = {
  sm: 'text-xs px-2 py-1',
  md: 'text-sm px-3 py-1.5',
  lg: 'text-base px-4 py-2',
};

export default function QuestStatusBadge({
  status,
  size = 'md',
  showDescription = false,
}: QuestStatusBadgeProps) {
  const config = statusConfig[status];
  const sizeStyle = sizeStyles[size];

  return (
    <div className="inline-flex flex-col items-start">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r ${config.color} ${sizeStyle} font-medium shadow-lg border`}
      >
        <span>{config.icon}</span>
        <span>{config.label}</span>
      </span>
      {showDescription && (
        <span className="text-xs text-gray-400 mt-1">
          {config.description}
        </span>
      )}
    </div>
  );
}
