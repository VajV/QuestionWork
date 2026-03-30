"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "@/lib/motion";
import type { AbilityInfo } from "@/lib/api";
import { activateAbility } from "@/lib/api";

interface RageModeProps {
  ability: AbilityInfo;
  onActivated?: (ability: AbilityInfo) => void;
}

function formatTimeLeft(isoDate: string): string {
  const diff = new Date(isoDate).getTime() - Date.now();
  if (diff <= 0) return "Истекло";
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  if (hours > 0) return `${hours}ч ${minutes}м`;
  return `${minutes}м`;
}

export default function RageMode({ ability, onActivated }: RageModeProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeLeft, setTimeLeft] = useState<string>("");

  // Tick timer every 30s for active/cooldown countdowns
  useEffect(() => {
    function tick() {
      if (ability.is_active && ability.active_until) {
        setTimeLeft(formatTimeLeft(ability.active_until));
      } else if (ability.is_on_cooldown && ability.cooldown_until) {
        setTimeLeft(formatTimeLeft(ability.cooldown_until));
      } else {
        setTimeLeft("");
      }
    }
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, [ability]);

  async function handleActivate() {
    setLoading(true);
    setError(null);
    try {
      const res = await activateAbility(ability.ability_id);
      onActivated?.(res.ability);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ошибка активации");
    } finally {
      setLoading(false);
    }
  }

  const canActivate = ability.is_unlocked && !ability.is_active && !ability.is_on_cooldown;

  return (
    <div className="relative overflow-hidden rounded-xl border border-gray-800 bg-gray-900/80">
      {/* Active glow overlay */}
      <AnimatePresence>
        {ability.is_active && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 pointer-events-none"
            style={{
              background: "radial-gradient(ellipse at center, rgba(220,38,38,0.15) 0%, transparent 70%)",
            }}
          />
        )}
      </AnimatePresence>

      <div className="relative p-4 space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <motion.span
              className="text-3xl"
              animate={ability.is_active ? { scale: [1, 1.15, 1] } : {}}
              transition={{ repeat: Infinity, duration: 1.5 }}
            >
              {ability.icon}
            </motion.span>
            <div>
              <h4 className="font-cinzel font-bold text-white">{ability.name_ru}</h4>
              <p className="text-xs text-gray-400">
                {ability.duration_hours}ч действие · {ability.cooldown_hours}ч перезарядка
              </p>
            </div>
          </div>

          {/* Status badge */}
          {ability.is_active && (
            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-600/30 text-red-400 border border-red-600/50 animate-pulse">
              АКТИВЕН — {timeLeft}
            </span>
          )}
          {ability.is_on_cooldown && !ability.is_active && (
            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-gray-700/50 text-gray-400 border border-gray-600">
              ⏳ {timeLeft}
            </span>
          )}
        </div>

        {/* Description */}
        <p className="text-sm text-gray-300">{ability.description_ru}</p>

        {/* Effects tags */}
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(ability.effects).map(([key, val]) => (
            <span
              key={key}
              className="text-[10px] px-2 py-0.5 rounded-full border border-red-800/50 bg-red-900/20 text-red-300"
            >
              {key === "xp_all_bonus" && `+${Number(val) * 100}% XP`}
              {key === "burnout_immune" && val === true && "🛡️ Иммунитет к выгоранию"}
              {key === "post_rage_burnout_hours" && `⚠️ ${val}ч выгорание после`}
            </span>
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">
            Использовано: {ability.times_used} раз
          </span>

          <motion.button
            className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${
              canActivate
                ? "bg-red-600 text-white hover:bg-red-500 shadow-lg shadow-red-600/25"
                : "bg-gray-800 text-gray-500 cursor-not-allowed"
            }`}
            whileHover={canActivate ? { scale: 1.05 } : {}}
            whileTap={canActivate ? { scale: 0.95 } : {}}
            onClick={handleActivate}
            disabled={!canActivate || loading}
          >
            {loading ? "..." : ability.is_active ? "Активен" : !ability.is_unlocked ? `Ур. ${ability.required_class_level}` : ability.is_on_cooldown ? "Перезарядка" : "💀 Активировать"}
          </motion.button>
        </div>

        {/* Error */}
        {error && (
          <div className="text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-2 py-1">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
