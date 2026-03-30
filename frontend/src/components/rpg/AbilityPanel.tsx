/**
 * AbilityPanel — UI для активации RPG-абилок класса
 */

"use client";

import React, { useCallback, useEffect, useState } from "react";
import { motion } from "@/lib/motion";
import { AbilityInfo, activateAbility, getAbilities } from "@/lib/api";
import { Zap, Clock, Lock, CheckCircle, Sparkles } from "lucide-react";

// Human-readable effect labels
const EFFECT_LABELS: Record<string, (v: number | boolean) => string> = {
  xp_all_bonus:        (v) => `+${Math.round((v as number) * 100)}% XP за все квесты`,
  xp_urgent_bonus:     (v) => `+${Math.round((v as number) * 100)}% XP за срочные квесты`,
  first_apply_bonus:   (v) => `+${Math.round((v as number) * 100)}% XP за быстрый отклик`,
  stale_bonus:         (v) => `+${Math.round((v as number) * 100)}% XP за застоявшиеся квесты`,
  ontime_bonus:        (v) => `+${Math.round((v as number) * 100)}% XP за досрочную сдачу`,
  high_budget_bonus:   (v) => `+${Math.round((v as number) * 100)}% XP за высокобюджетные`,
  analytics_bonus:     (v) => `+${Math.round((v as number) * 100)}% class XP`,
  burnout_immune:      () => "Иммунитет к штрафам Burnout",
  cancel_xp_protect:   () => "Защита XP при отмене квеста",
  deadline_penalty_reduce: (v) => `−${Math.round((v as number) * 100)}% штраф за дедлайн`,
  urgent_payout_bonus: (v) => `+${Math.round((v as number) * 100)}% к выплате за срочный квест`,
};

function formatTimer(iso: string | null): string {
  if (!iso) return "";
  const diff = new Date(iso).getTime() - Date.now();
  if (diff <= 0) return "Завершено";
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 0) return `${h}ч ${m}м`;
  return `${m}м`;
}

function AbilityCard({
  ability,
  onActivate,
  isActivating,
}: {
  ability: AbilityInfo;
  onActivate: (id: string) => void;
  isActivating: boolean;
}) {
  const [timer, setTimer] = useState(() =>
    ability.is_active ? formatTimer(ability.active_until) :
    ability.is_on_cooldown ? formatTimer(ability.cooldown_until) : ""
  );

  useEffect(() => {
    if (!ability.is_active && !ability.is_on_cooldown) return;
    const end = ability.is_active ? ability.active_until : ability.cooldown_until;
    const id = setInterval(() => setTimer(formatTimer(end)), 15000);
    return () => clearInterval(id);
  }, [ability.is_active, ability.is_on_cooldown, ability.active_until, ability.cooldown_until]);

  const canActivate = ability.is_unlocked && !ability.is_active && !ability.is_on_cooldown;

  const statusColor = ability.is_active
    ? "border-emerald-500/40 bg-emerald-950/30"
    : ability.is_on_cooldown
    ? "border-orange-500/30 bg-orange-950/20"
    : !ability.is_unlocked
    ? "border-gray-700/40 bg-gray-900/40 opacity-60"
    : "border-amber-500/30 bg-gray-900/50";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-xl border p-4 transition-all ${statusColor}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{ability.icon}</span>
          <div>
            <p className="font-cinzel font-bold text-sm text-gray-100">{ability.name_ru}</p>
            <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">{ability.name}</p>
          </div>
        </div>

        {/* Status badge */}
        {ability.is_active && (
          <span className="flex items-center gap-1 text-xs text-emerald-400 font-cinzel font-bold">
            <CheckCircle className="w-3.5 h-3.5" />
            Активна · {timer}
          </span>
        )}
        {ability.is_on_cooldown && (
          <span className="flex items-center gap-1 text-xs text-orange-400 font-cinzel">
            <Clock className="w-3.5 h-3.5" />
            КД · {timer}
          </span>
        )}
        {!ability.is_unlocked && (
          <span className="flex items-center gap-1 text-xs text-gray-500 font-cinzel">
            <Lock className="w-3.5 h-3.5" />
            Ур. {ability.required_class_level}
          </span>
        )}
      </div>

      {/* Description */}
      <p className="text-xs text-gray-400 mb-3 leading-relaxed">{ability.description_ru}</p>

      {/* Effects */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {Object.entries(ability.effects).map(([key, val]) => {
          const label = EFFECT_LABELS[key]?.(val);
          if (!label) return null;
          return (
            <span
              key={key}
              className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/25 text-amber-300 text-[10px] font-mono"
            >
              <Sparkles className="w-2.5 h-2.5" />
              {label}
            </span>
          );
        })}
      </div>

      {/* Meta row */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-3 text-[10px] text-gray-500">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            Длит. {ability.duration_hours}ч
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-orange-500/70" />
            КД {ability.cooldown_hours}ч
          </span>
          {ability.times_used > 0 && (
            <span className="text-gray-600">Использована {ability.times_used}×</span>
          )}
        </div>

        {canActivate && (
          <button
            onClick={() => onActivate(ability.ability_id)}
            disabled={isActivating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600/70 hover:bg-amber-500/80 text-white text-xs font-cinzel font-bold tracking-wide transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Zap className="w-3.5 h-3.5" />
            {isActivating ? "..." : "Активировать"}
          </button>
        )}
      </div>
    </motion.div>
  );
}

interface AbilityPanelProps {
  /** Pre-loaded abilities list. If omitted, the panel fetches them itself. */
  initialAbilities?: AbilityInfo[];
  /** Called after each successful activation with the updated ability. */
  onActivated?: (ability: AbilityInfo) => void;
}

export default function AbilityPanel({ initialAbilities, onActivated }: AbilityPanelProps) {
  const [abilities, setAbilities] = useState<AbilityInfo[]>(initialAbilities ?? []);
  const [loading, setLoading] = useState(!initialAbilities);
  const [error, setError] = useState("");
  const [activatingId, setActivatingId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => {
    if (initialAbilities) return;
    setLoading(true);
    getAbilities()
      .then(setAbilities)
      .catch((e) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false));
  }, [initialAbilities]);

  const handleActivate = useCallback(async (abilityId: string) => {
    setActivatingId(abilityId);
    try {
      const res = await activateAbility(abilityId);
      // Refresh the specific ability in state
      setAbilities((prev) =>
        prev.map((a) => (a.ability_id === abilityId ? res.ability : a))
      );
      setToast({ msg: `${res.ability.name_ru} активирована!`, ok: true });
      onActivated?.(res.ability);
    } catch (e: unknown) {
      setToast({ msg: e instanceof Error ? e.message : "Ошибка", ok: false });
    } finally {
      setActivatingId(null);
      setTimeout(() => setToast(null), 3500);
    }
  }, [onActivated]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return <p className="text-red-400 text-sm text-center py-4">{error}</p>;
  }

  if (!abilities.length) {
    return (
      <p className="text-gray-500 text-sm text-center py-6">
        Абилки для вашего класса не найдены
      </p>
    );
  }

  const activeCount = abilities.filter((a) => a.is_active).length;

  return (
    <div className="space-y-4">
      {/* Panel header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-cinzel font-bold text-gray-300 uppercase tracking-wider">
          Абилки класса
        </h3>
        {activeCount > 0 && (
          <span className="flex items-center gap-1 text-xs text-emerald-400 font-cinzel">
            <Zap className="w-3.5 h-3.5" />
            {activeCount} активна
          </span>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className={`px-3 py-2 rounded-lg text-sm font-medium text-center ${
            toast.ok
              ? "bg-emerald-900/60 border border-emerald-500/30 text-emerald-300"
              : "bg-red-900/60 border border-red-500/30 text-red-300"
          }`}
        >
          {toast.msg}
        </motion.div>
      )}

      {/* Ability cards */}
      <div className="space-y-3">
        {abilities.map((ability) => (
          <AbilityCard
            key={ability.ability_id}
            ability={ability}
            onActivate={handleActivate}
            isActivating={activatingId === ability.ability_id}
          />
        ))}
      </div>
    </div>
  );
}

/** Compact active-effects summary for use on quest pages etc. */
export function ActiveAbilityBadge({ abilities }: { abilities: AbilityInfo[] }) {
  const activeAbilities = abilities.filter((a) => a.is_active);
  if (!activeAbilities.length) return null;

  const totalXpBonus = activeAbilities.reduce((sum, a) => {
    const bonus = a.effects["xp_all_bonus"];
    return sum + (typeof bonus === "number" ? bonus : 0);
  }, 0);

  return (
    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-300 text-xs font-cinzel font-bold">
      <Zap className="w-3.5 h-3.5" />
      {activeAbilities.length > 1
        ? `${activeAbilities.length} абилки активны`
        : activeAbilities[0].name_ru}
      {totalXpBonus > 0 && (
        <span className="ml-1 text-amber-400">+{Math.round(totalXpBonus * 100)}% XP</span>
      )}
    </div>
  );
}
