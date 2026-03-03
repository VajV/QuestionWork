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
          <div className="text-center mb-8 mt-4">
            <h1 className="text-3xl md:text-4xl font-cinzel font-bold mb-2 text-amber-500 flex items-center justify-center gap-3 drop-shadow-[0_0_10px_rgba(217,119,6,0.5)] uppercase tracking-widest">
              <span className="text-3xl grayscale">✍️</span>
              Объявить Контракт
              <span className="text-3xl grayscale">📜</span>
            </h1>
            <div className="divider-ornament w-64 mx-auto my-4"></div>
            <p className="text-gray-400 font-inter">Опишите задачу — и наёмники откликнутся на ваш зов</p>
          </div>

          {/* Tip for clients */}
          {user?.role === "freelancer" && (
            <Card className="mb-6 p-0 border-none bg-transparent">
              <div className="bg-yellow-950/30 border border-yellow-700/50 p-4 rounded text-yellow-300 text-sm font-mono shadow-[inset_0_0_15px_rgba(234,179,8,0.1)]">
                <span className="mr-2">💡</span>
                Вы примкнули к фракции <strong>Наёмников</strong>. Обычно контракты создают Заказчики, но законы Гильдии не запрещают вам искать помощь.
              </div>
            </Card>
          )}

          {/* Error */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 p-4 bg-red-950/40 border border-red-900/50 rounded font-mono text-red-500 text-sm shadow-[0_0_10px_rgba(220,38,38,0.2)]"
            >
              ⚠️ {error}
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Title */}
            <Card className="p-0 border-none bg-transparent">
              <div className="rpg-card p-6 md:p-8">
                <h2 className="text-xl font-cinzel font-bold mb-6 text-amber-500 flex items-center gap-3 border-b border-amber-900/30 pb-3">
                  <span className="grayscale opacity-70">📝</span> Суть Задания
                </h2>

                <div className="space-y-6">
                  <div>
                    <label className="block text-xs font-mono uppercase tracking-widest text-gray-500 mb-2">
                      Заголовок Свитка <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={form.title}
                      onChange={(e) => updateField("title", e.target.value)}
                      maxLength={100}
                      placeholder="Например: Создать голема для сбора ресурсов"
                      className="w-full px-4 py-3 bg-black/50 border border-gray-800 rounded font-inter focus:outline-none focus:border-amber-500 text-gray-200 placeholder-gray-600 transition-colors shadow-inner"
                      disabled={loading}
                    />
                    <div className="flex justify-between mt-2 font-mono">
                      <span className="text-xs text-gray-600">От 5 рун</span>
                      <span className={`text-xs ${form.title.length > 90 ? "text-amber-500" : "text-gray-600"}`}>
                        {form.title.length}/100
                      </span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-mono uppercase tracking-widest text-gray-500 mb-2">
                      Подробности <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      value={form.description}
                      onChange={(e) => updateField("description", e.target.value)}
                      maxLength={2000}
                      rows={6}
                      placeholder="Опишите, что нужно совершить, какие артефакты требуются и так далее..."
                      className="w-full px-4 py-3 bg-black/50 border border-gray-800 rounded font-inter focus:outline-none focus:border-amber-500 text-gray-200 placeholder-gray-600 resize-y transition-colors shadow-inner"
                      disabled={loading}
                    />
                    <div className="flex justify-between mt-2 font-mono">
                      <span className="text-xs text-gray-600">От 20 рун</span>
                      <span className={`text-xs ${form.description.length > 1800 ? "text-amber-500" : "text-gray-600"}`}>
                        {form.description.length}/2000
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            {/* Grade */}
            <Card className="p-0 border-none bg-transparent">
              <div className="rpg-card p-6 md:p-8">
                <h2 className="text-xl font-cinzel font-bold mb-6 text-purple-400 flex items-center gap-3 border-b border-purple-900/30 pb-3">
                  <span className="grayscale opacity-70">🎮</span> Минимальный Ранг
                </h2>
                <div className="grid grid-cols-2 gap-4 mt-4">
                  {GRADE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => updateField("required_grade", opt.value)}
                      className={`p-4 rounded border-2 text-left transition-all ${
                        form.required_grade === opt.value
                          ? "border-amber-500 bg-amber-950/20 shadow-[inset_0_0_10px_rgba(217,119,6,0.2)]"
                          : "border-gray-800 bg-black/40 hover:border-gray-600 hover:bg-gray-900/50"
                      }`}
                      disabled={loading}
                    >
                      <div className="text-2xl mb-2 opacity-80">{opt.icon}</div>
                      <div className="font-cinzel font-bold text-gray-200 text-sm tracking-wider">{opt.label}</div>
                      <div className="text-xs text-gray-500 font-inter mt-1 leading-relaxed">{opt.description}</div>
                    </button>
                  ))}
                </div>
              </div>
            </Card>

            {/* Skills */}
            <Card className="p-0 border-none bg-transparent">
              <div className="rpg-card p-6 md:p-8">
                <h2 className="text-xl font-cinzel font-bold mb-6 text-gray-100 flex items-center gap-3 border-b border-gray-800 pb-3">
                  <span className="grayscale opacity-70">🛠️</span> Инструменты & Чары{" "}
                  <span className="text-sm font-mono text-gray-500 ml-2">
                    (до 10)
                  </span>
                </h2>

                {/* Selected skills */}
                {form.skills.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-6">
                    {form.skills.map((skill) => (
                      <span
                        key={skill}
                        className="flex items-center gap-2 px-3 py-1 bg-purple-950/40 border border-purple-800/60 rounded font-mono text-sm text-purple-200 shadow-sm"
                      >
                        {skill}
                        <button
                          type="button"
                          onClick={() => removeSkill(skill)}
                          className="text-purple-400 hover:text-red-400 font-bold transition-colors leading-none"
                          title="Развеять чары"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                {/* Manual input */}
                <div className="flex flex-col sm:flex-row gap-3 mb-6">
                  <input
                    type="text"
                    value={skillInput}
                    onChange={(e) => setSkillInput(e.target.value)}
                    onKeyDown={handleSkillKeyDown}
                    placeholder="Назовите навык и нажмите Enter..."
                    className="flex-1 px-4 py-3 bg-black/50 border border-gray-800 rounded font-inter focus:outline-none focus:border-purple-500 text-gray-200 placeholder-gray-600 text-sm shadow-inner transition-colors"
                    disabled={loading || form.skills.length >= 10}
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => addSkill(skillInput)}
                    disabled={loading || !skillInput.trim() || form.skills.length >= 10}
                    className="text-sm px-6 font-cinzel border-purple-900/50 hover:border-purple-500/50"
                  >
                    + Вплести
                  </Button>
                </div>

                {/* Popular skills */}
                <div>
                  <p className="text-xs font-mono uppercase tracking-widest text-gray-500 mb-3">Известные манускрипты:</p>
                  <div className="flex flex-wrap gap-2">
                    {POPULAR_SKILLS.filter((s) => !form.skills.includes(s)).slice(0, 20).map((skill) => (
                      <button
                        key={skill}
                        type="button"
                        onClick={() => addSkill(skill)}
                        disabled={loading || form.skills.length >= 10}
                        className="px-3 py-1.5 bg-gray-900 border border-gray-800 rounded font-mono text-xs text-gray-400 hover:border-purple-700 hover:text-purple-300 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        + {skill}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>

            {/* Budget & XP */}
            <Card className="p-0 border-none bg-transparent">
              <div className="rpg-card p-6 md:p-8">
                <h2 className="text-xl font-cinzel font-bold mb-6 text-green-500 flex items-center gap-3 border-b border-green-900/30 pb-3">
                  <span className="grayscale opacity-70">💰</span> Предлагаемая Добыча
                </h2>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6">
                  <div>
                    <label className="block text-xs font-mono uppercase tracking-widest text-gray-500 mb-2">
                      Награда <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="number"
                      value={form.budget}
                      onChange={(e) => updateField("budget", e.target.value)}
                      placeholder="5000"
                      min="1"
                      max="10000000"
                      className="w-full px-4 py-3 bg-black/50 border border-gray-800 rounded font-mono focus:outline-none focus:border-green-500 text-gray-200 placeholder-gray-600 shadow-inner transition-colors"
                      disabled={loading}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-mono uppercase tracking-widest text-gray-500 mb-2">
                      Валюта
                    </label>
                    <select
                      value={form.currency}
                      onChange={(e) => updateField("currency", e.target.value)}
                      className="w-full px-4 py-3 bg-black/50 border border-gray-800 rounded font-mono focus:outline-none focus:border-green-500 text-gray-200 shadow-inner transition-colors"
                      disabled={loading}
                    >
                      {CURRENCY_OPTIONS.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-mono uppercase tracking-widest text-gray-500 mb-2">
                    Даруемый Опыт{" "}
                    <span className="text-gray-600 normal-case tracking-normal ml-2">(по желанию, 10–500 XP)</span>
                  </label>
                  <div className="flex flex-col sm:flex-row gap-3 items-center">
                    <input
                      type="number"
                      value={form.xp_reward}
                      onChange={(e) => updateField("xp_reward", e.target.value)}
                      placeholder={suggested !== null ? `Предсказано: ${suggested} XP` : "Например: 150"}
                      min="10"
                      max="500"
                      className="w-full sm:flex-1 px-4 py-3 bg-black/50 border border-gray-800 rounded font-mono focus:outline-none focus:border-purple-500 text-gray-200 placeholder-gray-600 shadow-inner transition-colors"
                      disabled={loading}
                    />
                    {suggested !== null && !form.xp_reward && (
                      <button
                        type="button"
                        onClick={() => updateField("xp_reward", String(suggested))}
                        className="text-sm font-mono text-purple-400 hover:text-purple-300 bg-purple-950/30 px-3 py-2 rounded border border-purple-800/50 whitespace-nowrap transition-colors"
                      >
                        ← Принять {suggested} XP
                      </button>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-2 font-inter italic">
                    * Если оставить пустым — гильдия рассчитает опыт автоматически (10% от золота)
                  </p>
                </div>

                {/* Budget preview */}
                {form.budget && parseFloat(form.budget) > 0 && (
                  <div className="mt-6 p-4 bg-gray-900/50 border border-gray-800 rounded font-mono">
                    <p className="text-xs text-gray-500 uppercase tracking-widest mb-2">Награда за успешно выполненный долг:</p>
                    <div className="flex gap-8 text-base">
                      <span className="text-amber-500 font-bold drop-shadow-[0_0_8px_rgba(217,119,6,0.5)]">
                        💰 {parseFloat(form.budget).toLocaleString("ru-RU")} {form.currency}
                      </span>
                      <span className="text-purple-400 font-bold drop-shadow-[0_0_8px_rgba(168,85,247,0.5)]">
                        ⚡ {form.xp_reward || suggested || "~"} XP
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </Card>

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-4 mt-8">
              <Button
                type="submit"
                variant="primary"
                className="flex-1 py-4 text-lg font-cinzel tracking-wider shadow-[0_0_15px_rgba(217,119,6,0.3)] hover:shadow-[0_0_25px_rgba(217,119,6,0.5)]"
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-3">
                    <svg className="animate-spin h-5 w-5 text-amber-500" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Запечатываем...
                  </span>
                ) : (
                  "📜 Прибить к Доске"
                )}
              </Button>

              <Link href="/quests" className="sm:w-1/3">
                <Button type="button" variant="secondary" className="w-full h-full font-cinzel tracking-wider border-purple-900/50 hover:border-purple-500/50">
                  Вернуться
                </Button>
              </Link>
            </div>

            <p className="text-center text-xs text-gray-600 font-inter max-w-sm mx-auto mt-6">
              Объявляя контракт, вы клянётесь соблюдать Кодекс Гильдии. Невыплата награды карается изгнанием.
            </p>
          </form>
        </motion.div>
      </div>
    </main>
  );
}
