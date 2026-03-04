"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { PerkInfo, PerkTreeResponse } from "@/lib/api";
import { unlockPerk } from "@/lib/api";

interface PerkTreeProps {
  tree: PerkTreeResponse;
  onPerkUnlocked?: (tree: PerkTreeResponse) => void;
}

const TIER_LABELS: Record<number, string> = {
  1: "Tier I",
  2: "Tier II",
  3: "Tier III",
};

function PerkNode({
  perk,
  onUnlock,
  isLoading,
}: {
  perk: PerkInfo;
  onUnlock: (perkId: string) => void;
  isLoading: boolean;
}) {
  const [showTooltip, setShowTooltip] = useState(false);

  const borderColor = perk.is_unlocked
    ? "#22c55e"
    : perk.can_unlock
      ? "#eab308"
      : "#4b5563";
  const bgOpacity = perk.is_unlocked ? "20" : perk.can_unlock ? "10" : "05";

  return (
    <div className="relative">
      <motion.button
        className="relative w-20 h-20 rounded-xl border-2 flex flex-col items-center justify-center gap-0.5 transition-colors"
        style={{
          borderColor,
          backgroundColor: `${borderColor}${bgOpacity}`,
          boxShadow: perk.is_unlocked ? `0 0 16px ${borderColor}40` : "none",
        }}
        whileHover={{ scale: 1.08 }}
        whileTap={perk.can_unlock ? { scale: 0.95 } : {}}
        onClick={() => perk.can_unlock && !isLoading && onUnlock(perk.perk_id)}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        disabled={!perk.can_unlock || isLoading}
      >
        <span className="text-2xl">{perk.icon}</span>
        <span className="text-[10px] text-gray-300 font-medium leading-tight text-center px-1 truncate w-full">
          {perk.name_ru.split(" ")[0]}
        </span>
        {perk.is_unlocked && (
          <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-green-500 flex items-center justify-center text-[10px]">
            ✓
          </div>
        )}
        {perk.can_unlock && !perk.is_unlocked && (
          <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-yellow-500 animate-pulse" />
        )}
      </motion.button>

      {/* Tooltip */}
      <AnimatePresence>
        {showTooltip && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 5 }}
            className="absolute z-50 left-1/2 -translate-x-1/2 bottom-full mb-2 w-56 p-3 rounded-lg border border-gray-700 bg-gray-900/95 backdrop-blur shadow-xl"
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">{perk.icon}</span>
              <span className="font-bold text-sm text-white">{perk.name_ru}</span>
            </div>
            <p className="text-xs text-gray-300 mb-2">{perk.description_ru}</p>
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-gray-500">
                Цена: {perk.perk_point_cost} 🔮 | Ур. {perk.required_class_level}
              </span>
              {perk.lock_reason && !perk.is_unlocked && (
                <span className="text-red-400">{perk.lock_reason}</span>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function PerkTree({ tree, onPerkUnlocked }: PerkTreeProps) {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const tiers = [1, 2, 3];
  const perksByTier = tiers.map((t) => tree.perks.filter((p) => p.tier === t));

  async function handleUnlock(perkId: string) {
    setLoading(perkId);
    setError(null);
    try {
      const res = await unlockPerk(perkId);
      // Rebuild tree with updated perk
      const updatedPerks = tree.perks.map((p) =>
        p.perk_id === perkId ? res.perk : p,
      );
      onPerkUnlocked?.({
        ...tree,
        perks: updatedPerks,
        perk_points_spent: tree.perk_points_total - res.perk_points_available,
        perk_points_available: res.perk_points_available,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ошибка разблокировки");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-cinzel text-lg text-white">🔮 Дерево перков</h3>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-yellow-400 font-bold">
            {tree.perk_points_available}
          </span>
          <span className="text-gray-400">/ {tree.perk_points_total} очков</span>
        </div>
      </div>

      {error && (
        <div className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {/* Tiers */}
      <div className="space-y-4">
        {tiers.map((tier, i) => (
          <div key={tier}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                {TIER_LABELS[tier]}
              </span>
              <div className="flex-1 h-px bg-gray-800" />
            </div>
            <div className="flex gap-4 justify-center">
              {perksByTier[i].map((perk) => (
                <PerkNode
                  key={perk.perk_id}
                  perk={perk}
                  onUnlock={handleUnlock}
                  isLoading={loading === perk.perk_id}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
