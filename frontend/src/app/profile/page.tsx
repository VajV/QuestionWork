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
import Button from "@/components/ui/Button";
import { getUserProfile, getMyBadges, UserProfile } from "@/lib/api";
import type { UserBadgeEarned } from "@/lib/api";
import BadgeGrid from "@/components/rpg/BadgeGrid";
import { User, Briefcase, Award } from 'lucide-react';

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
          <div className="rpg-card p-8 flex flex-col md:flex-row gap-8 items-center relative overflow-hidden mb-6">
            <div className="absolute top-0 right-0 w-64 h-64 bg-purple-600 rounded-full blur-[100px] opacity-20 pointer-events-none"></div>

            <div className="avatar-frame relative z-10 shrink-0">
              <div className="w-full h-full bg-gray-900 rounded-full flex items-center justify-center border-4 border-amber-900/50 shadow-inner">
                <span className="text-5xl font-cinzel text-amber-500 font-bold drop-shadow-[0_0_8px_rgba(217,119,6,0.8)]">
                  {profile.username[0].toUpperCase()}
                </span>
              </div>
              
              <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 bg-black border-2 border-amber-600 rounded px-4 py-1 shadow-[0_0_15px_rgba(217,119,6,0.6)] z-20">
                <span className="font-cinzel text-amber-500 font-bold whitespace-nowrap">Ур. {profile.level}</span>
              </div>
            </div>

            <div className="flex-1 w-full relative z-10">
               <div className="flex justify-between items-start">
                  <div>
                     <h1 className="text-4xl font-cinzel text-gray-100 font-bold tracking-wider mb-2 drop-shadow-md">
                       {profile.username}
                     </h1>
                     <p className="text-amber-600/80 font-inter uppercase tracking-[0.2em] text-sm mb-6 flex items-center gap-2">
                       {profile.role === 'client' ? <Briefcase size={14} /> : <User size={14} />} 
                       {profile.role === 'client' ? 'Клиент' : 'Фрилансер'}
                     </p>
                  </div>
                  <LevelBadge level={profile.level} grade={profile.grade} size="lg" showGradeText={true} />
               </div>

               {/* Интегрированный XP бар */}
               <div className="mt-4">
                  <div className="flex justify-between font-mono text-sm text-gray-400 mb-2">
                    <span>ОПЫТ</span>
                    <span className="text-purple-400">{profile.xp} / {profile.xp_to_next} XP</span>
                  </div>
                  <div className="xp-bar-track relative overflow-hidden">
                     <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(xpPercent, 100)}%` }}
                        transition={{ duration: 1, delay: 0.3 }}
                        className="xp-bar-fill h-full absolute top-0 left-0" 
                     />
                  </div>
               </div>
            </div>
          </div>

          {/* Статы */}
          <StatsPanel stats={profile.stats} />

          {/* Бейджи */}
          <div className="rpg-card p-6 mt-6">
            <h3 className="text-xl font-cinzel text-amber-500 mb-4 flex items-center gap-2 border-b border-amber-900/30 pb-2">
              <Award className="text-amber-500" size={24} aria-hidden="true" focusable="false" /> Достижения
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
