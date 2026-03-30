"use client";

import { motion } from "@/lib/motion";
import QuestBudgetGuidance from "./QuestBudgetGuidance";
import type { UserGrade } from "@/lib/api";

import { safeParseMoney } from "@/lib/money";

export type WizardStep =
  | "problem"
  | "scope"
  | "budget"
  | "talent"
  | "review";

interface SidebarProps {
  currentStep: WizardStep;
  formData: {
    title: string;
    description: string;
    skills: string[];
    budget: string;
    currency: string;
    required_grade: UserGrade;
    xp_reward: string;
    is_urgent: boolean;
    deadline: string;
    required_portfolio: boolean;
  };
}

const STEP_TIPS: Record<WizardStep, { title: string; tips: string[] }> = {
  problem: {
    title: "Опишите проблему",
    tips: [
      "Начните с того, что должно произойти в результате",
      "Чёткий заголовок привлечёт больше подходящих откликов",
      "Описание от 100 символов увеличивает конверсию откликов на 40%",
    ],
  },
  scope: {
    title: "Навыки и Поставки",
    tips: [
      "Укажите 3-5 ключевых навыков для лучшей подборки",
      "Перечислите конкретные результаты (артефакты): что именно вы получите",
      "Требование портфолио помогает отсечь неподходящих кандидатов",
    ],
  },
  budget: {
    title: "Бюджет и Сроки",
    tips: [
      "Адекватный бюджет привлекает сильных специалистов",
      "Дедлайн помогает фрилансерам планировать работу",
      "Пометка «срочно» поднимает квест в ленте",
    ],
  },
  talent: {
    title: "Требования к Исполнителю",
    tips: [
      "Минимальный ранг фильтрует исполнителей по опыту",
      "Senior-задачи получают меньше, но более качественных откликов",
      "Уточните особые условия, если есть",
    ],
  },
  review: {
    title: "Финальная Проверка",
    tips: [
      "Проверьте все поля перед публикацией",
      "Черновик можно отредактировать позже",
      "После публикации квест сразу появится на доске",
    ],
  },
};

export default function QuestCreationSidebar({ currentStep, formData }: SidebarProps) {
  const stepTips = STEP_TIPS[currentStep];

  return (
    <motion.aside
      key={currentStep}
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-4"
    >
      {/* Contextual tips */}
      <div className="p-4 bg-gray-900/60 border border-gray-800 rounded-xl">
        <h3 className="text-sm font-cinzel font-bold text-amber-500 mb-3 flex items-center gap-2">
          <span className="text-base">💡</span> {stepTips.title}
        </h3>
        <ul className="space-y-2">
          {stepTips.tips.map((tip, i) => (
            <li key={i} className="text-xs text-gray-400 font-inter flex gap-2">
              <span className="text-purple-500 mt-0.5 shrink-0">▸</span>
              <span>{tip}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Budget guidance on budget step */}
      {currentStep === "budget" && (
        <QuestBudgetGuidance
          budget={formData.budget}
          currency={formData.currency}
          grade={formData.required_grade}
        />
      )}

      {/* Completeness check — decorative status indicator, not interactive */}
      <div className="p-4 bg-gray-900/40 border border-gray-800/60 rounded-xl" aria-hidden="true">
        <h3 className="text-xs font-mono uppercase tracking-widest text-gray-500 mb-3">
          Готовность квеста
        </h3>
        <div className="space-y-2">
          <CheckItem done={formData.title.trim().length >= 5} label="Заголовок" />
          <CheckItem done={formData.description.trim().length >= 20} label="Описание" />
          <CheckItem done={formData.skills.length >= 1} label="Навыки" />
          <CheckItem done={!!formData.budget && (safeParseMoney(formData.budget) ?? 0) >= 100} label="Бюджет" />
          <CheckItem done={!!formData.required_grade} label="Ранг" />
        </div>
      </div>
    </motion.aside>
  );
}

function CheckItem({ done, label }: { done: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <span className={done ? "text-emerald-500" : "text-gray-600"}>
        {done ? "✓" : "○"}
      </span>
      <span className={done ? "text-gray-300" : "text-gray-600"}>{label}</span>
    </div>
  );
}
