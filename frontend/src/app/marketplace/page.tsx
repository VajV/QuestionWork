/**
 * Marketplace page — freelancer leaderboard and stats hub
 * Shows all registered freelancers ranked by XP and grade
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { getAllUsers, UserProfile, UserGrade } from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import LevelBadge from "@/components/rpg/LevelBadge";

const PAGE_SIZE = 20;

// ─── Grade filter options ────────────────────────────────────────────────────

const GRADE_FILTERS: { value: UserGrade | "all"; label: string; icon: string }[] = [
  { value: "all",    label: "Все",    icon: "🌐" },
  { value: "novice", label: "Novice", icon: "🌱" },
  { value: "junior", label: "Junior", icon: "⚡" },
  { value: "middle", label: "Middle", icon: "🔥" },
  { value: "senior", label: "Senior", icon: "💎" },
];

const GRADE_COLORS: Record<UserGrade, string> = {
  novice: "text-green-400 border-green-500/40 bg-green-500/10",
  junior: "text-blue-400 border-blue-500/40 bg-blue-500/10",
  middle: "text-orange-400 border-orange-500/40 bg-orange-500/10",
  senior: "text-purple-400 border-purple-500/40 bg-purple-500/10",
};

const RANK_ICONS = ["🥇", "🥈", "🥉"];

// ─── Stats card ──────────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: string;
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <Card className="p-5 text-center">
      <div className="text-3xl mb-2">{icon}</div>
      <div className="text-2xl font-bold text-white mb-1">{value}</div>
      <div className="text-sm font-medium text-gray-300">{label}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </Card>
  );
}

// ─── Freelancer row ──────────────────────────────────────────────────────────

function FreelancerRow({
  user,
  rank,
}: {
  user: UserProfile;
  rank: number;
}) {
  const xpPercent = Math.min(100, (user.xp / user.xp_to_next) * 100);
  const rankIcon = rank <= 3 ? RANK_ICONS[rank - 1] : null;

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: rank * 0.04 }}
    >
      <Link href={`/users/${user.id}`} className="block">
        <Card
          className={`p-4 hover:border-purple-500/50 transition-colors cursor-pointer ${
            rank === 1 ? "border-yellow-500/40 bg-yellow-500/5" : ""
          }`}
        >
          <div className="flex items-center gap-4">
          {/* Rank */}
          <div className="w-10 text-center flex-shrink-0">
            {rankIcon ? (
              <span className="text-2xl">{rankIcon}</span>
            ) : (
              <span className="text-gray-500 font-bold text-lg">#{rank}</span>
            )}
          </div>

          {/* Avatar */}
          <div className="relative flex-shrink-0">
            <div
              className={`w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold ${
                rank === 1
                  ? "bg-gradient-to-br from-yellow-500 to-orange-600"
                  : "bg-gradient-to-br from-purple-500 to-purple-700"
              }`}
            >
              {user.username[0].toUpperCase()}
            </div>
            <div className="absolute -bottom-1 -right-1 scale-75">
              <LevelBadge level={user.level} grade={user.grade} />
            </div>
          </div>

          {/* Name + XP bar */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="font-bold text-white truncate">{user.username}</span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                  GRADE_COLORS[user.grade as UserGrade]
                }`}
              >
                {user.grade}
              </span>
            </div>

            {/* XP bar */}
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-gray-700 rounded-full h-1.5 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-600 to-purple-400 transition-all duration-700"
                  style={{ width: `${xpPercent}%` }}
                />
              </div>
              <span className="text-xs text-gray-400 whitespace-nowrap">
                {user.xp} XP
              </span>
            </div>
          </div>

          {/* Stats */}
          <div className="hidden sm:flex gap-4 text-center flex-shrink-0">
            <div>
              <div className="text-xs text-gray-500 mb-0.5">INT</div>
              <div className="text-sm font-bold text-blue-400">
                {user.stats.int}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-0.5">DEX</div>
              <div className="text-sm font-bold text-green-400">
                {user.stats.dex}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-0.5">CHA</div>
              <div className="text-sm font-bold text-yellow-400">
                {user.stats.cha}
              </div>
            </div>
          </div>

          {/* Badges count */}
          {user.badges.length > 0 && (
            <div className="hidden md:flex items-center gap-1 flex-shrink-0">
              <span className="text-yellow-400">🏆</span>
              <span className="text-xs text-gray-400">{user.badges.length}</span>
            </div>
          )}

          {/* Skills */}
          {user.skills && user.skills.length > 0 && (
            <div className="hidden lg:flex gap-1 flex-shrink-0 max-w-32 flex-wrap">
              {user.skills.slice(0, 2).map((skill) => (
                <span
                  key={skill}
                  className="text-xs px-2 py-0.5 bg-gray-700 rounded text-gray-400"
                >
                  {skill}
                </span>
              ))}
              {user.skills.length > 2 && (
                <span className="text-xs text-gray-500">
                  +{user.skills.length - 2}
                </span>
              )}
            </div>
          )}
          </div>
        </Card>
      </Link>
    </motion.div>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────

export default function MarketplacePage() {
  const { isAuthenticated } = useAuth();

  const [users, setUsers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gradeFilter, setGradeFilter] = useState<UserGrade | "all">("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  // Load freelancers — fetchPage and append are passed explicitly to avoid
  // stale-closure issues when loadUsers is called from the load-more handler
  const loadUsers = useCallback(
    async (fetchPage: number, append: boolean) => {
      const skip = (fetchPage - 1) * PAGE_SIZE;
      setLoading(true);
      setError(null);
      try {
        const grade =
          gradeFilter === "all" ? undefined : (gradeFilter as UserGrade);
        const data = await getAllUsers(skip, PAGE_SIZE, grade);
        // Only show freelancers, sorted by XP descending
        const freelancers = data
          .filter((u) => u.role === "freelancer")
          .sort((a, b) => b.xp - a.xp);
        if (append) {
          setUsers((prev) => [...prev, ...freelancers]);
        } else {
          setUsers(freelancers);
        }
        setHasMore(data.length === PAGE_SIZE);
        setPage(fetchPage);
      } catch (err) {
        console.error("Failed to load users:", err);
        setError("Не удалось загрузить список фрилансеров.");
      } finally {
        setLoading(false);
      }
    },
    [gradeFilter],
  );

  // Reload from page 1 whenever the grade filter (or initial mount) fires loadUsers
  useEffect(() => {
    loadUsers(1, false);
  }, [loadUsers]);

  const loadMore = () => loadUsers(page + 1, true);

  // Client-side search filter
  const filtered = users.filter(
    (u) =>
      search.trim() === "" ||
      u.username.toLowerCase().includes(search.toLowerCase()) ||
      (u.skills || []).some((s) =>
        s.toLowerCase().includes(search.toLowerCase())
      )
  );

  // Aggregate stats
  const totalFreelancers = users.length;
  const totalXp = users.reduce((sum, u) => sum + u.xp, 0);
  const seniorCount = users.filter((u) => u.grade === "senior").length;
  const topXp = users[0]?.xp ?? 0;

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />

      <div className="container mx-auto px-4 py-8">
        {/* Page header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="text-center mb-10">
            <h1 className="text-5xl font-bold mb-3 glow-text">
              <span className="text-purple-400">⚔️</span>{" "}
              <span className="text-white">Биржа фрилансеров</span>
            </h1>
            <p className="text-gray-400 text-lg">
              Лучшие IT-специалисты платформы, отсортированные по опыту
            </p>
          </div>

          {/* Stats overview */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
            <StatCard
              icon="👥"
              label="Фрилансеров"
              value={totalFreelancers}
              sub="зарегистрировано"
            />
            <StatCard
              icon="⚡"
              label="Суммарный XP"
              value={totalXp.toLocaleString("ru-RU")}
              sub="заработано всего"
            />
            <StatCard
              icon="💎"
              label="Senior-ов"
              value={seniorCount}
              sub="экспертов"
            />
            <StatCard
              icon="🏆"
              label="Рекорд XP"
              value={topXp.toLocaleString("ru-RU")}
              sub="у лидера"
            />
          </div>

          {/* Filters and search */}
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            {/* Grade filter */}
            <div className="flex gap-2 flex-wrap">
              {GRADE_FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setGradeFilter(f.value)}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    gradeFilter === f.value
                      ? "bg-purple-600 text-white shadow-lg shadow-purple-500/30"
                      : "bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700"
                  }`}
                >
                  <span>{f.icon}</span>
                  <span>{f.label}</span>
                </button>
              ))}
            </div>

            {/* Search */}
            <div className="flex-1">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск по имени или навыку..."
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500 text-sm"
              />
            </div>
          </div>

          {/* Results count */}
          <div className="flex items-center justify-between mb-4">
            <p className="text-gray-400 text-sm">
              Найдено:{" "}
              <span className="text-white font-bold">{filtered.length}</span>{" "}
              фрилансеров
            </p>
            <Link href="/quests">
              <Button variant="primary" className="text-sm px-4 py-2">
                📜 Смотреть квесты
              </Button>
            </Link>
          </div>

          {/* Loader */}
          {loading && (
            <Card className="p-12 text-center">
              <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-gray-400">Загружаем лидерборд...</p>
            </Card>
          )}

          {/* Error */}
          {error && !loading && (
            <Card className="p-8 text-center border-red-500/30">
              <span className="text-5xl mb-4 block">⚠️</span>
              <h3 className="text-xl font-bold text-red-400 mb-2">
                Ошибка загрузки
              </h3>
              <p className="text-gray-400 mb-4">{error}</p>
              <Button
                onClick={() => setGradeFilter(gradeFilter)}
                variant="secondary"
              >
                🔄 Повторить
              </Button>
            </Card>
          )}

          {/* Empty state */}
          {!loading && !error && filtered.length === 0 && (
            <Card className="p-12 text-center">
              <span className="text-6xl mb-4 block">🔍</span>
              <h3 className="text-xl font-bold mb-2">Никого не найдено</h3>
              <p className="text-gray-400 mb-4">
                Попробуйте изменить фильтры или поисковый запрос
              </p>
              <Button
                onClick={() => {
                  setGradeFilter("all");
                  setSearch("");
                }}
                variant="secondary"
              >
                Сбросить фильтры
              </Button>
            </Card>
          )}

          {/* Leaderboard */}
          {!loading && !error && filtered.length > 0 && (
            <div className="space-y-2">
              {filtered.map((user, idx) => (
                <FreelancerRow key={user.id} user={user} rank={idx + 1} />
              ))}
            </div>
          )}

          {/* Load more */}
          {!loading && !error && hasMore && search.trim() === "" && (
            <div className="mt-6 text-center">
              <Button
                variant="secondary"
                onClick={loadMore}
                className="px-8 py-3"
              >
                Загрузить ещё
              </Button>
            </div>
          )}

          {/* CTA for non-authenticated */}
          {!isAuthenticated && !loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="mt-10"
            >
              <Card className="p-8 text-center border-purple-500/30 bg-purple-500/5">
                <div className="text-5xl mb-4">🚀</div>
                <h3 className="text-2xl font-bold mb-2">
                  Хотите попасть в топ?
                </h3>
                <p className="text-gray-400 mb-6">
                  Зарегистрируйтесь, берите квесты и зарабатывайте XP!
                </p>
                <div className="flex gap-4 justify-center">
                  <Link href="/auth/register">
                    <Button variant="primary" className="px-8 py-3">
                      🎮 Начать игру
                    </Button>
                  </Link>
                  <Link href="/quests">
                    <Button variant="secondary" className="px-8 py-3">
                      📜 Смотреть квесты
                    </Button>
                  </Link>
                </div>
              </Card>
            </motion.div>
          )}
        </motion.div>
      </div>
    </main>
  );
}
