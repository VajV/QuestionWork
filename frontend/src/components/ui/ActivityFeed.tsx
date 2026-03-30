"use client";

import React from "react";
import Card from "./Card";

export interface ActivityItem {
  icon: string;
  title: string;
  meta: string;
  tone?: string;
}

interface ActivityFeedProps {
  items: ActivityItem[];
  label?: string;
  className?: string;
  maxItems?: number;
}

export default function ActivityFeed({
  items,
  label = "Активность",
  className = "",
  maxItems,
}: ActivityFeedProps) {
  const visible = maxItems ? items.slice(0, maxItems) : items;

  return (
    <Card variant="default" className={`border-white/10 bg-gradient-to-b from-white/[0.05] to-black/25 p-8 ${className}`}>
      <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-[var(--accent-cyan)]">
        {label}
      </p>
      <div className="mt-6 space-y-4">
        {visible.map((event, idx) => (
          <div key={idx} className="activity-row">
            <div className="activity-icon">{event.icon}</div>
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium truncate ${event.tone ?? "text-stone-200"}`}>
                {event.title}
              </p>
              <p className="mt-1 text-xs uppercase tracking-[0.24em] text-stone-500">
                {event.meta}
              </p>
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-sm text-stone-500 text-center py-4">Нет активности</p>
        )}
      </div>
    </Card>
  );
}
