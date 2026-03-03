"use client";

/**
 * BadgeGrid — displays a grid of earned badges for a user profile.
 *
 * Usage:
 *   <BadgeGrid badges={earnedBadges} />
 *
 * If no badges yet, shows an encouraging empty state.
 */

import type { UserBadgeEarned } from "@/lib/api";

interface BadgeGridProps {
  badges: UserBadgeEarned[];
  /** Show the earned date below each badge. Default true. */
  showDate?: boolean;
  /** Maximum number of badges to display. Undefined = all. */
  limit?: number;
}

export default function BadgeGrid({
  badges,
  showDate = true,
  limit,
}: BadgeGridProps) {
  const displayed = limit ? badges.slice(0, limit) : badges;

  if (badges.length === 0) {
    return (
      <div className="rpg-card min-h-[160px] border-dashed flex flex-col items-center justify-center p-8 text-center bg-gray-950/30">
        <span className="text-4xl filter grayscale opacity-50 mb-4 drop-shadow-md">🏅</span>
        <p className="text-sm font-cinzel text-gray-500 uppercase tracking-widest">
          Коллекция пуста. Выполняйте квесты, чтобы заслужить первые достижения!
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
      {displayed.map((b) => (
        <BadgeCard key={b.id} badge={b} showDate={showDate} />
      ))}
      {limit && badges.length > limit && (
        <div className="flex items-center justify-center rounded border border-gray-700 bg-gray-900/50 p-4 font-mono text-sm text-gray-500">
          +{badges.length - limit} ещё
        </div>
      )}
    </div>
  );
}

function BadgeCard({
  badge: b,
  showDate,
}: {
  badge: UserBadgeEarned;
  showDate: boolean;
}) {
  const earnedDate = new Date(b.earned_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div
      title={b.badge_description}
      className="group flex flex-col items-center gap-3 rounded border border-purple-900/30 bg-gray-900/80 p-5 shadow-lg relative overflow-hidden transition-all duration-300 hover:scale-105 hover:border-purple-500/60 hover:bg-purple-950/20 hover:shadow-[0_0_15px_rgba(139,92,246,0.3)] cursor-pointer"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-purple-500/[0.05] to-transparent pointer-events-none" />
      <span className="text-4xl drop-shadow-[0_0_8px_rgba(168,85,247,0.8)] filter transition-all group-hover:scale-110 group-hover:drop-shadow-[0_0_15px_rgba(168,85,247,1)]" aria-hidden>
        {b.badge_icon}
      </span>
      <span className="text-sm font-cinzel font-bold text-center text-purple-200 leading-tight">
        {b.badge_name}
      </span>
      <span className="text-[10px] font-inter text-center text-gray-400 line-clamp-2">
        {b.badge_description}
      </span>
      {showDate && (
        <span className="text-[10px] font-mono text-gray-500 mt-auto border-t border-gray-800 w-full text-center pt-2">
          {earnedDate}
        </span>
      )}
    </div>
  );
}
