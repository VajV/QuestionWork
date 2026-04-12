"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getWeeklyChallenges, WeeklyChallenge } from "@/lib/api";
import { isApiError } from "@/lib/api";

function ChallengeRow({ ch }: { ch: WeeklyChallenge }) {
  const pct = Math.min(100, Math.round((ch.current_value / ch.target_value) * 100));

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-sm">
        <span className={ch.completed ? "text-green-400 font-semibold" : "text-white/80"}>
          {ch.completed ? "✓ " : ""}{ch.title}
        </span>
        <span className="text-white/50 text-xs tabular-nums">
          {ch.current_value}/{ch.target_value}
          {ch.completed && (
            <span className="ml-1 text-yellow-400">+{ch.xp_reward} XP</span>
          )}
        </span>
      </div>
      <div className="relative h-1.5 rounded-full bg-white/10 overflow-hidden">
        <motion.div
          className={`absolute inset-y-0 left-0 rounded-full ${ch.completed ? "bg-green-500" : "bg-indigo-500"}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
      <p className="text-xs text-white/40">{ch.description}</p>
    </div>
  );
}

interface Props {
  className?: string;
}

export function WeeklyChallengesWidget({ className = "" }: Props) {
  const [challenges, setChallenges] = useState<WeeklyChallenge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    getWeeklyChallenges()
      .then((data) => { if (mounted) { setChallenges(data); setLoading(false); } })
      .catch((err) => {
        if (!mounted) return;
        setError(isApiError(err) ? (err.detail ?? err.message) : "Ошибка загрузки");
        setLoading(false);
      });
    return () => { mounted = false; };
  }, []);

  const completed = challenges.filter((c) => c.completed).length;

  return (
    <div className={`rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-4 ${className}`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-between w-full mb-3"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">🏆</span>
          <span className="font-semibold text-white">Недельные вызовы</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-white/50">
          {!loading && <span className="text-green-400">{completed}/{challenges.length}</span>}
          <span>{open ? "▲" : "▼"}</span>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            {loading && (
              <div className="space-y-3">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="h-10 rounded bg-white/5 animate-pulse" />
                ))}
              </div>
            )}
            {error && <p className="text-red-400 text-sm">{error}</p>}
            {!loading && !error && challenges.length === 0 && (
              <p className="text-white/40 text-sm text-center py-2">Нет вызовов на эту неделю</p>
            )}
            {!loading && !error && (
              <div className="space-y-4">
                {challenges.map((ch) => (
                  <ChallengeRow key={ch.id} ch={ch} />
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
