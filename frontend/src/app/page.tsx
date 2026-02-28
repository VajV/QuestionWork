/**
 * Главная страница QuestionWork
 * 
 * Если пользователь авторизован — показывает профиль
 * Если нет — показывает приветственную страницу с кнопками
 */

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import LevelBadge from "@/components/rpg/LevelBadge";
import StatsPanel from "@/components/rpg/StatsPanel";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { getUserProfile, UserProfile, ApiError } from "@/lib/api";

// Mock-данные для fallback
const MOCK_PROFILE: UserProfile = {
  id: "user_123456",
  username: "NoviceDev",
  email: "novice@example.com",
  level: 1,
  grade: "novice",
  xp: 0,
  xp_to_next: 100,
  stats: { int: 10, dex: 10, cha: 10 },
  badges: [],
  bio: null,
  skills: [],
  created_at: "2026-02-28T00:00:00Z",
  updated_at: "2026-02-28T00:00:00Z",
};

/**
 * Компонент приветственной страницы (для неавторизованных)
 */
function WelcomePage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />
      
      <div className="container mx-auto px-4 py-16">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="max-w-4xl mx-auto text-center"
        >
          {/* Логотип */}
          <h1 className="text-6xl font-bold mb-6 glow-text">
            <span className="text-purple-400">Question</span>
            <span className="text-white">Work</span>
          </h1>
          
          <p className="text-xl text-gray-300 mb-8">
            IT-фриланс биржа с RPG-геймификацией
          </p>

          {/* Особенности */}
          <div className="grid md:grid-cols-3 gap-6 mb-12">
            <Card className="p-6 hover:border-purple-500/50 transition-colors">
              <div className="text-4xl mb-4">🎮</div>
              <h3 className="text-lg font-bold mb-2">RPG Профиль</h3>
              <p className="text-gray-400 text-sm">
                Прокачивай уровень, получай статы и достижения за выполнение заказов
              </p>
            </Card>
            
            <Card className="p-6 hover:border-purple-500/50 transition-colors">
              <div className="text-4xl mb-4">⚔️</div>
              <h3 className="text-lg font-bold mb-2">Квесты</h3>
              <p className="text-gray-400 text-sm">
                Бери заказы в работу как квесты и получай опыт и награды
              </p>
            </Card>
            
            <Card className="p-6 hover:border-purple-500/50 transition-colors">
              <div className="text-4xl mb-4">🏆</div>
              <h3 className="text-lg font-bold mb-2">Грейды</h3>
              <p className="text-gray-400 text-sm">
                Расти от Novice до Senior и получай доступ к лучшим заказам
              </p>
            </Card>
          </div>

          {/* Кнопки */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/auth/register">
              <Button variant="primary" className="text-lg px-8 py-3">
                🚀 Начать приключение
              </Button>
            </Link>
            <Link href="/auth/login">
              <Button variant="secondary" className="text-lg px-8 py-3">
                🔑 Уже с нами
              </Button>
            </Link>
          </div>

          {/* Демо-информация */}
          <div className="mt-12 p-6 bg-gray-800/30 rounded-xl border border-gray-700">
            <p className="text-gray-400 text-sm mb-2">🎯 Для быстрого старта используйте:</p>
            <code className="text-purple-300 bg-gray-800 px-3 py-1 rounded">
              novice_dev / password123
            </code>
          </div>
        </motion.div>
      </div>
    </main>
  );
}

/**
 * Компонент профиля (для авторизованных)
 */
function ProfileView({ profile }: { profile: UserProfile }) {
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
          <h1 className="text-3xl font-bold text-center mb-8">
            👤 Ваш профиль
          </h1>

          <Card className="p-6 mb-6">
            <div className="flex flex-col md:flex-row gap-6 items-center">
              <div className="relative">
                <div className="w-32 h-32 rounded-full bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center text-4xl font-bold glow">
                  {profile.username[0].toUpperCase()}
                </div>
                <div className="absolute -bottom-2 -right-2">
                  <LevelBadge level={profile.level} grade={profile.grade} />
                </div>
              </div>

              <div className="flex-1 w-full">
                <h2 className="text-2xl font-bold mb-2">{profile.username}</h2>
                <p className="text-gray-400 mb-4">{profile.email}</p>
                
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
                </div>

                <div className="flex gap-4">
                  <Link href="/quests">
                    <Button variant="primary">🔍 Найти квест</Button>
                  </Link>
                  <Link href="/marketplace">
                    <Button variant="secondary">💼 Биржа</Button>
                  </Link>
                </div>
              </div>
            </div>
          </Card>

          <StatsPanel stats={profile.stats} />
        </motion.div>
      </div>
    </main>
  );
}

/**
 * Основная страница
 */
export default function Home() {
  const router = useRouter();
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    async function loadProfile() {
      if (!isAuthenticated || !user?.id) {
        setLoading(false);
        return;
      }

      try {
        // Пытаемся загрузить профиль с API
        const data = await getUserProfile(user.id);
        setProfile(data);
      } catch (err) {
        console.error("Ошибка загрузки профиля:", err);
        // Используем данные из AuthContext (они уже есть после логина/регистрации)
        setProfile(user);
      } finally {
        setLoading(false);
      }
    }

    loadProfile();
  }, [isAuthenticated, user]);

  // Показываем лоадер при проверке авторизации
  if (authLoading || loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Загрузка...</p>
        </div>
      </main>
    );
  }

  // Если авторизован — показываем профиль
  if (isAuthenticated && profile) {
    return <ProfileView profile={profile} />;
  }

  // Если не авторизован — показываем приветствие
  return <WelcomePage />;
}
