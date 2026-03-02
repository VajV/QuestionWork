/**
 * Публичный профиль пользователя (фрилансера)
 *
 * Маршрут: /users/[id]
 * - Открыт для всех (не требует авторизации)
 * - Показывает grade, уровень, XP, статы, бейджи, навыки
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import { getUserProfile, UserProfile } from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import LevelBadge from "@/components/rpg/LevelBadge";
import StatsPanel from "@/components/rpg/StatsPanel";

// ─── Grade display helpers ────────────────────────────────────────────────────

const GRADE_COLORS: Record<string, string> = {
  novice: "text-gray-400 border-gray-600",
  junior: "text-green-400 border-green-600",
  middle: "text-blue-400 border-blue-600",
  senior: "text-yellow-400 border-yellow-600",
};

const GRADE_LABEL: Record<string, string> = {
  novice: "Novice",
  junior: "Junior",
  middle: "Middle",
  senior: "Senior",
};

export default function PublicProfilePage() {
  const params = useParams();
  const userId = params.id as string;
  const { user: currentUser } = useAuth();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getUserProfile(userId);
      setProfile(data);
    } catch (err: unknown) {
      const status =
        err instanceof Response ? err.status : (err as { status?: number })?.status;
      if (status === 404) {
        setError("Пользователь не найден.");
      } else {
        setError("Не удалось загрузить профиль. Попробуйте позже.");
      }
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  // ─── Loading ───────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-12">
          <Card className="p-12 text-center">
            <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-400">Загрузка профиля...</p>
          </Card>
        </div>
      </main>
    );
  }

  // ─── Error ─────────────────────────────────────────────────────────────────

  if (error || !profile) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-12 max-w-lg">
          <Card className="p-8 text-center border-red-500/30">
            <span className="text-5xl mb-4 block">😕</span>
            <h2 className="text-xl font-bold text-red-400 mb-2">
              {error ?? "Профиль недоступен"}
            </h2>
            <div className="flex gap-3 justify-center mt-6">
              <Button variant="secondary" onClick={loadProfile}>
                🔄 Повторить
              </Button>
              <Link href="/marketplace">
                <Button variant="primary">← Биржа</Button>
              </Link>
            </div>
          </Card>
        </div>
      </main>
    );
  }

  const xpPercent = Math.min(100, (profile.xp / profile.xp_to_next) * 100);
  const isOwnProfile = currentUser?.id === profile.id;

  // ─── Profile render ────────────────────────────────────────────────────────

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />

      <div className="container mx-auto px-4 py-8 max-w-3xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          {/* Back link */}
          <Link
            href="/marketplace"
            className="text-gray-400 hover:text-white text-sm transition-colors flex items-center gap-1"
          >
            ← Вернуться на биржу
          </Link>

          {/* Hero card */}
          <Card className="p-6">
            <div className="flex items-start gap-5 flex-wrap">
              {/* Avatar */}
              <div className="relative flex-shrink-0">
                <div className="w-20 h-20 rounded-full bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center text-3xl font-bold text-white">
                  {profile.username[0].toUpperCase()}
                </div>
                <div className="absolute -bottom-2 -right-2">
                  <LevelBadge level={profile.level} grade={profile.grade} />
                </div>
              </div>

              {/* Name + grade */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 flex-wrap mb-1">
                  <h1 className="text-2xl font-bold text-white">
                    {profile.username}
                  </h1>
                  <span
                    className={`text-sm px-3 py-1 rounded-full border font-medium ${GRADE_COLORS[profile.grade] ?? ""}`}
                  >
                    {GRADE_LABEL[profile.grade] ?? profile.grade}
                  </span>
                  {isOwnProfile && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-purple-600/30 border border-purple-500/40 text-purple-300">
                      Вы
                    </span>
                  )}
                </div>

                <p className="text-gray-400 text-sm mb-3">
                  Уровень {profile.level} · Фрилансер
                </p>

                {/* XP bar */}
                <div className="flex items-center gap-3">
                  <div className="flex-1 bg-gray-700 rounded-full h-2 overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-purple-600 to-purple-400"
                      initial={{ width: 0 }}
                      animate={{ width: `${xpPercent}%` }}
                      transition={{ duration: 0.8, ease: "easeOut" }}
                    />
                  </div>
                  <span className="text-sm text-gray-400 whitespace-nowrap">
                    {profile.xp} / {profile.xp_to_next} XP
                  </span>
                </div>
              </div>

              {/* Own-profile edit button */}
              {isOwnProfile && (
                <Link href="/profile">
                  <Button variant="secondary" className="flex-shrink-0">
                    ✏️ Редактировать
                  </Button>
                </Link>
              )}
            </div>
          </Card>

          {/* Stats */}
          <Card className="p-6">
            <h2 className="text-lg font-bold mb-4">📊 Характеристики</h2>
            <StatsPanel stats={profile.stats} />
          </Card>

          {/* Skills */}
          {profile.skills && profile.skills.length > 0 && (
            <Card className="p-6">
              <h2 className="text-lg font-bold mb-4">🛠 Навыки</h2>
              <div className="flex flex-wrap gap-2">
                {profile.skills.map((skill) => (
                  <span
                    key={skill}
                    className="px-3 py-1.5 bg-gray-700/60 border border-gray-600/50 rounded-lg text-sm text-gray-200"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </Card>
          )}

          {/* Badges */}
          {profile.badges.length > 0 && (
            <Card className="p-6">
              <h2 className="text-lg font-bold mb-4">
                🏆 Достижения ({profile.badges.length})
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {profile.badges.map((badge) => (
                  <div
                    key={badge.id}
                    className="flex items-center gap-3 p-3 rounded-lg bg-gray-800/60 border border-gray-700/50"
                  >
                    <span className="text-2xl flex-shrink-0">{badge.icon}</span>
                    <div className="min-w-0">
                      <div className="font-medium text-sm text-white truncate">
                        {badge.name}
                      </div>
                      <div className="text-xs text-gray-400 truncate">
                        {badge.description}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* No badges placeholder */}
          {profile.badges.length === 0 && (
            <Card className="p-6 text-center border-dashed border-gray-700">
              <span className="text-4xl mb-2 block">🔒</span>
              <p className="text-gray-500 text-sm">Достижений пока нет</p>
            </Card>
          )}
        </motion.div>
      </div>
    </main>
  );
}
