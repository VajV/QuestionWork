/**
 * EventLeaderboard — таблица лидеров ивента
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getEventLeaderboard } from "@/lib/api";
import { EventLeaderboardResponse } from "@/types";
import { Trophy, Medal, Award } from "lucide-react";

interface EventLeaderboardProps {
  eventId: string;
}

const RANK_ICONS: Record<number, { icon: React.ReactNode; color: string }> = {
  1: { icon: <Trophy className="w-4 h-4" />, color: "text-yellow-400" },
  2: { icon: <Medal className="w-4 h-4" />, color: "text-gray-300" },
  3: { icon: <Award className="w-4 h-4" />, color: "text-amber-600" },
};

const GRADE_COLORS: Record<string, string> = {
  novice: "text-gray-400",
  junior: "text-emerald-400",
  middle: "text-violet-400",
  senior: "text-amber-400",
};

export default function EventLeaderboard({ eventId }: EventLeaderboardProps) {
  const [data, setData] = useState<EventLeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchLeaderboard = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getEventLeaderboard(eventId, { limit: 50 });
      setData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    fetchLeaderboard();
  }, [fetchLeaderboard]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return <p className="text-red-400 text-sm text-center py-4">{error}</p>;
  }

  if (!data || data.entries.length === 0) {
    return (
      <p className="text-gray-500 text-sm text-center py-8">
        Пока нет участников
      </p>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-cinzel font-bold text-gray-300 uppercase tracking-wider">
          Таблица лидеров
        </h3>
        <span className="text-xs text-gray-500">
          {data.total_participants} участников
        </span>
      </div>

      <div className="rounded-lg border border-gray-700/60 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-800/60 text-gray-400 text-xs uppercase tracking-wider">
              <th className="py-2 px-3 text-left w-12">#</th>
              <th className="py-2 px-3 text-left">Игрок</th>
              <th className="py-2 px-3 text-center">Грейд</th>
              <th className="py-2 px-3 text-right">Очки</th>
              <th className="py-2 px-3 text-right">XP бонус</th>
            </tr>
          </thead>
          <tbody>
            {data.entries.map((entry) => {
              const rankInfo = RANK_ICONS[entry.rank];
              const gradeColor = GRADE_COLORS[entry.grade] || "text-gray-400";

              return (
                <tr
                  key={entry.user_id}
                  className={`border-t border-gray-700/40 transition-colors hover:bg-gray-800/40 ${
                    entry.rank <= 3 ? "bg-gray-800/20" : ""
                  }`}
                >
                  <td className="py-2.5 px-3">
                    {rankInfo ? (
                      <span className={rankInfo.color}>{rankInfo.icon}</span>
                    ) : (
                      <span className="text-gray-500 text-xs">{entry.rank}</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3">
                    <Link
                      href={`/users/${entry.user_id}`}
                      className="text-gray-200 hover:text-amber-300 transition-colors font-medium"
                    >
                      {entry.username}
                    </Link>
                  </td>
                  <td className={`py-2.5 px-3 text-center text-xs font-cinzel font-bold uppercase ${gradeColor}`}>
                    {entry.grade}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-gray-200">
                    {entry.score.toLocaleString()}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    {entry.xp_bonus > 0 ? (
                      <span className="text-amber-400 font-mono">
                        +{entry.xp_bonus}
                      </span>
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
                    {entry.badge_awarded && (
                      <span className="ml-1.5" title="Бейдж получен">🏅</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
