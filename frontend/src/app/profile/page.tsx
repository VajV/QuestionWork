/**
 * Страница профиля пользователя
 * 
 * Показывает данные авторизованного пользователя
 * Доступна только после входа
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import LevelBadge from "@/components/rpg/LevelBadge";
import StatsPanel from "@/components/rpg/StatsPanel";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { getUserProfile, getMyBadges, UserProfile } from "@/lib/api";
import type { UserBadgeEarned } from "@/lib/api";
import BadgeGrid from "@/components/rpg/BadgeGrid";
import { User, Briefcase, Star, Award } from 'lucide-react';

export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [earnedBadges, setEarnedBadges] = useState<UserBadgeEarned[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [isAuthenticated, authLoading, router]);

  // Load profile
  const loadProfile = useCallback(async () => {
    if (!user?.id) return;
    setLoading(true);
    setError(null);
    try {
      const [data, badgeData] = await Promise.all([
        getUserProfile(user.id),
        getMyBadges(),
      ]);
      setProfile(data);
      setEarnedBadges(badgeData.badges);
    } catch (err) {
      console.error("Ошибка загрузки профиля:", err);
      setError("Не удалось загрузить профиль. Попробуйте позже.");
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  if (authLoading || loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto">
            <div className="glass-card p-6 mb-6">
              <div className="animate-pulse space-y-4">
                <div className="h-32 bg-gray-700/50 rounded-full w-32 mx-auto" />
                <div className="h-8 bg-gray-700/50 rounded w-48 mx-auto" />
                <div className="h-4 bg-gray-700/50 rounded w-32 mx-auto" />
              </div>
            </div>
          </div>
        </div>
      </main>
    );
  }

  // Error loading profile — show retry card instead of blank page
  if (error) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-4xl mx-auto">
            <div className="glass-card p-6 !border-red-500/50">
              <div className="text-center">
                <span className="text-4xl mb-2 block" aria-hidden="true">⚠️</span>
                <h3 className="text-xl font-bold text-red-400 mb-2">Ошибка загрузки профиля</h3>
                <p className="text-gray-400 mb-4">{error}</p>
                <Button onClick={loadProfile} variant="secondary">
                  🔄 Повторить
                </Button>
              </div>
            </div>
          </div>
        </div>
      </main>
    );
  }

  // If not authenticated, redirect is in progress
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
          <div className="glass-card p-6 mb-6">
            <div className="flex flex-col md:flex-row gap-6 items-center">
              {/* Аватар */}
              <div className="relative">
                <div className="w-32 h-32 rounded-full bg-gradient-to-br from-purple-500 via-violet-600 to-purple-900 flex items-center justify-center text-4xl font-bold ring-4 ring-purple-500/40 shadow-[0_0_40px_rgba(139,92,246,0.5)]">
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
                  <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${
                    profile.role === 'client'
                      ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30 shadow-[0_0_8px_rgba(59,130,246,0.4)]'
                      : 'bg-green-500/20 text-green-300 border border-green-500/30 shadow-[0_0_8px_rgba(34,197,94,0.4)]'
                  }`}>
                    {profile.role === 'client' ? <Briefcase size={14} aria-hidden="true" focusable="false" /> : <User size={14} aria-hidden="true" focusable="false" />}
                    {profile.role === 'client' ? 'Клиент' : 'Фрилансер'}
                  </span>
                </div>
                
                {/* XP Bar */}
                <div className="mb-4">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-purple-300">Experience</span>
                    <span className="text-purple-300">{profile.xp} / {profile.xp_to_next} XP</span>
                  </div>
                  <div className="w-full bg-white/5 backdrop-blur-sm border border-white/10 rounded-full h-4 relative overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${xpPercent}%` }}
                      transition={{ duration: 1, delay: 0.3 }}
                      className="h-full bg-gradient-to-r from-violet-600 via-purple-500 to-fuchsia-400 shadow-[0_0_12px_rgba(139,92,246,0.7)]"
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
          </div>

          {/* Статы */}
          <StatsPanel stats={profile.stats} />

          {/* Бейджи */}
          <div className="glass-card p-6 mt-6">
            <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Award className="text-yellow-400" size={24} aria-hidden="true" focusable="false" /> Достижения
            </h3>
            <BadgeGrid badges={earnedBadges} />
          </div>

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
