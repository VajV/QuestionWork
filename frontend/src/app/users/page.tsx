"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "@/lib/motion";
import Header from "@/components/layout/Header";
import LevelBadge from "@/components/rpg/LevelBadge";
import Button from "@/components/ui/Button";
import { getAllUsers, getApiErrorMessage } from "@/lib/api";
import type { PublicUserProfile, UserGrade } from "@/lib/api";
import { Users, ChevronRight, Star, CheckCircle } from "lucide-react";

const PAGE_SIZE = 20;

const GRADE_OPTIONS: { value: UserGrade | "all"; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "novice", label: "Novice" },
  { value: "junior", label: "Junior" },
  { value: "middle", label: "Middle" },
  { value: "senior", label: "Senior" },
];

const SORT_OPTIONS: {
  value: "created_at" | "xp" | "level" | "username";
  label: string;
}[] = [
  { value: "created_at", label: "Дата регистрации" },
  { value: "xp", label: "Опыт (XP)" },
  { value: "level", label: "Уровень" },
  { value: "username", label: "Имя" },
];

const GRADE_COLORS: Record<string, string> = {
  novice: "text-gray-400 border-gray-600",
  junior: "text-green-400 border-green-600",
  middle: "text-blue-400 border-blue-600",
  senior: "text-purple-400 border-purple-600",
};

const BUDGET_BAND_LABELS: Record<string, string> = {
  up_to_15k: "До 15k",
  "15k_to_50k": "15k-50k",
  "50k_to_150k": "50k-150k",
  "150k_plus": "150k+",
};

const AVAILABILITY_LABELS: Record<string, string> = {
  available: "Доступен",
  limited: "1-2 слота",
  busy: "Загружен",
};

export default function UserDirectoryPage() {
  const router = useRouter();
  const [users, setUsers] = useState<PublicUserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [grade, setGrade] = useState<UserGrade | "all">("all");
  const [sortBy, setSortBy] = useState<
    "created_at" | "xp" | "level" | "username"
  >("xp");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getAllUsers(
        offset,
        PAGE_SIZE,
        grade === "all" ? undefined : grade,
        sortBy,
        sortOrder,
      );
      setUsers(result.users);
      setHasMore(result.has_more);
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось загрузить список пользователей."));
    } finally {
      setLoading(false);
    }
  }, [offset, grade, sortBy, sortOrder]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setOffset(0);
  }, [grade, sortBy, sortOrder]);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Header />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-3xl font-cinzel text-amber-400 mb-2 flex items-center gap-3">
            <Users size={32} /> Участники платформы
          </h1>
          <p className="text-gray-400 mb-8">
            Найдите фрилансеров и заказчиков на платформе QuestionWork.
          </p>

          {/* Filters */}
          <div className="flex flex-wrap gap-4 mb-6">
            {/* Grade filter */}
            <div className="flex gap-1 rounded-lg bg-gray-900/50 p-1">
              {GRADE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setGrade(opt.value)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    grade === opt.value
                      ? "bg-amber-500/20 text-amber-400"
                      : "text-gray-400 hover:text-white hover:bg-gray-800"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            {/* Sort order */}
            <button
              onClick={() =>
                setSortOrder((prev) => (prev === "desc" ? "asc" : "desc"))
              }
              className="px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-700 text-sm text-gray-300 hover:text-white transition-colors"
            >
              {sortOrder === "desc" ? "↓ По убыванию" : "↑ По возрастанию"}
            </button>
          </div>

          {/* Loading */}
          {loading && (
            <div className="text-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500 mx-auto mb-4" />
              <p className="text-gray-500">Загрузка...</p>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 mb-6">
              {error}
            </div>
          )}

          {/* Empty */}
          {!loading && !error && users.length === 0 && (
            <div className="text-center py-16">
              <Users size={48} className="mx-auto mb-4 text-gray-600" />
              <p className="text-gray-500">Пользователи не найдены.</p>
            </div>
          )}

          {/* User list */}
          {!loading && !error && users.length > 0 && (
            <div className="space-y-3">
              {users.map((u) => (
                <motion.div
                  key={u.id}
                  whileHover={{ x: 4 }}
                  onClick={() => router.push(`/users/${u.id}`)}
                  className="flex items-center gap-4 rounded-xl border border-gray-800 bg-gray-900/60 p-4 cursor-pointer hover:border-amber-500/30 hover:bg-gray-900/80 transition-all"
                >
                  <LevelBadge level={u.level} grade={u.grade} size="sm" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-cinzel font-bold text-white truncate">
                        {u.username}
                      </span>
                      <span
                        className={`text-[10px] uppercase tracking-wider font-mono border rounded px-1.5 py-0.5 ${GRADE_COLORS[u.grade] || "text-gray-400 border-gray-600"}`}
                      >
                        {u.grade}
                      </span>
                      <span className="text-[10px] text-gray-500 capitalize">
                        {u.role === "freelancer"
                          ? "фрилансер"
                          : u.role === "client"
                            ? "заказчик"
                            : u.role}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                      <span>{u.xp} XP</span>
                      {u.avg_rating != null && (
                        <span className="flex items-center gap-1 text-amber-400">
                          <Star size={12} /> {u.avg_rating.toFixed(1)}
                          {(u.review_count ?? 0) > 0 && (
                            <span className="text-gray-500">({u.review_count})</span>
                          )}
                        </span>
                      )}
                      {(u.confirmed_quest_count ?? 0) > 0 && (
                        <span className="flex items-center gap-1 text-emerald-400">
                          <CheckCircle size={12} /> {u.confirmed_quest_count} квестов
                        </span>
                      )}
                      {u.typical_budget_band && (
                        <span>{BUDGET_BAND_LABELS[u.typical_budget_band] ?? u.typical_budget_band}</span>
                      )}
                      {u.availability_status && (
                        <span>{AVAILABILITY_LABELS[u.availability_status] ?? u.availability_status}</span>
                      )}
                      {u.response_time_hint && (
                        <span className="truncate max-w-[220px]">{u.response_time_hint}</span>
                      )}
                      {u.character_class && (
                        <span className="capitalize">{u.character_class}</span>
                      )}
                      {u.skills.length > 0 && (
                        <span className="truncate max-w-[200px]">
                          {u.skills.slice(0, 3).join(", ")}
                          {u.skills.length > 3 &&
                            ` +${u.skills.length - 3}`}
                        </span>
                      )}
                    </div>
                  </div>
                  <ChevronRight size={18} className="text-gray-600" />
                </motion.div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {!loading && !error && (
            <div className="flex justify-center gap-3 mt-6">
              {offset > 0 && (
                <Button
                  variant="secondary"
                  onClick={() =>
                    setOffset((prev) => Math.max(0, prev - PAGE_SIZE))
                  }
                >
                  ← Назад
                </Button>
              )}
              {hasMore && users.length > 0 && (
                <Button
                  variant="secondary"
                  onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
                >
                  Далее →
                </Button>
              )}
            </div>
          )}
        </motion.div>
      </main>
    </div>
  );
}
