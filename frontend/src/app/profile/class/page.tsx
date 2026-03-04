/**
 * Панель прогрессии класса — перки, способности, XP
 *
 * Доступна по /profile/class для авторизованных фрилансеров с выбранным классом.
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import ClassBadge from "@/components/rpg/ClassBadge";
import PerkTree from "@/components/rpg/PerkTree";
import RageMode from "@/components/rpg/RageMode";
import {
  getMyClass,
  getPerkTree,
  getAbilities,
} from "@/lib/api";
import type { UserClassInfo, PerkTreeResponse, AbilityInfo } from "@/lib/api";

export default function ClassDashboardPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [classInfo, setClassInfo] = useState<UserClassInfo | null>(null);
  const [perkTree, setPerkTree] = useState<PerkTreeResponse | null>(null);
  const [abilities, setAbilities] = useState<AbilityInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/auth/login");
  }, [isAuthenticated, authLoading, router]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ci, tree, abs] = await Promise.all([
        getMyClass(),
        getPerkTree(),
        getAbilities(),
      ]);
      setClassInfo(ci);
      setPerkTree(tree);
      setAbilities(abs);
    } catch (err: unknown) {
      if (err instanceof Error && err.message.includes("404")) {
        // No class selected — redirect to profile
        router.push("/profile");
        return;
      }
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (isAuthenticated) loadData();
  }, [isAuthenticated, loadData]);

  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-950 to-gray-900 text-white">
        <Header />
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-pulse text-gray-400">Загрузка класса...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-950 to-gray-900 text-white">
        <Header />
        <div className="max-w-2xl mx-auto p-8 text-center">
          <p className="text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  if (!classInfo) return null;

  const xpPercent =
    classInfo.class_xp_to_next > 0
      ? Math.min(
          100,
          ((classInfo.class_xp - 0) /
            (classInfo.class_xp + classInfo.class_xp_to_next)) *
            100,
        )
      : 100;

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-950 to-gray-900 text-white">
      <Header />

      <main className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        {/* ── Class header ── */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-6"
        >
          <ClassBadge classInfo={classInfo} size="lg" />
          <div className="flex-1 space-y-2">
            {/* XP bar */}
            <div className="flex items-center justify-between text-xs text-gray-400">
              <span>
                Класс XP: {classInfo.class_xp}
              </span>
              <span>{classInfo.class_xp_to_next} до сл. уровня</span>
            </div>
            <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: classInfo.color }}
                initial={{ width: 0 }}
                animate={{ width: `${xpPercent}%` }}
                transition={{ duration: 0.8 }}
              />
            </div>

            {/* Quick stats */}
            <div className="flex gap-4 text-xs text-gray-500">
              <span>🗡️ Квестов: {classInfo.quests_completed_as_class}</span>
              <span>🔥 Серия: {classInfo.consecutive_quests}</span>
              {classInfo.is_burnout && (
                <span className="text-orange-400">⚠️ Выгорание активно</span>
              )}
              {classInfo.rage_active && (
                <span className="text-red-400 font-bold animate-pulse">
                  💀 РЕЖИМ ЯРОСТИ
                </span>
              )}
            </div>
          </div>
        </motion.section>

        {/* ── Abilities (Rage Mode) ── */}
        {abilities.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <h2 className="font-cinzel text-lg text-white mb-3">
              ⚡ Способности
            </h2>
            <div className="space-y-3">
              {abilities.map((a) => (
                <RageMode
                  key={a.ability_id}
                  ability={a}
                  onActivated={(updated) => {
                    setAbilities((prev) =>
                      prev.map((ab) =>
                        ab.ability_id === updated.ability_id ? updated : ab,
                      ),
                    );
                    loadData(); // refresh class info (rage status)
                  }}
                />
              ))}
            </div>
          </motion.section>
        )}

        {/* ── Perk Tree ── */}
        {perkTree && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="border border-gray-800 rounded-xl bg-gray-900/50 p-6"
          >
            <PerkTree
              tree={perkTree}
              onPerkUnlocked={(updated) => {
                setPerkTree(updated);
                loadData(); // refresh class info (perk points)
              }}
            />
          </motion.section>
        )}

        {/* ── Bonuses summary ── */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="grid grid-cols-2 gap-4"
        >
          {/* Active bonuses */}
          <div className="border border-gray-800 rounded-xl bg-gray-900/50 p-4 space-y-2">
            <h3 className="text-sm font-bold text-green-400">✦ Бонусы</h3>
            {classInfo.active_bonuses.map((b) => (
              <div key={b.key} className="text-xs text-gray-300">
                {b.label}
              </div>
            ))}
          </div>
          {/* Weaknesses */}
          <div className="border border-gray-800 rounded-xl bg-gray-900/50 p-4 space-y-2">
            <h3 className="text-sm font-bold text-red-400">✧ Слабости</h3>
            {classInfo.weaknesses.map((b) => (
              <div key={b.key} className="text-xs text-gray-400">
                {b.label}
              </div>
            ))}
          </div>
        </motion.section>

        {/* ── Perk points info ── */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="text-center text-xs text-gray-600 space-y-1"
        >
          <p>
            Очки перков: {classInfo.perk_points_available} доступно из{" "}
            {classInfo.perk_points_total} (потрачено {classInfo.perk_points_spent})
          </p>
          <p>
            Разблокировано перков: {classInfo.unlocked_perks.length}
          </p>
        </motion.section>
      </main>
    </div>
  );
}
