/**
 * Главная страница QuestionWork
 *
 * Если пользователь авторизован — показывает профиль
 * Если нет — показывает приветственную страницу с кнопками
 */

"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import LevelBadge from "@/components/rpg/LevelBadge";
import StatsPanel from "@/components/rpg/StatsPanel";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { getUserProfile, UserProfile } from "@/lib/api";

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
          className="max-w-4xl mx-auto text-center relative"
        >
          {/* Логотип */}
          <h1 className="text-5xl md:text-7xl font-cinzel font-bold mb-6 tracking-wider">
            <span className="text-amber-500 drop-shadow-[0_0_15px_rgba(217,119,6,0.6)] relative z-10 block md:inline">Question</span>
            <span className="text-gray-200">Work</span>
          </h1>

          <div className="divider-ornament my-8 max-w-lg mx-auto"></div>

          <p className="text-xl font-inter text-gray-300 mb-12 uppercase tracking-[0.2em]">
            IT-гильдия с RPG-механикой
          </p>

          {/* Особенности */}
          <div className="grid md:grid-cols-3 gap-8 mb-16 px-4">
            <div className="rpg-card p-8 group hover:scale-105 transition-all duration-300">
              <div className="text-5xl mb-6 drop-shadow-[0_0_10px_rgba(168,85,247,0.8)] grayscale group-hover:grayscale-0 transition-all">🧙‍♂️</div>
              <h3 className="text-lg font-cinzel font-bold mb-4 text-purple-300">Путь Героя</h3>
              <p className="text-gray-400 font-inter text-sm leading-relaxed">
                Прокачивайте уровень, распределяйте статы и собирайте трофеи за выполненные контракты
              </p>
            </div>

            <div className="rpg-card p-8 group hover:scale-105 transition-all duration-300">
              <div className="text-5xl mb-6 drop-shadow-[0_0_10px_rgba(217,119,6,0.8)] grayscale group-hover:grayscale-0 transition-all">📜</div>
              <h3 className="text-lg font-cinzel font-bold mb-4 text-amber-500">Доска Заказов</h3>
              <p className="text-gray-400 font-inter text-sm leading-relaxed">
                Берите квесты, договаривайтесь с заказчиками и получайте золото с опытом
              </p>
            </div>

            <div className="rpg-card p-8 group hover:scale-105 transition-all duration-300">
              <div className="text-5xl mb-6 drop-shadow-[0_0_10px_rgba(59,130,246,0.8)] grayscale group-hover:grayscale-0 transition-all">👑</div>
              <h3 className="text-lg font-cinzel font-bold mb-4 text-blue-400">Иерархия</h3>
              <p className="text-gray-400 font-inter text-sm leading-relaxed">
                Развивайтесь от Новичка до Магистра и получайте доступ к элитным заданиям
              </p>
            </div>
          </div>

          {/* Кнопки */}
          <div className="flex flex-col sm:flex-row gap-6 justify-center">
            <Link href="/auth/register">
              <Button variant="primary" className="text-lg px-10 py-4 w-full sm:w-auto shadow-[0_0_20px_rgba(217,119,6,0.4)]">
                🚀 Начать Приключение
              </Button>
            </Link>
            <Link href="/auth/login">
              <Button variant="secondary" className="text-lg px-10 py-4 w-full sm:w-auto">
                🔑 Войти во Врата
              </Button>
            </Link>
          </div>

          {/* Демо-информация */}
          <div className="mt-16 p-6 bg-black/40 rounded border border-amber-900/30 font-mono text-sm max-w-sm mx-auto shadow-inner">
            <p className="text-gray-500 mb-3 uppercase tracking-wider">🎯 Быстрый старт (Dev):</p>
            <code className="text-amber-500 bg-black px-4 py-2 rounded border border-gray-800 shadow-[inset_0_0_10px_rgba(0,0,0,0.8)] block">
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
    <main className="min-h-screen bg-gray-950 text-gray-200 font-inter">
      <Header />

      <div className="container mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-4xl mx-auto"
        >
          <div className="text-center mb-10 mt-6">
            <h1 className="text-4xl font-cinzel font-bold text-amber-500 drop-shadow-[0_0_10px_rgba(217,119,6,0.5)] uppercase tracking-widest mb-2">
              Свиток Героя
            </h1>
            <div className="divider-ornament w-48 mx-auto"></div>
          </div>

          <Card className="mb-8 p-0 overflow-hidden bg-transparent border-none shadow-none">
            <div className="rpg-card p-8 flex flex-col md:flex-row gap-8 items-center md:items-start relative">
              {/* Avatar section */}
              <div className="relative shrink-0">
                <div className="avatar-frame w-32 h-32 flex items-center justify-center text-4xl font-cinzel font-bold text-amber-500 bg-gray-900 mx-auto">
                  {profile.username[0].toUpperCase()}
                </div>
                <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 z-10">
                  <LevelBadge level={profile.level} grade={profile.grade} />
                </div>
              </div>

              {/* Info section */}
              <div className="flex-1 w-full text-center md:text-left mt-4 md:mt-0">
                <h2 className="text-3xl font-cinzel font-bold text-gray-100 mb-1">{profile.username}</h2>
                <p className="text-gray-500 font-mono text-sm mb-6 flex items-center justify-center md:justify-start gap-2">
                  <span className="text-amber-700">🔮</span> {profile.email}
                </p>

                <div className="mb-6 bg-black/40 p-4 border border-purple-900/30 rounded">
                  <div className="flex justify-between font-mono text-xs mb-2">
                    <span className="text-purple-400 uppercase tracking-widest shadow-purple-900/50 drop-shadow-md">Кумулятивный Опыт</span>
                    <span className="text-amber-500">
                      {profile.xp} <span className="text-gray-600">/</span> {profile.xp_to_next} XP
                    </span>
                  </div>
                  <div className="xp-bar-track h-3">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(xpPercent, 100)}%` }}
                      transition={{ duration: 1.5, ease: "easeOut", delay: 0.3 }}
                      className="stat-bar-fill-xp relative"
                    >
                      <div className="absolute top-0 right-0 bottom-0 w-10 bg-gradient-to-r from-transparent to-white/30"></div>
                    </motion.div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-4 justify-center md:justify-start">
                  <Link href="/quests">
                    <Button variant="primary" className="shadow-[0_0_15px_rgba(217,119,6,0.3)] hover:shadow-[0_0_25px_rgba(217,119,6,0.5)] transition-shadow">
                      📜 Искать Контракты
                    </Button>
                  </Link>
                  <Link href="/marketplace">
                    <Button variant="secondary" className="border-purple-900/50 hover:border-purple-500/50">
                      ⚖️ Зал Гильдии
                    </Button>
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
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

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
