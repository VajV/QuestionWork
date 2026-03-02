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
      <div className="rounded-xl border border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
        <span className="text-4xl">🏅</span>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          No badges earned yet. Complete quests to unlock achievements!
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
        <div className="flex items-center justify-center rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-sm text-gray-500 dark:text-gray-400">
          +{badges.length - limit} more
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
      className="flex flex-col items-center gap-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 shadow-sm hover:shadow-md transition-shadow"
    >
      <span className="text-3xl" aria-hidden>
        {b.badge_icon}
      </span>
      <span className="text-xs font-semibold text-center text-gray-800 dark:text-gray-100 leading-tight">
        {b.badge_name}
      </span>
      <span className="text-xs text-center text-gray-500 dark:text-gray-400 line-clamp-2">
        {b.badge_description}
      </span>
      {showDate && (
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {earnedDate}
        </span>
      )}
    </div>
  );
}
