"use client";

import { motion } from "framer-motion";
import Header from "@/components/layout/Header";
import LevelBadge from "@/components/rpg/LevelBadge";
import StatsPanel from "@/components/rpg/StatsPanel";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

// Типы для профиля
interface Profile {
  username: string;
  level: number;
  grade: string;
  xp: number;
  maxXp: number;
  stats: {
    int: number;
    dex: number;
    cha: number;
  };
}

// Демо-данные (позже будут приходить с бэкенда)
const demoProfile: Profile = {
  username: "NoviceDev",
  level: 1,
  grade: "Novice",
  xp: 0,
  maxXp: 100,
  stats: {
    int: 10,
    dex: 10,
    cha: 10,
  },
};

export default function Home() {
  const profile = demoProfile;
  const xpPercent = (profile.xp / profile.maxXp) * 100;

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
          {/* Заголовок */}
          <h1 className="text-4xl font-bold text-center mb-8 glow-text">
            <span className="text-purple-400">Question</span>
            <span className="text-white">Work</span>
          </h1>

          {/* Профиль */}
          <Card className="p-6 mb-6">
            <div className="flex flex-col md:flex-row gap-6 items-center">
              {/* Аватар */}
              <div className="relative">
                <div className="w-32 h-32 rounded-full bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center text-4xl font-bold glow">
                  {profile.username[0]}
                </div>
                <div className="absolute -bottom-2 -right-2">
                  <LevelBadge level={profile.level} grade={profile.grade} />
                </div>
              </div>

              {/* Инфо */}
              <div className="flex-1 w-full">
                <h2 className="text-2xl font-bold mb-2">{profile.username}</h2>
                <p className="text-gray-400 mb-4">IT Freelancer</p>
                
                {/* XP Bar */}
                <div className="mb-4">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-purple-300">Experience</span>
                    <span className="text-purple-300">{profile.xp} / {profile.maxXp} XP</span>
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

                {/* Кнопка */}
                <Button disabled variant="primary">
                  🔒 Начать квест (скоро)
                </Button>
              </div>
            </div>
          </Card>

          {/* Статы */}
          <StatsPanel stats={profile.stats} />
        </motion.div>
      </div>
    </main>
  );
}
