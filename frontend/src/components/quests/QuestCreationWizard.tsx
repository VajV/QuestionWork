"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "@/lib/motion";
import { createQuest, UserGrade } from "@/lib/api";
import type { ApiError } from "@/lib/api";
import { safeParseMoney } from "@/lib/money";
import Button from "@/components/ui/Button";
import QuestCreationSidebar, { type WizardStep } from "./QuestCreationSidebar";
import RecommendedTalentRail from "@/components/marketplace/RecommendedTalentRail";
import { trackAnalyticsEvent } from "@/lib/analytics";

// ─── Constants ────────────────────────────────────────────────────────────────

const GRADE_OPTIONS: { value: UserGrade; label: string; description: string; icon: string }[] = [
  { value: "novice",  label: "Novice",  description: "Простые задачи, начальный уровень", icon: "🌱" },
  { value: "junior",  label: "Junior",  description: "Стандартные проекты",               icon: "⚡" },
  { value: "middle",  label: "Middle",  description: "Сложные задачи, опыт обязателен",   icon: "🔥" },
  { value: "senior",  label: "Senior",  description: "Экспертный уровень",                icon: "💎" },
];

const CURRENCY_OPTIONS = ["RUB", "USD", "EUR"];

const POPULAR_SKILLS = [
  "JavaScript", "TypeScript", "React", "Next.js", "Vue.js",
  "Python", "FastAPI", "Django", "Node.js", "Go",
  "PostgreSQL", "MongoDB", "Redis", "Docker", "Kubernetes",
  "HTML", "CSS", "Tailwind", "Figma", "UI/UX",
  "iOS", "Android", "Flutter", "React Native",
  "DevOps", "AWS", "Linux", "Git", "CI/CD",
  "Web Scraping", "BeautifulSoup", "Selenium",
  "aiogram", "Telegram Bot", "Google API",
];

const STEPS: { key: WizardStep; label: string; icon: string }[] = [
  { key: "problem",  label: "Проблема",     icon: "📝" },
  { key: "scope",    label: "Навыки",       icon: "🛠️" },
  { key: "budget",   label: "Бюджет",       icon: "💰" },
  { key: "talent",   label: "Требования",   icon: "🎮" },
  { key: "review",   label: "Публикация",   icon: "📜" },
];

const DRAFT_KEY = "qw_quest_draft";

// ─── Form State ───────────────────────────────────────────────────────────────

export interface WizardFormState {
  title: string;
  description: string;
  required_grade: UserGrade;
  skills: string[];
  budget: string;
  currency: string;
  xp_reward: string;
  is_urgent: boolean;
  deadline: string;
  required_portfolio: boolean;
}

const INITIAL_FORM: WizardFormState = {
  title: "",
  description: "",
  required_grade: "novice",
  skills: [],
  budget: "",
  currency: "RUB",
  xp_reward: "",
  is_urgent: false,
  deadline: "",
  required_portfolio: false,
};

// ─── Component ────────────────────────────────────────────────────────────────

interface Props {
  /** Pre-fill form from a template */
  initialData?: Partial<WizardFormState>;
  templateMeta?: { id: string; name?: string };
}

export default function QuestCreationWizard({ initialData, templateMeta }: Props) {
  const router = useRouter();

  // Restore draft from localStorage or use template data
  const [form, setForm] = useState<WizardFormState>(() => {
    if (initialData && Object.keys(initialData).length > 0) {
      return { ...INITIAL_FORM, ...initialData };
    }
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(DRAFT_KEY);
        if (saved) return { ...INITIAL_FORM, ...JSON.parse(saved) };
      } catch { /* ignore corrupt data */ }
    }
    return INITIAL_FORM;
  });

  const [step, setStep] = useState<WizardStep>("problem");
  const [skillInput, setSkillInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [successLabel, setSuccessLabel] = useState("Квест создан!");

  // ─── Draft persistence ──────────────────────────────────────────────────────
  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(form));
    } catch { /* quota exceeded — ignore */ }
  }, [form]);

  const clearDraft = useCallback(() => {
    try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
  }, []);

  // ─── Helpers ────────────────────────────────────────────────────────────────

  const updateField = <K extends keyof WizardFormState>(key: K, value: WizardFormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const addSkill = (skill: string) => {
    const trimmed = skill.trim();
    if (!trimmed || form.skills.includes(trimmed) || form.skills.length >= 20) return;
    updateField("skills", [...form.skills, trimmed]);
    setSkillInput("");
  };

  const removeSkill = (skill: string) =>
    updateField("skills", form.skills.filter((s) => s !== skill));

  const handleSkillKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addSkill(skillInput);
    }
  };

  const suggestedXp = () => {
    const b = safeParseMoney(form.budget);
    if (b === null || b <= 0) return null;
    return Math.min(500, Math.max(10, Math.round(b * 0.1)));
  };

  // ─── Step navigation ───────────────────────────────────────────────────────

  const stepIndex = STEPS.findIndex((s) => s.key === step);

  /** Return a human-readable error for the current step, or null if valid. */
  const validateStep = (): string | null => {
    switch (step) {
      case "problem":
        if (form.title.trim().length < 5)       return "Введите заголовок (мин. 5 символов)";
        if (form.description.trim().length < 20) return "Введите описание (мин. 20 символов)";
        return null;
      case "scope":
        if (form.skills.length < 1)              return "Добавьте хотя бы один навык";
        return null;
      case "budget":
        if (!form.budget || (safeParseMoney(form.budget) ?? 0) < 100) return "Минимальный бюджет — 100";
        return null;
      default:
        return null;
    }
  };

  // // const canAdvance = (): boolean => validateStep() === null;

  const goNext = () => {
    const stepError = validateStep();
    if (stepError) {
      setError(stepError);
      return;
    }
    if (stepIndex < STEPS.length - 1) {
      setError(null);
      setStep(STEPS[stepIndex + 1].key);
    }
  };

  const goPrev = () => {
    if (stepIndex > 0) {
      setError(null);
      setStep(STEPS[stepIndex - 1].key);
    }
  };

  const goToStep = (target: WizardStep) => {
    setError(null);
    setStep(target);
  };

  // ─── Validation ─────────────────────────────────────────────────────────────

  const validate = (): string | null => {
    if (form.title.trim().length < 5)       return "Название должно содержать не менее 5 символов";
    if (form.title.trim().length > 200)     return "Название слишком длинное (макс. 200)";
    if (form.description.trim().length < 20) return "Описание от 20 символов";
    if (form.description.trim().length > 5000) return "Описание макс. 5000 символов";
    const budget = safeParseMoney(form.budget);
    if (budget === null || budget < 100)    return "Минимальный бюджет — 100";
    if (budget > 1_000_000)                 return "Максимальный бюджет — 1 000 000";
    if (form.skills.length === 0)           return "Добавьте хотя бы один навык";
    if (form.xp_reward) {
      const xp = parseInt(form.xp_reward);
      if (isNaN(xp) || xp < 10 || xp > 500) return "XP награда 10–500";
    }
    return null;
  };

  /** Check whether the form has enough data for a server-side draft (backend requires title, description, budget). */
  const canSaveServerDraft = (): boolean => {
    const budget = safeParseMoney(form.budget);
    return (
      form.title.trim().length >= 5 &&
      form.description.trim().length >= 20 &&
      budget !== null && budget >= 100
    );
  };

  // ─── Submit ─────────────────────────────────────────────────────────────────

  const submitQuest = async (status: "draft" | "open") => {
    setError(null);

    if (status === "open") {
      const validationError = validate();
      if (validationError) { setError(validationError); return; }
    }

    // Draft: if not enough data for the backend, save locally with explicit feedback
    if (status === "draft" && !canSaveServerDraft()) {
      try { localStorage.setItem(DRAFT_KEY, JSON.stringify(form)); } catch { /* ignore */ }
      setSuccessLabel("Черновик сохранён локально!");
      setSuccess(true);
      return;
    }

    setLoading(true);
    try {
      const quest = await createQuest({
        title: form.title.trim(),
        description: form.description.trim(),
        required_grade: form.required_grade,
        skills: form.skills,
        budget: Number(form.budget),
        currency: form.currency,
        xp_reward: form.xp_reward ? parseInt(form.xp_reward) : undefined,
        status,
        is_urgent: form.is_urgent || undefined,
        deadline: form.deadline || undefined,
        required_portfolio: form.required_portfolio || undefined,
      });

      if (templateMeta?.id) {
        trackAnalyticsEvent("quest_created_from_template", {
          template_id: templateMeta.id,
          template_name: templateMeta.name ?? null,
          quest_id: quest.id,
          publish_status: status,
        });
      } else {
        trackAnalyticsEvent("quest_created", {
          quest_id: quest.id,
          publish_status: status,
        });
      }

      clearDraft();
      setSuccessLabel(status === "draft" ? "Черновик сохранён!" : "Квест создан!");
      setSuccess(true);
      setTimeout(() => router.push(`/quests/${quest.id}`), 1500);
    } catch (err) {
      let msg = "Не удалось создать квест.";
      const apiError = err as Partial<ApiError>;
      if (typeof apiError.detail === "string" && apiError.detail.trim()) msg = apiError.detail;
      else if (typeof apiError.message === "string" && apiError.message.trim()) msg = apiError.message;
      else if (err instanceof Error) msg = err.message;
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // ─── Success ────────────────────────────────────────────────────────────────

  if (success) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        className="py-12"
      >
        <div className="text-center mb-10">
          <div className="text-7xl mb-6">🎉</div>
          <h2 className="text-3xl font-bold text-white mb-2">{successLabel}</h2>
          <p className="text-gray-400">Перенаправляем на страницу квеста...</p>
        </div>

        {form.skills.length > 0 && (
          <div className="max-w-md mx-auto rounded-xl border border-white/5 bg-white/[0.02] p-6">
            <RecommendedTalentRail
              skills={form.skills}
              limit={3}
              title="Подходящие исполнители для вашего квеста"
            />
          </div>
        )}
      </motion.div>
    );
  }

  const suggested = suggestedXp();

  // ─── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col lg:flex-row gap-6 lg:gap-8">
      {/* Main column */}
      <div className="flex-1 min-w-0">
        {/* Step progress bar */}
        <div className="flex items-center justify-between mb-8 px-2">
          {STEPS.map((s, i) => {
            const isCurrent = s.key === step;
            const isDone = i < stepIndex;
            return (
              <button
                key={s.key}
                type="button"
                onClick={() => goToStep(s.key)}
                aria-label={`Шаг ${i + 1}: ${s.label}`}
                data-step={s.key}
                className="flex flex-col items-center gap-1 group"
              >
                <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold border-2 transition-all ${
                  isCurrent
                    ? "border-amber-500 bg-amber-500/20 text-amber-400 shadow-[0_0_12px_rgba(217,119,6,0.4)]"
                    : isDone
                      ? "border-emerald-600 bg-emerald-900/30 text-emerald-400"
                      : "border-gray-700 bg-gray-900 text-gray-600 group-hover:border-gray-600"
                }`}>
                  {isDone ? "✓" : s.icon}
                </div>
                <span className={`text-[10px] font-mono uppercase tracking-widest hidden sm:block ${
                  isCurrent ? "text-amber-400" : isDone ? "text-emerald-500" : "text-gray-600"
                }`}>
                  {s.label}
                </span>
              </button>
            );
          })}
        </div>

        {/* Error */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mb-6 p-4 bg-red-950/40 border border-red-900/50 rounded font-mono text-red-500 text-sm"
            >
              ⚠️ {error}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Step content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -30 }}
            transition={{ duration: 0.25 }}
          >
            {step === "problem" && (
              <div className="space-y-4">
                {/* Template suggestion banner */}
                {!initialData && (
                  <div className="p-4 bg-purple-950/20 border border-purple-800/40 rounded-xl flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-300 font-inter">Есть готовые шаблоны?</p>
                      <p className="text-xs text-gray-500">Начните с шаблона — заполните квест быстрее</p>
                    </div>
                    <Link href="/quests/templates"
                      className="px-4 py-2 bg-purple-800/50 hover:bg-purple-700/70 border border-purple-700/40 rounded text-sm text-purple-200 font-cinzel whitespace-nowrap transition-colors">
                      📋 Шаблоны
                    </Link>
                  </div>
                )}
                <StepProblem form={form} updateField={updateField} loading={loading} />
              </div>
            )}
            {step === "scope" && (
              <StepScope
                form={form}
                updateField={updateField}
                skillInput={skillInput}
                setSkillInput={setSkillInput}
                addSkill={addSkill}
                removeSkill={removeSkill}
                handleSkillKeyDown={handleSkillKeyDown}
                loading={loading}
              />
            )}
            {step === "budget" && (
              <StepBudget form={form} updateField={updateField} suggested={suggested} loading={loading} />
            )}
            {step === "talent" && (
              <StepTalent form={form} updateField={updateField} loading={loading} />
            )}
            {step === "review" && (
              <StepReview form={form} suggested={suggested} />
            )}
          </motion.div>
        </AnimatePresence>

        {/* Navigation */}
        <div className="flex items-center justify-between mt-8 pt-6 border-t border-gray-800/50">
          <div className="flex gap-3">
            {stepIndex > 0 && (
              <Button type="button" variant="secondary" onClick={goPrev} disabled={loading}
                className="font-cinzel border-gray-700 hover:border-gray-500">
                ← Назад
              </Button>
            )}
          </div>

          <div className="flex gap-3">
            {/* Save draft on any step */}
            <Button type="button" variant="secondary" onClick={() => submitQuest("draft")} disabled={loading}
              className="font-cinzel border-amber-900/50 hover:border-amber-500/50 text-sm">
              📝 Черновик
            </Button>

            {step !== "review" ? (
              <Button type="button" variant="primary" onClick={goNext} disabled={loading}
                className="font-cinzel shadow-[0_0_10px_rgba(217,119,6,0.3)]">
                Далее →
              </Button>
            ) : (
              <Button type="button" variant="primary" onClick={() => submitQuest("open")} disabled={loading}
                className="font-cinzel shadow-[0_0_15px_rgba(217,119,6,0.3)] hover:shadow-[0_0_25px_rgba(217,119,6,0.5)]">
                {loading ? "⏳ Публикуем..." : "📜 Прибить к Доске"}
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-full lg:w-72 shrink-0">
        <QuestCreationSidebar currentStep={step} formData={form} />
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Step sub-components
// ═══════════════════════════════════════════════════════════════════════════════

function StepProblem({ form, updateField, loading }: {
  form: WizardFormState;
  updateField: <K extends keyof WizardFormState>(key: K, value: WizardFormState[K]) => void;
  loading: boolean;
}) {
  return (
    <div className="rpg-card p-6 md:p-8">
      <h2 className="text-xl font-cinzel font-bold mb-2 text-amber-500 flex items-center gap-3 border-b border-amber-900/30 pb-3">
        <span className="grayscale opacity-70">📝</span> Опишите проблему
      </h2>
      <p className="text-sm text-gray-500 mb-6 font-inter">Чёткая постановка задачи — половина успешного результата</p>

      <div className="space-y-6">
        <div>
          <label className="block text-xs font-mono uppercase tracking-widest text-gray-500 mb-2">
            Заголовок <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => updateField("title", e.target.value)}
            maxLength={200}
            placeholder="Например: Разработать REST API для системы заказов"
            className="w-full px-4 py-3 bg-black/50 border border-gray-800 rounded font-inter focus:outline-none focus:border-amber-500 text-gray-200 placeholder-gray-600 transition-colors shadow-inner"
            disabled={loading}
          />
          <div className="flex justify-between mt-2 font-mono">
            <span className="text-xs text-gray-600">Мин. 5 символов</span>
            <span className={`text-xs ${form.title.length > 190 ? "text-amber-500" : "text-gray-600"}`}>
              {form.title.length}/200
            </span>
          </div>
        </div>

        <div>
          <label className="block text-xs font-mono uppercase tracking-widest text-gray-500 mb-2">
            Подробное описание <span className="text-red-500">*</span>
          </label>
          <textarea
            value={form.description}
            onChange={(e) => updateField("description", e.target.value)}
            maxLength={5000}
            rows={8}
            placeholder="Опишите, что нужно сделать, какие результаты ожидаете, контекст проекта..."
            className="w-full px-4 py-3 bg-black/50 border border-gray-800 rounded font-inter focus:outline-none focus:border-amber-500 text-gray-200 placeholder-gray-600 resize-y transition-colors shadow-inner"
            disabled={loading}
          />
          <div className="flex justify-between mt-2 font-mono">
            <span className="text-xs text-gray-600">Мин. 20 символов</span>
            <span className={`text-xs ${form.description.length > 4500 ? "text-amber-500" : "text-gray-600"}`}>
              {form.description.length}/5000
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function StepScope({ form, updateField, skillInput, setSkillInput, addSkill, removeSkill, handleSkillKeyDown, loading }: {
  form: WizardFormState;
  updateField: <K extends keyof WizardFormState>(key: K, value: WizardFormState[K]) => void;
  skillInput: string;
  setSkillInput: (v: string) => void;
  addSkill: (s: string) => void;
  removeSkill: (s: string) => void;
  handleSkillKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  loading: boolean;
}) {
  return (
    <div className="rpg-card p-6 md:p-8">
      <h2 className="text-xl font-cinzel font-bold mb-2 text-gray-100 flex items-center gap-3 border-b border-gray-800 pb-3">
        <span className="grayscale opacity-70">🛠️</span> Навыки и Поставки
        <span className="text-sm font-mono text-gray-500 ml-2">(до 20)</span>
      </h2>
      <p className="text-sm text-gray-500 mb-6 font-inter">Какие технологии нужны исполнителю?</p>

      {/* Selected skills */}
      {form.skills.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6" role="list" aria-label="Выбранные навыки">
          {form.skills.map((skill) => (
            <span key={skill} role="listitem"
              className="flex items-center gap-2 px-3 py-1 bg-purple-950/40 border border-purple-800/60 rounded font-mono text-sm text-purple-200">
              {skill}
              <button type="button" onClick={() => removeSkill(skill)}
                aria-label={`Удалить навык ${skill}`}
                className="text-purple-400 hover:text-red-400 font-bold leading-none">×</button>
            </span>
          ))}
        </div>
      )}

      {/* Manual input */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <input
          type="text"
          id="skill-input"
          value={skillInput}
          onChange={(e) => setSkillInput(e.target.value)}
          onKeyDown={handleSkillKeyDown}
          placeholder="Навык + Enter..."
          aria-label="Добавить навык вручную"
          className="flex-1 px-4 py-3 bg-black/50 border border-gray-800 rounded font-inter focus:outline-none focus:border-purple-500 text-gray-200 placeholder-gray-600 text-sm shadow-inner"
          disabled={loading || form.skills.length >= 20}
        />
        <Button type="button" variant="secondary" onClick={() => addSkill(skillInput)}
          disabled={loading || !skillInput.trim() || form.skills.length >= 20}
          aria-label="Добавить навык"
          className="text-sm px-6 font-cinzel border-purple-900/50 hover:border-purple-500/50">
          + Добавить
        </Button>
      </div>

      {/* Popular skills */}
      <div>
        <p className="text-xs font-mono uppercase tracking-widest text-gray-500 mb-3">Популярные навыки:</p>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Популярные навыки">
          {POPULAR_SKILLS.filter((s) => !form.skills.includes(s)).slice(0, 20).map((skill) => (
            <button key={skill} type="button" onClick={() => addSkill(skill)}
              disabled={loading || form.skills.length >= 20}
              aria-label={`Навык ${skill}`}
              aria-pressed={form.skills.includes(skill)}
              className="px-3 py-1.5 bg-gray-900 border border-gray-800 rounded font-mono text-xs text-gray-400 hover:border-purple-700 hover:text-purple-300 transition-colors disabled:opacity-30">
              + {skill}
            </button>
          ))}
        </div>
      </div>

      {/* Portfolio requirement */}
      <div className="mt-6 pt-4 border-t border-gray-800/50">
        <label className="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" checked={form.required_portfolio}
            onChange={(e) => updateField("required_portfolio", e.target.checked)}
            aria-label="Требуется портфолио"
            className="w-4 h-4 accent-purple-500" />
          <span className="text-sm text-gray-300 font-inter">Требуется портфолио</span>
        </label>
      </div>
    </div>
  );
}

function StepBudget({ form, updateField, suggested, loading }: {
  form: WizardFormState;
  updateField: <K extends keyof WizardFormState>(key: K, value: WizardFormState[K]) => void;
  suggested: number | null;
  loading: boolean;
}) {
  return (
    <div className="rpg-card p-6 md:p-8">
      <h2 className="text-xl font-cinzel font-bold mb-2 text-green-500 flex items-center gap-3 border-b border-green-900/30 pb-3">
        <span className="grayscale opacity-70">💰</span> Бюджет и Сроки
      </h2>
      <p className="text-sm text-gray-500 mb-6 font-inter">Адекватный бюджет привлекает сильных специалистов</p>

      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <div>
            <label htmlFor="budget-input" className="block text-xs font-mono uppercase tracking-widest text-gray-500 mb-2">
              Награда <span className="text-red-500">*</span>
            </label>
            <input type="number" id="budget-input" value={form.budget} onChange={(e) => updateField("budget", e.target.value)}
              placeholder="5000" min="100" max="1000000"
              aria-label="Бюджет"
              className="w-full px-4 py-3 bg-black/50 border border-gray-800 rounded font-mono focus:outline-none focus:border-green-500 text-gray-200 placeholder-gray-600 shadow-inner"
              disabled={loading} />
          </div>
          <div>
            <label htmlFor="currency-select" className="block text-xs font-mono uppercase tracking-widest text-gray-500 mb-2">Валюта</label>
            <select id="currency-select" value={form.currency} onChange={(e) => updateField("currency", e.target.value)}
              aria-label="Валюта"
              className="w-full px-4 py-3 bg-black/50 border border-gray-800 rounded font-mono focus:outline-none focus:border-green-500 text-gray-200 shadow-inner"
              disabled={loading}>
              {CURRENCY_OPTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        {/* XP */}
        <div>
          <label htmlFor="xp-input" className="block text-xs font-mono uppercase tracking-widest text-gray-500 mb-2">
            XP награда <span className="text-gray-600 normal-case tracking-normal ml-2">(10–500, необязательно)</span>
          </label>
          <div className="flex flex-col sm:flex-row gap-3 items-center">
            <input type="number" id="xp-input" value={form.xp_reward} onChange={(e) => updateField("xp_reward", e.target.value)}
              placeholder={suggested !== null ? `Авто: ${suggested} XP` : "150"} min="10" max="500"
              aria-label="XP награда"
              className="w-full sm:flex-1 px-4 py-3 bg-black/50 border border-gray-800 rounded font-mono focus:outline-none focus:border-purple-500 text-gray-200 placeholder-gray-600 shadow-inner"
              disabled={loading} />
            {suggested !== null && !form.xp_reward && (
              <button type="button" onClick={() => updateField("xp_reward", String(suggested))}
                aria-label={`Установить XP награду ${suggested}`}
                className="text-sm font-mono text-purple-400 hover:text-purple-300 bg-purple-950/30 px-3 py-2 rounded border border-purple-800/50 whitespace-nowrap">
                ← {suggested} XP
              </button>
            )}
          </div>
        </div>

        {/* Urgency & deadline */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-2">
          <label className="flex items-center gap-3 cursor-pointer">
            <input type="checkbox" checked={form.is_urgent}
              onChange={(e) => updateField("is_urgent", e.target.checked)}
              aria-label="Срочный квест"
              role="switch"
              aria-checked={form.is_urgent}
              className="w-4 h-4 accent-red-500" />
            <span className="text-sm text-gray-300 font-inter">🔥 Срочный квест</span>
          </label>
          <div>
            <label htmlFor="deadline-input" className="block text-xs font-mono uppercase tracking-widest text-gray-500 mb-2">Дедлайн</label>
            <input type="date" id="deadline-input" value={form.deadline} onChange={(e) => updateField("deadline", e.target.value)}
              aria-label="Дедлайн"
              className="w-full px-4 py-3 bg-black/50 border border-gray-800 rounded font-mono focus:outline-none focus:border-green-500 text-gray-200 shadow-inner"
              disabled={loading} />
          </div>
        </div>

        {/* Budget preview */}
        {form.budget && (safeParseMoney(form.budget) ?? 0) > 0 && (
          <div className="p-4 bg-gray-900/50 border border-gray-800 rounded font-mono">
            <p className="text-xs text-gray-500 uppercase tracking-widest mb-2">Итого за выполнение:</p>
            <div className="flex gap-8 text-base">
              <span className="text-amber-500 font-bold">💰 {(safeParseMoney(form.budget) ?? 0).toLocaleString("ru-RU")} {form.currency}</span>
              <span className="text-purple-400 font-bold">⚡ {form.xp_reward || suggested || "~"} XP</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StepTalent({ form, updateField, loading }: {
  form: WizardFormState;
  updateField: <K extends keyof WizardFormState>(key: K, value: WizardFormState[K]) => void;
  loading: boolean;
}) {
  return (
    <div className="rpg-card p-6 md:p-8">
      <h2 className="text-xl font-cinzel font-bold mb-2 text-purple-400 flex items-center gap-3 border-b border-purple-900/30 pb-3">
        <span className="grayscale opacity-70">🎮</span> Требования к Исполнителю
      </h2>
      <p className="text-sm text-gray-500 mb-6 font-inter">Какой уровень специалиста вам нужен?</p>

      <fieldset>
        <legend className="text-xs font-mono uppercase tracking-widest text-gray-500 mb-3">Требуемый ранг</legend>
        <div className="grid grid-cols-2 gap-4" role="radiogroup" aria-label="Требуемый ранг">
          {GRADE_OPTIONS.map((opt) => {
            const isSelected = form.required_grade === opt.value;
            return (
              <label
                key={opt.value}
                role="radio"
                aria-checked={isSelected}
                aria-label={`${opt.label} — ${opt.description}`}
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); updateField("required_grade", opt.value); } }}
                className={`p-4 rounded border-2 text-left transition-all cursor-pointer ${
                  isSelected
                    ? "border-amber-500 bg-amber-950/20 shadow-[inset_0_0_10px_rgba(217,119,6,0.2)]"
                    : "border-gray-800 bg-black/40 hover:border-gray-600"
                } ${loading ? "opacity-50 pointer-events-none" : ""}`}
              >
                <input
                  type="radio"
                  name="required_grade"
                  value={opt.value}
                  checked={isSelected}
                  onChange={() => updateField("required_grade", opt.value)}
                  disabled={loading}
                  className="sr-only"
                />
                <div className="text-2xl mb-2 opacity-80">{opt.icon}</div>
                <div className="font-cinzel font-bold text-gray-200 text-sm tracking-wider">{opt.label}</div>
                <div className="text-xs text-gray-500 font-inter mt-1">{opt.description}</div>
              </label>
            );
          })}
        </div>
      </fieldset>
    </div>
  );
}

function StepReview({ form, suggested }: { form: WizardFormState; suggested: number | null }) {
  const missing: string[] = [];
  if (form.title.trim().length < 5)       missing.push("Заголовок (мин. 5 символов)");
  if (form.description.trim().length < 20) missing.push("Описание (мин. 20 символов)");
  if (form.skills.length === 0)            missing.push("Навыки (хотя бы один)");
  const budget = safeParseMoney(form.budget);
  if (budget === null || budget < 100)     missing.push("Бюджет (мин. 100)");

  return (
    <div className="rpg-card p-6 md:p-8">
      <h2 className="text-xl font-cinzel font-bold mb-2 text-amber-500 flex items-center gap-3 border-b border-amber-900/30 pb-3">
        <span className="grayscale opacity-70">📜</span> Проверка перед публикацией
      </h2>
      <p className="text-sm text-gray-500 mb-6 font-inter">Убедитесь, что всё заполнено верно</p>

      {missing.length > 0 && (
        <div className="mb-6 p-4 bg-red-950/40 border border-red-900/50 rounded">
          <p className="text-sm font-mono text-red-400 mb-2">⚠️ Не заполнены обязательные поля:</p>
          <ul className="list-disc list-inside text-sm text-red-300 space-y-1">
            {missing.map((m) => <li key={m}>{m}</li>)}
          </ul>
        </div>
      )}

      <div className="space-y-4">
        <ReviewRow label="Заголовок" value={form.title || "—"} />
        <ReviewRow label="Описание" value={form.description ? `${form.description.slice(0, 150)}${form.description.length > 150 ? "..." : ""}` : "—"} />
        <ReviewRow label="Навыки" value={form.skills.length > 0 ? form.skills.join(", ") : "—"} />
        <ReviewRow label="Бюджет" value={form.budget ? `${(safeParseMoney(form.budget) ?? 0).toLocaleString("ru-RU")} ${form.currency}` : "—"} />
        <ReviewRow label="Ранг" value={form.required_grade.toUpperCase()} />
        <ReviewRow label="XP" value={form.xp_reward || (suggested ? `~${suggested} (авто)` : "авто")} />
        {form.is_urgent && <ReviewRow label="Срочность" value="🔥 Срочный" />}
        {form.deadline && <ReviewRow label="Дедлайн" value={form.deadline} />}
        {form.required_portfolio && <ReviewRow label="Портфолио" value="✓ Требуется" />}
      </div>
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-start py-2 border-b border-gray-800/40">
      <span className="text-xs font-mono uppercase tracking-widest text-gray-500 shrink-0 mr-4">{label}</span>
      <span className="text-sm text-gray-300 font-inter text-right">{value}</span>
    </div>
  );
}
