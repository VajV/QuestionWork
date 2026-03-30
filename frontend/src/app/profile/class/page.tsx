/**
 * Панель прогрессии класса — перки, способности, XP
 *
 * Доступна по /profile/class для авторизованных фрилансеров с выбранным классом.
 */

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "@/lib/motion";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import ClassBadge from "@/components/rpg/ClassBadge";
import PerkTree from "@/components/rpg/PerkTree";
import AbilityPanel from "@/components/rpg/AbilityPanel";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import { useSWRFetch } from "@/hooks/useSWRFetch";
import {
  getMyClass,
  getPerkTree,
  getAbilities,
  getApiErrorMessage,
} from "@/lib/api";
import type { UserClassInfo, PerkTreeResponse, AbilityInfo } from "@/lib/api";

interface ClassDashboardData {
  classInfo: UserClassInfo;
  perkTree: PerkTreeResponse | null;
  abilities: AbilityInfo[];
}

function ClassMetricCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string | number;
  hint: string;
  accent: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/25 p-4 backdrop-blur-sm">
      <div className="text-[11px] uppercase tracking-[0.25em] text-gray-500">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${accent}`}>{value}</div>
      <div className="mt-1 text-xs text-gray-400">{hint}</div>
    </div>
  );
}

export default function ClassDashboardPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push("/auth/login");
  }, [isAuthenticated, authLoading, router]);

  const {
    data,
    error,
    isLoading,
    mutate,
  } = useSWRFetch<ClassDashboardData>(
    !authLoading && isAuthenticated ? (["profile-class-dashboard"] as const) : null,
    async () => {
      const classInfo = await getMyClass();

      if (!classInfo.has_class) {
        return {
          classInfo,
          perkTree: null,
          abilities: [],
        };
      }

      const [perkTree, abilities] = await Promise.all([getPerkTree(), getAbilities()]);

      return {
        classInfo,
        perkTree,
        abilities,
      };
    },
    { revalidateOnFocus: false },
  );

  const classInfo = data?.classInfo ?? null;
  const perkTree = data?.perkTree ?? null;
  const abilities = data?.abilities ?? [];
  const errorMessage = error ? getApiErrorMessage(error, "Ошибка загрузки") : null;

  if (authLoading || (isAuthenticated && isLoading)) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-950 to-gray-900 text-white">
        <Header />
        <div className="flex items-center justify-center h-[60vh]">
          <div className="animate-pulse text-gray-400">Загрузка класса...</div>
        </div>
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-950 to-gray-900 text-white">
        <Header />
        <div className="max-w-2xl mx-auto p-8 text-center">
          <p className="text-red-400 mb-4">{errorMessage}</p>
          <button
            type="button"
            onClick={() => void mutate()}
            className="rounded-lg border border-amber-500/40 px-4 py-2 text-sm text-amber-300 transition-colors hover:bg-amber-900/20"
          >
            Повторить
          </button>
        </div>
      </div>
    );
  }

  if (!classInfo) return null;

  if (!classInfo.has_class) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-950 to-gray-900 text-white">
        <Header />
        <main className="max-w-4xl mx-auto px-4 py-10">
          <section className="rounded-3xl border border-white/10 bg-gradient-to-br from-gray-900 via-gray-950 to-slate-900/80 p-8 text-center">
            <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full border border-white/10 bg-white/5 text-4xl">
              🜁
            </div>
            <p className="mt-6 text-xs uppercase tracking-[0.35em] text-slate-400">Class command</p>
            <h1 className="mt-3 font-cinzel text-4xl text-white">Класс еще не выбран</h1>
            <p className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-gray-400">
              Эта панель активируется после выбора архетипа. Сначала откройте профиль и выберите класс, затем здесь появятся перки, способности и прогрессия.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <button
                type="button"
                onClick={() => router.push("/profile")}
                className="rounded-xl border border-white/10 px-5 py-3 text-sm text-gray-300 transition-colors hover:border-amber-500/40 hover:text-amber-200"
              >
                Открыть профиль
              </button>
              <button
                type="button"
                onClick={() => void mutate()}
                className="rounded-xl border border-slate-500/30 bg-slate-500/10 px-5 py-3 text-sm text-slate-200 transition-colors hover:bg-slate-500/20"
              >
                Обновить состояние
              </button>
            </div>
          </section>
        </main>
      </div>
    );
  }

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

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        <GuildStatusStrip
          mode="class"
          eyebrow="Class command"
          title="Тактический слой прогрессии вашего архетипа"
          description="Здесь виден не только уровень класса, но и режим его состояния: серия, unlocked perks, давление выгорания и активные способности, которые меняют ваш стиль игры на рынке."
          stats={[
            { label: "Класс lvl", value: classInfo.class_level, note: "глубина ветки", tone: "slate" },
            { label: "Перки", value: classInfo.unlocked_perks.length, note: "уже открыто", tone: "purple" },
            { label: "Серия", value: classInfo.consecutive_quests, note: "непрерывный темп", tone: "amber" },
            { label: "Способности", value: abilities.length, note: "активный арсенал", tone: "cyan" },
          ]}
          signals={[
            { label: classInfo.name_ru, tone: "red" },
            { label: classInfo.rage_active ? "Rage mode online" : "Rage mode offline", tone: classInfo.rage_active ? "red" : "slate" },
            { label: classInfo.is_burnout ? "Есть риск burnout" : "Состояние стабильно", tone: classInfo.is_burnout ? "amber" : "emerald" },
          ]}
        />

        {/* ── Class header ── */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-3xl border border-white/10 bg-gradient-to-br from-gray-900 via-gray-950 to-red-950/20 p-6 md:p-8"
        >
          <div className="flex w-full flex-col gap-8 lg:flex-row lg:items-center">
            <ClassBadge classInfo={classInfo} size="lg" />
            <div className="flex-1 space-y-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-xs uppercase tracking-[0.3em] text-amber-400/80">Class Command</div>
                  <h1 className="mt-2 text-4xl font-cinzel font-bold text-white">{classInfo.name_ru}</h1>
                  <p className="mt-2 max-w-2xl text-sm leading-relaxed text-gray-400">
                    Управляйте бонусами класса, активными способностями и темпом прогрессии. Это ваш tactical screen для роста и контроля риска.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => router.push("/profile")}
                  className="rounded-xl border border-white/10 px-4 py-2 text-sm text-gray-300 transition-colors hover:border-amber-500/40 hover:text-amber-200"
                >
                  ← Вернуться в профиль
                </button>
              </div>

              {/* XP bar */}
              <div>
                <div className="mb-2 flex items-center justify-between text-xs text-gray-400">
                  <span>Класс XP: {classInfo.class_xp}</span>
                  <span>{classInfo.class_xp_to_next} до следующего уровня</span>
                </div>
                <div className="h-3 rounded-full bg-gray-800 overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ backgroundColor: classInfo.color }}
                    initial={{ width: 0 }}
                    animate={{ width: `${xpPercent}%` }}
                    transition={{ duration: 0.8 }}
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-4">
                <ClassMetricCard label="Класс lvl" value={classInfo.class_level} hint="Текущий уровень ветки" accent="text-white" />
                <ClassMetricCard label="Квестов" value={classInfo.quests_completed_as_class} hint="Завершено в этом классе" accent="text-amber-300" />
                <ClassMetricCard label="Серия" value={classInfo.consecutive_quests} hint="Непрерывный ритм без сброса" accent="text-orange-300" />
                <ClassMetricCard label="Перки" value={classInfo.unlocked_perks.length} hint="Уже разблокировано" accent="text-purple-300" />
              </div>

              <div className="flex flex-wrap gap-3 text-xs">
                {classInfo.is_burnout && (
                  <span className="rounded-full border border-orange-500/30 bg-orange-950/20 px-3 py-1 text-orange-300">⚠️ Выгорание активно</span>
                )}
                {classInfo.rage_active && (
                  <span className="rounded-full border border-red-500/30 bg-red-950/20 px-3 py-1 font-bold text-red-300">💀 Режим ярости активен</span>
                )}
                {!classInfo.is_burnout && !classInfo.rage_active && (
                  <span className="rounded-full border border-emerald-500/30 bg-emerald-950/20 px-3 py-1 text-emerald-300">✅ Состояние класса стабильное</span>
                )}
              </div>
            </div>
          </div>
        </motion.section>

        {/* ── Abilities ── */}
        {abilities.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <h2 className="font-cinzel text-lg text-white mb-3">
              ⚡ Способности
            </h2>
            <AbilityPanel
              key={abilities.map((ability) => `${ability.ability_id}:${ability.is_active}`).join("|")}
              initialAbilities={abilities}
              onActivated={() => void mutate()}
            />
          </motion.section>
        )}

        {abilities.length === 0 && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="rounded-2xl border border-gray-800 bg-gray-900/50 p-6 text-center"
          >
            <div className="text-4xl">⚡</div>
            <h2 className="mt-3 text-lg font-cinzel text-white">Способности пока не открыты</h2>
            <p className="mt-2 text-sm text-gray-400">Прокачайте класс, чтобы открыть активные умения и tactical abilities.</p>
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
              onPerkUnlocked={() => void mutate()}
            />
          </motion.section>
        )}

        {/* ── Bonuses summary ── */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="grid gap-4 md:grid-cols-2"
        >
          {/* Active bonuses */}
          <div className="border border-gray-800 rounded-xl bg-gray-900/50 p-4 space-y-2">
            <h3 className="text-sm font-bold text-green-400">✦ Бонусы</h3>
            {classInfo.active_bonuses.length > 0 ? classInfo.active_bonuses.map((b) => (
              <div key={b.key} className="text-xs text-gray-300">
                {b.label}
              </div>
            )) : <div className="text-xs text-gray-500">Активные бонусы ещё не проявились.</div>}
          </div>
          {/* Weaknesses */}
          <div className="border border-gray-800 rounded-xl bg-gray-900/50 p-4 space-y-2">
            <h3 className="text-sm font-bold text-red-400">✧ Слабости</h3>
            {classInfo.weaknesses.length > 0 ? classInfo.weaknesses.map((b) => (
              <div key={b.key} className="text-xs text-gray-400">
                {b.label}
              </div>
            )) : <div className="text-xs text-gray-500">Явные слабости пока не отображены.</div>}
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
