/**
 * Страница профиля пользователя
 * 
 * Показывает данные авторизованного пользователя
 * Доступна только после входа
 */

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import LevelBadge from "@/components/rpg/LevelBadge";
import StatsPanel from "@/components/rpg/StatsPanel";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { getUserProfile, UserProfile } from "@/lib/api";

export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // Редирект если не авторизован
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [isAuthenticated, authLoading, router]);

  // Загрузка профиля
  useEffect(() => {
    async function loadProfile() {
      if (!user?.id) return;

      try {
        const data = await getUserProfile(user.id);
        setProfile(data);
      } catch (error) {
        console.error("Ошибка загрузки профиля:", error);
      } finally {
        setLoading(false);
      }
    }

    loadProfile();
  }, [user?.id]);

  // Показываем лоадер во время загрузки
  if (authLoading || loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto">
            <Card className="p-6 mb-6">
              <div className="animate-pulse space-y-4">
                <div className="h-32 bg-gray-700 rounded-full w-32 mx-auto" />
                <div className="h-8 bg-gray-700 rounded w-48 mx-auto" />
                <div className="h-4 bg-gray-700 rounded w-32 mx-auto" />
              </div>
            </Card>
          </div>
        </div>
      </main>
    );
  }

  // Если не авторизован — не рендерим (будет редирект)
  if (!isAuthenticated || !profile) {
    return null;
  }

  const xpPercent = (profile.xp / profile.xp_to_next) * 100;

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />
      
      <div className="container mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-4xl mx-auto"
        >
          {/* Заголовок страницы */}
          <h1 className="text-3xl font-bold text-center mb-8">
            👤 Профиль пользователя
          </h1>

          {/* Основная карточка профиля */}
          <Card className="p-6 mb-6">
            <div className="flex flex-col md:flex-row gap-6 items-center">
              {/* Аватар */}
              <div className="relative">
                <div className="w-32 h-32 rounded-full bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center text-4xl font-bold glow">
                  {profile.username[0].toUpperCase()}
                </div>
                <div className="absolute -bottom-2 -right-2">
                  <LevelBadge level={profile.level} grade={profile.grade} />
                </div>
              </div>

              {/* Инфо */}
              <div className="flex-1 w-full">
                <h2 className="text-2xl font-bold mb-2">{profile.username}</h2>
                <p className="text-gray-400 mb-4">{profile.email}</p>
                
                {/* Роль */}
                <div className="mb-4">
                  <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                    profile.role === 'client'
                      ? 'bg-blue-500/20 text-blue-300 border border-blue-500/50'
                      : 'bg-green-500/20 text-green-300 border border-green-500/50'
                  }`}>
                    {profile.role === 'client' ? '💼 Клиент' : '👨‍💻 Фрилансер'}
                  </span>
                </div>
                
                {/* XP Bar */}
                <div className="mb-4">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-purple-300">Experience</span>
                    <span className="text-purple-300">{profile.xp} / {profile.xp_to_next} XP</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-4 overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${xpPercent}%` }}
                      transition={{ duration: 1, delay: 0.3 }}
                      className="h-full bg-gradient-to-r from-purple-600 to-purple-400"
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    До следующего уровня: {profile.xp_to_next - profile.xp} XP
                  </p>
                </div>

                {/* Метаданные */}
                <div className="flex gap-4 text-sm text-gray-400">
                  <span>📅 Зарегистрирован: {new Date(profile.created_at).toLocaleDateString('ru-RU')}</span>
                </div>
              </div>
            </div>
          </Card>

          {/* Статы */}
          <StatsPanel stats={profile.stats} />

          {/* Бейджи */}
          {profile.badges.length > 0 && (
            <Card className="p-6 mt-6">
              <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
                <span>🏆</span> Достижения
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {profile.badges.map((badge) => (
                  <div key={badge.id} className="flex items-center gap-3 p-3 bg-gray-800/50 rounded-lg">
                    <span className="text-3xl">{badge.icon}</span>
                    <div>
                      <div className="font-medium text-white">{badge.name}</div>
                      <div className="text-sm text-gray-400">{badge.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Навигация */}
          <div className="flex gap-4 mt-6">
            <Button variant="secondary" onClick={() => router.push("/quests")}>
              🔍 Найти квест
            </Button>
            <Button variant="secondary" onClick={() => router.push("/marketplace")}>
              💼 Биржа заказов
            </Button>
          </div>
        </motion.div>
      </div>
    </main>
  );
}
