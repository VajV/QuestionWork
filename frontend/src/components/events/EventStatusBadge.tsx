/**
 * EventStatusBadge — цветной бейдж статуса ивента
 */

"use client";

import { EventStatus } from "@/types";

interface EventStatusBadgeProps {
  status: EventStatus;
  size?: "sm" | "md" | "lg";
}

const statusConfig: Record<
  EventStatus,
  { color: string; icon: string; label: string }
> = {
  draft: {
    color: "border-gray-500/40 bg-gray-900/60 text-gray-400",
    icon: "📝",
    label: "Черновик",
  },
  active: {
    color: "border-emerald-500/40 bg-emerald-900/40 text-emerald-300 animate-pulse",
    icon: "⚡",
    label: "Активен",
  },
  ended: {
    color: "border-amber-500/40 bg-amber-900/40 text-amber-300",
    icon: "⏳",
    label: "Завершён",
  },
  finalized: {
    color: "border-purple-500/40 bg-purple-900/40 text-purple-300",
    icon: "🏆",
    label: "Итоги",
  },
};

const sizeStyles = {
  sm: "text-[10px] px-2 py-0.5",
  md: "text-xs px-3 py-1",
  lg: "text-sm px-4 py-1.5",
};

export default function EventStatusBadge({
  status,
  size = "md",
}: EventStatusBadgeProps) {
  const config = statusConfig[status];
  const sizeStyle = sizeStyles[size];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border font-cinzel tracking-wider uppercase font-bold ${config.color} ${sizeStyle}`}
    >
      <span>{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );
}
