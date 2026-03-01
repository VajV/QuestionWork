/**
 * Quest creation page
 * Only authenticated users (clients) can create quests
 */

"use client";

import { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import { createQuest, UserGrade } from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

const GRADE_OPTIONS: { value: UserGrade; label: string; description: string; icon: string }[] = [
  { value: "novice",  label: "Novice",  description: "Простые задачи, начальный уровень", icon: "🌱" },
  { value: "junior",  label: "Junior",  description: "Стандартные проекты",               icon: "⚡" },
  { value: "middle",  label: "Middle",  description: "Сложные задачи, опыт обязателен",   icon: "🔥" },
  { value: "senior",  label: "Senior",  description: "Экспертный уровень",                icon: "💎" },
];

const CURRENCY_OPTIONS = ["RUB", "USD", "EUR", "USDT"];

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

interface FormState {
  title: string;
  description: string;
  required_grade: UserGrade;
  skills: string[];
  budget: string;
  currency: string;
  xp_reward: string;
}

const INITIAL_FORM: FormState = {
  title: "",
  description: "",
  required_grade: "novice",
  skills: [],
  budget: "",
  currency: "RUB",
  xp_reward: "",
};

export default function CreateQuestPage() {
  const router = useRouter();
  const { isAuthenticated, user, loading: authLoading } = useAuth();

  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [skillInput, setSkillInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [isAuthenticated, authLoading, router]);

  if (authLoading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Загрузка...</p>
        </div>
      </main>
    );
  }

  if (!isAuthenticated) return null;

  // ─── Helpers ────────────────────────────────────────────────────────────────

  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const addSkill = (skill: string) => {
    const trimmed = skill.trim();
    if (!trimmed || form.skills.includes(trimmed) || form.skills.length >= 10) return;
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

  // Suggested XP based on budget
  const suggestedXp = () => {
    const b = parseFloat(form.budget);
    if (isNaN(b) || b <= 0) return null;
    return Math.min(500, Math.max(10, Math.round(b * 0.1)));
  };

  // ─── Validation ─────────────────────────────────────────────────────────────

  const validate = (): string | null => {
    if (form.title.trim().length < 5)
      return "Название должно содержать не менее 5 символов";
    if (form.title.trim().length > 100)
      return "Название слишком длинное (максимум 100 символов)";
    if (form.description.trim().length < 20)
      return "Описание должно содержать не менее 20 символов";
    if (form.description.trim().length > 2000)
      return "Описание слишком длинное (максимум 2000 символов)";
    const budget = parseFloat(form.budget);
    if (isNaN(budget) || budget <= 0)
      return "Введите корректный бюджет (больше 0)";
    if (budget > 10_000_000)
      return "Бюджет слишком большой";
    if (form.skills.length === 0)
      return "Добавьте хотя бы один необходимый навык";
    if (form.xp_reward) {
      const xp = parseInt(form.xp_reward);
      if (isNaN(xp) || xp < 10 || xp > 500)
        return "XP награда должна быть от 10 до 500";
    }
    return null;
  };

  // ─── Submit ─────────────────────────────────────────────────────────────────

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    try {
      const quest = await createQuest({
        title: form.title.trim(),
        description: form.description.trim(),
        required_grade: form.required_grade,
        skills: form.skills,
        budget: parseFloat(form.budget),
        currency: form.currency,
        xp_reward: form.xp_reward ? parseInt(form.xp_reward) : undefined,
      });

      setSuccess(true);
      setTimeout(() => router.push(`/quests/${quest.id}`), 1500);
    } catch (err) {
      console.error("Quest creation error:", err);
      setError("Не удалось создать квест. Проверьте данные и попробуйте ещё раз.");
    } finally {
      setLoading(false);
    }
  };

  // ─── Render ─────────────────────────────────────────────────────────────────

  if (success) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center"
        >
          <div className="text-7xl mb-6">🎉</div>
          <h2 className="text-3xl font-bold text-white mb-2">Квест создан!</h2>
          <p className="text-gray-400">Перенаправляем на страницу квеста...</p>
        </motion.div>
      </main>
    );
  }

  const suggested = suggestedXp();

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />

      <div className="container mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-2xl mx-auto"
        >
          {/* Page header */}
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold mb-2">
              <span className="text-purple-400">✨</span>{" "}
              <span className="text-white">Создать квест</span>
            </h1>
            <p className="text-gray-400">Опишите задачу — фрилансеры откликнутся</p>
          </div>

          {/* Tip for clients */}
          {user?.role === "freelancer" && (
            <Card className="p-4 mb-6 border-yellow-500/30 bg-yellow-500/10">
              <p className="text-yellow-300 text-sm">
                💡 Вы зарегистрированы как <strong>фрилансер</strong>. Квесты обычно
                создают клиенты, но ничто не мешает вам разместить задание тоже.
              </p>
            </Card>
          )}

          {/* Error */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 p-4 bg-red-900/30 border border-red-500/50 rounded-lg text-red-200 text-sm"
            >
              ⚠️ {error}
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Title */}
            <Card className="p-6">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <span>📝</span> Основное
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Название квеста <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.title}
                    onChange={(e) => updateField("title", e.target.value)}
                    maxLength={100}
                    placeholder="Например: Разработать Telegram-бота для записи клиентов"
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500 transition-colors"
                    disabled={loading}
                  />
                  <div className="flex justify-between mt-1">
                    <span className="text-xs text-gray-500">Минимум 5 символов</span>
                    <span className={`text-xs ${form.title.length > 90 ? "text-yellow-400" : "text-gray-500"}`}>
                      {form.title.length}/100
                    </span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Описание задачи <span className="text-red-400">*</span>
                  </label>
                  <textarea
                    value={form.description}
                    onChange={(e) => updateField("description", e.target.value)}
                    maxLength={2000}
                    rows={6}
                    placeholder="Подробно опишите что нужно сделать, какой результат ожидается, есть ли дизайн/ТЗ..."
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500 resize-y transition-colors"
                    disabled={loading}
                  />
                  <div className="flex justify-between mt-1">
                    <span className="text-xs text-gray-500">Минимум 20 символов</span>
                    <span className={`text-xs ${form.description.length > 1800 ? "text-yellow-400" : "text-gray-500"}`}>
                      {form.description.length}/2000
                    </span>
                  </div>
                </div>
              </div>
            </Card>

            {/* Grade */}
            <Card className="p-6">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <span>🎮</span> Требуемый грейд
              </h2>
              <div className="grid grid-cols-2 gap-3">
                {GRADE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => updateField("required_grade", opt.value)}
                    className={`p-4 rounded-lg border-2 text-left transition-all ${
                      form.required_grade === opt.value
                        ? "border-purple-500 bg-purple-500/20"
                        : "border-gray-700 bg-gray-800 hover:border-gray-600"
                    }`}
                    disabled={loading}
                  >
                    <div className="text-2xl mb-1">{opt.icon}</div>
                    <div className="font-bold text-white text-sm">{opt.label}</div>
                    <div className="text-xs text-gray-400 mt-1">{opt.description}</div>
                  </button>
                ))}
              </div>
            </Card>

            {/* Skills */}
            <Card className="p-6">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <span>🛠️</span> Необходимые навыки{" "}
                <span className="text-sm font-normal text-gray-400">
                  (до 10)
                </span>
              </h2>

              {/* Selected skills */}
              {form.skills.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {form.skills.map((skill) => (
                    <span
                      key={skill}
                      className="flex items-center gap-1 px-3 py-1 bg-purple-600/30 border border-purple-500/50 rounded-full text-sm text-purple-200"
                    >
                      {skill}
                      <button
                        type="button"
                        onClick={() => removeSkill(skill)}
                        className="ml-1 text-purple-400 hover:text-red-400 transition-colors leading-none"
                        title="Удалить навык"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}

              {/* Manual input */}
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  value={skillInput}
                  onChange={(e) => setSkillInput(e.target.value)}
                  onKeyDown={handleSkillKeyDown}
                  placeholder="Введите навык и нажмите Enter..."
                  className="flex-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500 text-sm"
                  disabled={loading || form.skills.length >= 10}
                />
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => addSkill(skillInput)}
                  disabled={loading || !skillInput.trim() || form.skills.length >= 10}
                  className="text-sm px-4"
                >
                  + Добавить
                </Button>
              </div>

              {/* Popular skills */}
              <div>
                <p className="text-xs text-gray-500 mb-2">Популярные навыки:</p>
                <div className="flex flex-wrap gap-2">
                  {POPULAR_SKILLS.filter((s) => !form.skills.includes(s)).slice(0, 20).map((skill) => (
                    <button
                      key={skill}
                      type="button"
                      onClick={() => addSkill(skill)}
                      disabled={loading || form.skills.length >= 10}
                      className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-gray-400 hover:border-purple-500 hover:text-purple-300 transition-colors disabled:opacity-40"
                    >
                      {skill}
                    </button>
                  ))}
                </div>
              </div>
            </Card>

            {/* Budget & XP */}
            <Card className="p-6">
              <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                <span>💰</span> Бюджет и награда
              </h2>

              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Бюджет <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="number"
                    value={form.budget}
                    onChange={(e) => updateField("budget", e.target.value)}
                    placeholder="5000"
                    min="1"
                    max="10000000"
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500"
                    disabled={loading}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">
                    Валюта
                  </label>
                  <select
                    value={form.currency}
                    onChange={(e) => updateField("currency", e.target.value)}
                    className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white"
                    disabled={loading}
                  >
                    {CURRENCY_OPTIONS.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  XP награда{" "}
                  <span className="text-gray-500 font-normal">(необязательно, 10–500)</span>
                </label>
                <div className="flex gap-3 items-center">
                  <input
                    type="number"
                    value={form.xp_reward}
                    onChange={(e) => updateField("xp_reward", e.target.value)}
                    placeholder={suggested !== null ? `Авто: ${suggested} XP` : "Например: 150"}
                    min="10"
                    max="500"
                    className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500"
                    disabled={loading}
                  />
                  {suggested !== null && !form.xp_reward && (
                    <button
                      type="button"
                      onClick={() => updateField("xp_reward", String(suggested))}
                      className="text-sm text-purple-400 hover:text-purple-300 whitespace-nowrap"
                    >
                      ← Взять {suggested} XP
                    </button>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Если не заполнено — рассчитывается автоматически (10% от бюджета)
                </p>
              </div>

              {/* Budget preview */}
              {form.budget && parseFloat(form.budget) > 0 && (
                <div className="mt-4 p-3 bg-gray-800/50 rounded-lg border border-gray-700">
                  <p className="text-xs text-gray-400 mb-1">Предпросмотр награды:</p>
                  <div className="flex gap-6 text-sm">
                    <span className="text-green-400 font-bold">
                      💰 {parseFloat(form.budget).toLocaleString("ru-RU")} {form.currency}
                    </span>
                    <span className="text-purple-400 font-bold">
                      ⚡ {form.xp_reward || suggested || "~"} XP
                    </span>
                  </div>
                </div>
              )}
            </Card>

            {/* Actions */}
            <div className="flex gap-4">
              <Button
                type="submit"
                variant="primary"
                className="flex-1 py-3 text-base font-bold"
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle
                        className="opacity-25"
                        cx="12" cy="12" r="10"
                        stroke="currentColor" strokeWidth="4" fill="none"
                      />
                      <path
                        className="opacity-75" fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Создаём квест...
                  </span>
                ) : (
                  "🚀 Разместить квест"
                )}
              </Button>

              <Link href="/quests">
                <Button type="button" variant="secondary" className="py-3 px-6">
                  Отмена
                </Button>
              </Link>
            </div>

            <p className="text-center text-xs text-gray-500">
              Размещая квест, вы соглашаетесь с правилами платформы.
              После размещения фрилансеры смогут откликнуться.
            </p>
          </form>
        </motion.div>
      </div>
    </main>
  );
}
