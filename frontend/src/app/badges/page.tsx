"use client";

import { useMemo } from "react";
import { motion } from "@/lib/motion";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import { getBadgeCatalogue, getMyBadges } from "@/lib/api";
import type { Badge } from "@/lib/api";
import { Award, Lock, CheckCircle } from "lucide-react";
import { useSWRFetch } from "@/hooks/useSWRFetch";

export default function BadgeCataloguePage() {
  const { isAuthenticated } = useAuth();

  const {
    data: catalogue,
    error: catError,
    isLoading: catLoading,
  } = useSWRFetch("/badges/catalogue", () => getBadgeCatalogue());

  const {
    data: myBadges,
    error: myError,
    isLoading: myLoading,
  } = useSWRFetch(
    isAuthenticated ? "/badges/me" : null,
    () => getMyBadges(),
  );

  const badges: Badge[] = catalogue?.badges ?? [];
  const earned = useMemo(
    () => new Set(myBadges?.badges.map((b) => b.badge_id) ?? []),
    [myBadges],
  );
  const loading = catLoading || myLoading;
  const error = catError || myError ? "Не удалось загрузить каталог достижений." : null;

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
            <Award size={32} /> Каталог достижений
          </h1>
          <p className="text-gray-400 mb-8">
            Все доступные достижения на платформе. Выполняйте квесты и
            прокачивайтесь, чтобы открывать новые!
          </p>

          {loading && (
            <div className="text-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500 mx-auto mb-4" />
              <p className="text-gray-500">Загрузка каталога...</p>
            </div>
          )}

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 mb-6">
              {error}
            </div>
          )}

          {!loading && !error && badges.length === 0 && (
            <div className="text-center py-16">
              <Award size={48} className="mx-auto mb-4 text-gray-600" />
              <p className="text-gray-500">Каталог пока пуст.</p>
            </div>
          )}

          {!loading && !error && badges.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {badges.map((badge) => {
                const isEarned = earned.has(badge.id);
                return (
                  <motion.div
                    key={badge.id}
                    whileHover={{ scale: 1.05 }}
                    className={`relative flex flex-col items-center gap-3 rounded-xl border p-5 shadow-lg transition-all duration-300 cursor-default ${
                      isEarned
                        ? "border-purple-500/60 bg-purple-950/20 shadow-[0_0_15px_rgba(139,92,246,0.2)]"
                        : "border-gray-700/50 bg-gray-900/80"
                    }`}
                  >
                    {isEarned && (
                      <div className="absolute top-2 right-2">
                        <CheckCircle size={16} className="text-green-400" />
                      </div>
                    )}
                    {!isEarned && (
                      <div className="absolute top-2 right-2">
                        <Lock size={14} className="text-gray-600" />
                      </div>
                    )}
                    <span
                      className={`text-4xl drop-shadow-md ${
                        isEarned
                          ? "drop-shadow-[0_0_8px_rgba(168,85,247,0.8)]"
                          : "filter grayscale opacity-60"
                      }`}
                    >
                      {badge.icon}
                    </span>
                    <span
                      className={`text-sm font-cinzel font-bold text-center leading-tight ${
                        isEarned ? "text-purple-200" : "text-gray-400"
                      }`}
                    >
                      {badge.name}
                    </span>
                    <span className="text-[10px] text-center text-gray-500 line-clamp-2">
                      {badge.description}
                    </span>
                    <span className="text-[10px] font-mono text-gray-600 mt-auto border-t border-gray-800 w-full text-center pt-2">
                      {badge.criteria_type}: {badge.criteria_value}
                    </span>
                  </motion.div>
                );
              })}
            </div>
          )}
        </motion.div>
      </main>
    </div>
  );
}
