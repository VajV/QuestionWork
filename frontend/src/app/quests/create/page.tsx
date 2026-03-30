/**
 * Quest creation page — guided workflow
 * Only authenticated users with client/admin role can create quests
 */

"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion } from "@/lib/motion";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import QuestCreationWizard from "@/components/quests/QuestCreationWizard";
import type { WizardFormState } from "@/components/quests/QuestCreationWizard";
import { trackAnalyticsEvent } from "@/lib/analytics";

export default function CreateQuestPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-400">Загрузка...</p>
        </div>
      </main>
    }>
      <CreateQuestInner />
    </Suspense>
  );
}

function CreateQuestInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, user, loading: authLoading } = useAuth();

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/auth/login");
    }
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      trackAnalyticsEvent("quest_create_started");
    }
  }, [authLoading, isAuthenticated]);

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

  // Only clients and admins can create quests
  if (user?.role !== "client" && user?.role !== "admin") {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
        <Header />
        <div className="flex items-center justify-center min-h-[80vh]">
          <div className="text-center max-w-md px-6">
            <div className="text-6xl mb-6">🚫</div>
            <h2 className="text-2xl font-bold text-white mb-3">Недостаточно прав</h2>
            <p className="text-gray-400 mb-6">
              Создавать квесты могут только пользователи с ролью <span className="text-purple-400 font-semibold">Клиент</span> или <span className="text-purple-400 font-semibold">Админ</span>.
              Фрилансеры могут только откликаться на уже существующие контракты.
            </p>
            <Link
              href="/quests"
              className="inline-block bg-purple-600 hover:bg-purple-700 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
            >
              Смотреть квесты
            </Link>
          </div>
        </div>
      </main>
    );
  }

  // Build initial data from query params (template pre-fill)
  const initialData: Partial<WizardFormState> = {};
  const tTitle = searchParams.get("title");
  const tDesc = searchParams.get("description");
  const tGrade = searchParams.get("grade");
  const tSkills = searchParams.get("skills");
  const tBudget = searchParams.get("budget");
  const tCurrency = searchParams.get("currency");
  const tUrgent = searchParams.get("urgent");
  const tPortfolio = searchParams.get("portfolio");
  const templateId = searchParams.get("template_id");
  const templateName = searchParams.get("template_name");
  if (tTitle) initialData.title = tTitle;
  if (tDesc) initialData.description = tDesc;
  if (tGrade) initialData.required_grade = tGrade as WizardFormState["required_grade"];
  if (tSkills) initialData.skills = tSkills.split(",").map((s) => s.trim()).filter(Boolean);
  if (tBudget) initialData.budget = tBudget;
  if (tCurrency) initialData.currency = tCurrency;
  if (tUrgent === "true") initialData.is_urgent = true;
  if (tPortfolio === "true") initialData.required_portfolio = true;

  return (
    <main className="guild-world-shell min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      <Header />

      <div className="container mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-4xl mx-auto"
        >
          {/* Page header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl md:text-4xl font-cinzel font-bold mb-2 text-amber-500 flex items-center justify-center gap-3 drop-shadow-[0_0_10px_rgba(217,119,6,0.5)] uppercase tracking-widest">
              <span className="text-3xl grayscale">✍️</span>
              Объявить Контракт
              <span className="text-3xl grayscale">📜</span>
            </h1>
            <div className="divider-ornament w-64 mx-auto my-4"></div>
            <p className="text-gray-400 font-inter">Пошаговый помощник — заполните бриф и опубликуйте квест</p>
          </div>

          <QuestCreationWizard
            initialData={Object.keys(initialData).length > 0 ? initialData : undefined}
            templateMeta={templateId ? { id: templateId, name: templateName ?? undefined } : undefined}
          />

          <p className="text-center text-xs text-gray-600 font-inter max-w-sm mx-auto mt-8">
            Объявляя контракт, вы клянётесь соблюдать Кодекс Гильдии.
          </p>
        </motion.div>
      </div>
    </main>
  );
}
