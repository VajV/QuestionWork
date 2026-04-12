"use client";

import { useState, useEffect, useCallback, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { motion } from "@/lib/motion";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import FreelancerOnboardingChecklist, {
  type OnboardingItem,
} from "@/components/profile/FreelancerOnboardingChecklist";
import { getUserProfile, updateMyProfile, getApiErrorMessage, type PublicUserProfile } from "@/lib/api";

const AVAILABILITY_OPTIONS = [
  { value: "available", label: "Готов брать новые задачи" },
  { value: "limited", label: "Осталось 1-2 слота" },
  { value: "busy", label: "Сфокусирован на текущих задачах" },
] as const;

function buildChecklist(
  bio: string,
  skills: string[],
  availabilityStatus: string,
  portfolioSummary: string,
  portfolioLinks: string[],
  hasProofItem: boolean,
  hasClass: boolean,
): OnboardingItem[] {
  return [
    {
      key: "bio",
      label: "Заполнить биографию",
      hint: "Расскажите о себе и своём опыте — заказчики смотрят это первым.",
      done: bio.trim().length >= 20,
    },
    {
      key: "skills",
      label: "Добавить навыки (минимум 2)",
      hint: "Укажите технологии и области экспертизы для точного подбора квестов.",
      done: skills.filter((s) => s.trim()).length >= 2,
    },
    {
      key: "availability",
      label: "Показать доступность",
      hint: "Заказчик должен понять, готовы ли вы взять новый проект сейчас.",
      done: availabilityStatus.trim().length > 0,
    },
    {
      key: "portfolio",
      label: "Добавить портфолио или summary",
      hint: "Ссылка на кейсы или короткое описание выполненных проектов повышает доверие.",
      done: portfolioLinks.length > 0 || portfolioSummary.trim().length >= 40,
    },
    {
      key: "proof",
      label: "Получить первый proof item",
      hint: "Первый отзыв или подтверждённый квест закрепляет доверие сильнее любой витрины.",
      done: hasProofItem,
    },
    {
      key: "class",
      label: "Выбрать класс персонажа",
      hint: "Класс открывается на 5-м уровне и влияет на бонусы XP.",
      done: hasClass,
    },
  ];
}

export default function ProfileSetupPage() {
  const router = useRouter();
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [bio, setBio] = useState("");
  const [skillsInput, setSkillsInput] = useState("");
  const [availabilityStatus, setAvailabilityStatus] = useState("");
  const [portfolioSummary, setPortfolioSummary] = useState("");
  const [portfolioLinksInput, setPortfolioLinksInput] = useState("");
  const [profileSnapshot, setProfileSnapshot] = useState<PublicUserProfile | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (user) {
      setBio(user.bio ?? "");
      setSkillsInput((user.skills ?? []).join(", "));
      setAvailabilityStatus(user.availability_status ?? "");
      setPortfolioSummary(user.portfolio_summary ?? "");
      setPortfolioLinksInput((user.portfolio_links ?? []).join("\n"));
    }
  }, [user]);

  useEffect(() => {
    if (!user?.id) {
      return;
    }

    getUserProfile(user.id)
      .then((profile) => setProfileSnapshot(profile))
      .catch(() => setProfileSnapshot(null));
  }, [user?.id]);

  const skills = skillsInput
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const portfolioLinks = portfolioLinksInput
    .split(/\r?\n/)
    .map((link) => link.trim())
    .filter(Boolean);

  const checklist = buildChecklist(
    bio,
    skills,
    availabilityStatus,
    portfolioSummary,
    portfolioLinks,
    Boolean((profileSnapshot?.review_count ?? 0) > 0 || (profileSnapshot?.confirmed_quest_count ?? 0) > 0),
    !!user?.character_class,
  );

  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setSaving(true);
      setError(null);
      try {
        await updateMyProfile({
          bio: bio.trim(),
          skills,
          availability_status: availabilityStatus,
          portfolio_summary: portfolioSummary.trim(),
          portfolio_links: portfolioLinks,
        });
        setSaved(true);
        setTimeout(() => router.push("/profile"), 1200);
      } catch (err) {
        setError(getApiErrorMessage(err, "Не удалось сохранить."));
      } finally {
        setSaving(false);
      }
    },
    [availabilityStatus, bio, portfolioLinks, portfolioSummary, router, skills],
  );

  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Header />
      <main className="max-w-3xl mx-auto px-4 py-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-3xl font-cinzel text-amber-400 mb-2">
            Настройка профиля
          </h1>
          <p className="text-gray-400 mb-8">
            Заполните информацию о себе, чтобы заказчики могли вас найти и довериться вам.
          </p>

          <div className="grid gap-8 lg:grid-cols-[1fr_280px]">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Bio */}
              <Card className="p-6">
                <label className="block text-sm font-medium text-amber-300 mb-2">
                  О себе
                </label>
                <textarea
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  rows={4}
                  maxLength={500}
                  placeholder="Кратко опишите свой опыт, специализацию и чем вы полезны заказчикам..."
                  className="w-full bg-gray-900/60 border border-gray-700 rounded-lg p-3 text-sm text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none resize-none"
                />
                <p className="text-xs text-gray-500 mt-1 text-right">
                  {bio.length}/500
                </p>
              </Card>

              {/* Skills */}
              <Card className="p-6">
                <label className="block text-sm font-medium text-amber-300 mb-2">
                  Навыки (через запятую)
                </label>
                <input
                  type="text"
                  value={skillsInput}
                  onChange={(e) => setSkillsInput(e.target.value)}
                  placeholder="TypeScript, React, FastAPI, PostgreSQL..."
                  className="w-full bg-gray-900/60 border border-gray-700 rounded-lg p-3 text-sm text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none"
                />
                {skills.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {skills.map((s, i) => (
                      <span
                        key={i}
                        className="px-2.5 py-1 text-xs rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </Card>

              <Card className="p-6">
                <label className="block text-sm font-medium text-amber-300 mb-2">
                  Текущая доступность
                </label>
                <div className="grid gap-2">
                  {AVAILABILITY_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setAvailabilityStatus(option.value)}
                      className={`rounded-lg border px-4 py-3 text-left text-sm transition-colors ${
                        availabilityStatus === option.value
                          ? "border-amber-500/50 bg-amber-500/10 text-amber-200"
                          : "border-gray-700 bg-gray-900/40 text-gray-300 hover:border-gray-500"
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </Card>

              <Card className="p-6">
                <label className="block text-sm font-medium text-amber-300 mb-2">
                  Portfolio summary
                </label>
                <textarea
                  value={portfolioSummary}
                  onChange={(e) => setPortfolioSummary(e.target.value)}
                  rows={3}
                  maxLength={500}
                  placeholder="Опишите 1-2 сильных кейса, чтобы заказчик сразу понял ваш тип проектов и уровень результата."
                  className="w-full bg-gray-900/60 border border-gray-700 rounded-lg p-3 text-sm text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none resize-none"
                />
                <p className="text-xs text-gray-500 mt-1 text-right">
                  {portfolioSummary.length}/500
                </p>

                <label className="block text-sm font-medium text-amber-300 mb-2 mt-5">
                  Ссылки на портфолио
                </label>
                <textarea
                  value={portfolioLinksInput}
                  onChange={(e) => setPortfolioLinksInput(e.target.value)}
                  rows={4}
                  placeholder={"https://github.com/you/project\nhttps://dribbble.com/shots/..."}
                  className="w-full bg-gray-900/60 border border-gray-700 rounded-lg p-3 text-sm text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none resize-none"
                />
                <p className="text-xs text-gray-500 mt-1">
                  По одной ссылке на строку. Подойдут GitHub, Behance, Dribbble, Notion case study или live-demo.
                </p>
              </Card>

              {error && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-400">
                  {error}
                </div>
              )}

              {saved && (
                <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3 text-sm text-emerald-400">
                  Профиль сохранён! Перенаправляем...
                </div>
              )}

              <div className="flex gap-3">
                <Button type="submit" variant="primary" disabled={saving}>
                  {saving ? "Сохраняю..." : "Сохранить профиль"}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => router.push("/profile")}
                >
                  Пропустить
                </Button>
              </div>
            </form>

            {/* Sidebar checklist */}
            <div className="hidden lg:block">
              <FreelancerOnboardingChecklist items={checklist} />
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  );
}
