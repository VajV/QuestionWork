"use client";

import { motion, AnimatePresence } from "@/lib/motion";
import type { UserGrade } from "@/lib/api";
import { safeParseMoney } from "@/lib/money";

interface BudgetGuidanceProps {
  budget: string;
  currency: string;
  grade: UserGrade;
}

const GRADE_BUDGET_HINTS: Record<UserGrade, { min: number; typical: string; note: string }> = {
  novice:  { min: 100,   typical: "500 – 3 000",    note: "Простые задачи, обычно до 3000 ₽" },
  junior:  { min: 1000,  typical: "3 000 – 15 000",  note: "Стандартные проекты, чаще 3-15 тыс. ₽" },
  middle:  { min: 5000,  typical: "15 000 – 80 000",  note: "Сложные задачи, обычно 15-80 тыс. ₽" },
  senior:  { min: 15000, typical: "50 000 – 500 000", note: "Экспертные проекты, от 50 тыс. ₽" },
};

export default function QuestBudgetGuidance({ budget, currency, grade }: BudgetGuidanceProps) {
  const hint = GRADE_BUDGET_HINTS[grade];
  const budgetNum = safeParseMoney(budget);
  const hasBudget = budgetNum !== null && budgetNum > 0;

  const isLow = hasBudget && budgetNum < hint.min;
  const suggestedXp = hasBudget ? Math.min(500, Math.max(10, Math.round(budgetNum * 0.1))) : null;

  return (
    <div className="space-y-3">
      {/* Grade-based typical range */}
      <div className="p-3 bg-gray-900/60 border border-gray-800 rounded-lg">
        <p className="text-xs font-mono uppercase tracking-widest text-gray-500 mb-1">
          Типичный бюджет для {grade}
        </p>
        <p className="text-sm text-amber-400 font-mono font-bold">{hint.typical} {currency}</p>
        <p className="text-xs text-gray-500 mt-1">{hint.note}</p>
      </div>

      {/* Low budget warning */}
      <AnimatePresence>
        {isLow && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="p-3 bg-amber-950/30 border border-amber-900/50 rounded-lg"
          >
            <p className="text-xs text-amber-400 font-mono">
              ⚠️ Бюджет ниже типичного для ранга {grade}. Это может снизить количество откликов.
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* XP estimate */}
      <AnimatePresence>
        {suggestedXp && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="p-3 bg-purple-950/20 border border-purple-900/40 rounded-lg"
          >
            <p className="text-xs text-gray-500 font-mono">
              Ожидаемый опыт: <span className="text-purple-400 font-bold">{suggestedXp} XP</span>
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Response expectations */}
      <div className="p-3 bg-gray-900/40 border border-gray-800/50 rounded-lg">
        <p className="text-xs font-mono uppercase tracking-widest text-gray-500 mb-1">Ожидания по откликам</p>
        <ul className="text-xs text-gray-400 space-y-1 font-inter">
          <li>• Средний отклик — 2-6 часов</li>
          <li>• Больше навыков → точнее подборка специалистов</li>
          <li>• Портфолио ускоряет оценку кандидатов</li>
        </ul>
      </div>
    </div>
  );
}
