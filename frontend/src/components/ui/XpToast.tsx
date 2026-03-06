/**
 * XpToast — всплывающее уведомление о полученных XP.
 *
 * Рендерится через React Portal в document.body (не ломает z-index).
 * Анимации через Framer Motion.
 *
 * Props:
 *   data — XpToastData | null (null = скрыт)
 *   onClose — вызывается после клика на тост
 */

"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import type { XpToastData } from "@/hooks/useXpToast";

interface XpToastProps {
  data: XpToastData | null;
  onClose?: () => void;
}

export default function XpToast({ data, onClose }: XpToastProps) {
  // Track portal target (SSR-safe)
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  const showMultiplier =
    data?.classMultiplier !== undefined &&
    Math.round((data.classMultiplier - 1.0) * 100) !== 0;

  const multiplierPct =
    data?.classMultiplier !== undefined
      ? Math.round((data.classMultiplier - 1.0) * 100)
      : 0;

  const toastContent = (
    <AnimatePresence>
      {data && (
        <>
          {/* ── Level-up overlay ── */}
          {data.level_up && (
            <motion.div
              key="levelup"
              className="fixed inset-0 z-[9998] flex items-center justify-center pointer-events-none"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4 }}
            >
              <motion.div
                className="text-center select-none"
                animate={{ scale: [1, 1.12, 1], opacity: [1, 1, 1] }}
                transition={{ duration: 1.2, repeat: 1 }}
              >
                <div className="text-6xl mb-2 drop-shadow-[0_0_30px_rgba(251,191,36,0.9)]">
                  🎉
                </div>
                <div className="font-cinzel font-bold text-3xl text-amber-400 drop-shadow-[0_0_20px_rgba(251,191,36,0.7)] tracking-widest uppercase">
                  Уровень {data.new_level}!
                </div>
              </motion.div>
            </motion.div>
          )}

          {/* ── XP Toast chip ── */}
          <motion.div
            key="xp-toast"
            className="fixed bottom-8 left-1/2 z-[9999] -translate-x-1/2 pointer-events-auto cursor-pointer"
            initial={{ opacity: 0, y: 40, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ type: "spring", damping: 20, stiffness: 300 }}
            onClick={onClose}
          >
            <div className="flex flex-col items-center gap-1.5 bg-gray-900/95 border border-purple-500/60 rounded-2xl px-8 py-4 shadow-[0_0_30px_rgba(168,85,247,0.4)] backdrop-blur-sm">
              {/* XP amount */}
              <div className="flex items-center gap-2">
                <motion.div
                  animate={{ rotate: [0, 20, -20, 0] }}
                  transition={{ duration: 0.6, delay: 0.1 }}
                >
                  <Sparkles size={22} className="text-purple-400" />
                </motion.div>
                <span className="font-cinzel font-bold text-2xl text-purple-300 tracking-wide">
                  +{data.xp_gained} XP
                </span>
              </div>

              {/* Class multiplier row */}
              {showMultiplier && (
                <div
                  className="text-sm font-mono font-semibold"
                  style={{ color: data.classColor ?? "#a78bfa" }}
                >
                  ×{data.classMultiplier?.toFixed(1)} (бонус класса{" "}
                  {multiplierPct > 0 ? `+${multiplierPct}%` : `${multiplierPct}%`})
                </div>
              )}

              {/* Level-up inline hint */}
              {data.level_up && (
                <motion.div
                  className="text-xs font-cinzel text-amber-400 tracking-widest uppercase"
                  animate={{ opacity: [0.7, 1, 0.7] }}
                  transition={{ duration: 1.2, repeat: Infinity }}
                >
                  🎉 Уровень {data.new_level}!
                </motion.div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );

  return createPortal(toastContent, document.body);
}
