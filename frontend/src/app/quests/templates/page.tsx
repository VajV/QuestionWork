/**
 * Quest Templates management page
 *
 * Clients and admins can create, view, edit, delete and use templates
 * to quickly create quests from saved blueprints.
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  getTemplates,
  createTemplate,
  deleteTemplate,
  updateTemplate,
  createQuestFromTemplate,
  getApiErrorMessage,
  QuestTemplate,
  UpdateTemplatePayload,
} from "@/lib/api";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import SeasonFactionRail from "@/components/ui/SeasonFactionRail";
import WorldPanel from "@/components/ui/WorldPanel";
import { trackAnalyticsEvent } from "@/lib/analytics";
import { safeParseMoney } from "@/lib/money";
import {
  Plus,
  Trash2,
  FileText,
  Rocket,
  Loader2,
  ChevronUp,
  Pencil,
  X,
} from "lucide-react";

const GRADE_LABELS: Record<string, string> = {
  novice: "Novice",
  junior: "Junior",
  middle: "Middle",
  senior: "Senior",
};

const GRADE_COLORS: Record<string, string> = {
  novice: "text-gray-400 border-gray-600 bg-gray-900/50",
  junior: "text-green-400 border-green-700 bg-green-950/40",
  middle: "text-blue-400 border-blue-700 bg-blue-950/40",
  senior: "text-purple-300 border-purple-700 bg-purple-950/40",
};

const INTENT_GROUPS = [
  { label: "MVP / Прототип", icon: "🚀", hint: "Быстрый запуск продукта", keywords: ["mvp", "prototype", "прототип", "лендинг", "landing"] },
  { label: "Срочный фикс", icon: "🔥", hint: "Исправление бага или сбоя", keywords: ["fix", "bug", "фикс", "баг", "срочн", "urgent"] },
  { label: "Дашборд / Аналитика", icon: "📊", hint: "Панели и отчёты", keywords: ["dashboard", "дашборд", "аналитик", "отчёт", "report"] },
  { label: "Бэкенд / API", icon: "⚙️", hint: "Серверная разработка", keywords: ["backend", "api", "бэкенд", "сервер", "fastapi", "django"] },
  { label: "Фронтенд / UI", icon: "🎨", hint: "Интерфейс и компоненты", keywords: ["frontend", "ui", "ux", "фронтенд", "react", "next", "vue"] },
  { label: "Рефакторинг", icon: "🔧", hint: "Улучшение кодовой базы", keywords: ["refactor", "рефакторинг", "переписать", "migration", "миграц"] },
];

export default function TemplatesPage() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuth();

  const [templates, setTemplates] = useState<QuestTemplate[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Editing state
  const [editingId, setEditingId] = useState<string | null>(null);

  // New template form
  const [showForm, setShowForm] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const hasTrackedView = useRef(false);
  const [form, setForm] = useState({
    name: "",
    title: "",
    description: "",
    required_grade: "novice" as string,
    skills: "" as string,
    budget: "",
    currency: "RUB",
    is_urgent: false,
    required_portfolio: false,
  });

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getTemplates(50, 0);
      setTemplates(res.templates);
      setTotal(res.total);
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось загрузить шаблоны"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) load();
  }, [isAuthenticated, load]);

  useEffect(() => {
    if (loading || hasTrackedView.current) {
      return;
    }
    hasTrackedView.current = true;
    trackAnalyticsEvent("template_viewed", {
      template_count: templates.length,
      recommended_group_count: INTENT_GROUPS.length,
    });
  }, [loading, templates.length]);

  // Guard: only clients/admins
  useEffect(() => {
    if (user && user.role !== "client" && user.role !== "admin") {
      router.push("/quests");
    }
  }, [user, router]);

  const handleCreate = async () => {
    if (!form.name.trim() || !form.title.trim()) return;
    setFormLoading(true);
    setError(null);

    try {
      const skills = form.skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      await createTemplate({
        name: form.name.trim(),
        title: form.title.trim(),
        description: form.description.trim(),
        required_grade: form.required_grade,
        skills,
        budget: safeParseMoney(form.budget) ?? 0,
        currency: form.currency,
        is_urgent: form.is_urgent,
        required_portfolio: form.required_portfolio,
      });
      setSuccess("Шаблон создан!");
      setShowForm(false);
      setForm({
        name: "",
        title: "",
        description: "",
        required_grade: "novice",
        skills: "",
        budget: "",
        currency: "RUB",
        is_urgent: false,
        required_portfolio: false,
      });
      await load();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(getApiErrorMessage(err, "Ошибка при создании шаблона"));
    } finally {
      setFormLoading(false);
    }
  };

  const handleEdit = useCallback((template: QuestTemplate) => {
    setForm({
      name: template.name,
      title: template.title,
      description: template.description || "",
      required_grade: template.required_grade,
      skills: template.skills.join(", "),
      budget: template.budget > 0 ? String(template.budget) : "",
      currency: template.currency || "RUB",
      is_urgent: template.is_urgent,
      required_portfolio: template.required_portfolio,
    });
    setEditingId(template.id);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const handleUpdate = async () => {
    if (!editingId) return;
    setFormLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: UpdateTemplatePayload = {
        name: form.name.trim() || undefined,
        title: form.title.trim() || undefined,
        description: form.description.trim() || undefined,
        required_grade: form.required_grade || undefined,
        skills: form.skills ? form.skills.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
        budget: form.budget ? (safeParseMoney(form.budget) ?? undefined) : undefined,
        currency: form.currency || undefined,
        is_urgent: form.is_urgent,
        required_portfolio: form.required_portfolio,
      };
      await updateTemplate(editingId, payload);
      setSuccess("Шаблон обновлён!");
      setEditingId(null);
      setShowForm(false);
      setForm({
        name: "",
        title: "",
        description: "",
        required_grade: "novice",
        skills: "",
        budget: "",
        currency: "RUB",
        is_urgent: false,
        required_portfolio: false,
      });
      await load();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось обновить шаблон"));
    } finally {
      setFormLoading(false);
    }
  };

  const handleCancelEdit = useCallback(() => {
    setEditingId(null);
    setShowForm(false);
    setForm({
      name: "",
      title: "",
      description: "",
      required_grade: "novice",
      skills: "",
      budget: "",
      currency: "RUB",
      is_urgent: false,
      required_portfolio: false,
    });
  }, []);

  const handleDelete = async (id: string) => {
    if (!confirm("Удалить шаблон?")) return;
    try {
      await deleteTemplate(id);
      setTemplates((prev) => prev.filter((t) => t.id !== id));
      setTotal((t) => t - 1);
      setSuccess("Шаблон удалён");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(getApiErrorMessage(err, "Ошибка при удалении"));
    }
  };

  const handleUseTemplate = async (id: string) => {
    const template = templates.find((item) => item.id === id);
    trackAnalyticsEvent("template_selected", {
      template_id: id,
      template_name: template?.name ?? null,
      flow: "instant-create",
    });
    try {
      const quest = await createQuestFromTemplate(id);
      trackAnalyticsEvent("quest_created_from_template", {
        template_id: id,
        template_name: template?.name ?? null,
        quest_id: quest.id,
        flow: "instant-create",
      });
      router.push(`/quests/${quest.id}`);
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось создать квест из шаблона"));
    }
  };

  /** Navigate to guided wizard with template pre-filled */
  const handleUseInWizard = (tpl: QuestTemplate) => {
    trackAnalyticsEvent("template_selected", {
      template_id: tpl.id,
      template_name: tpl.name,
      flow: "guided-wizard",
    });
    const params = new URLSearchParams();
    if (tpl.title) params.set("title", tpl.title);
    if (tpl.description) params.set("description", tpl.description);
    if (tpl.required_grade) params.set("grade", tpl.required_grade);
    if (tpl.skills?.length) params.set("skills", tpl.skills.join(","));
    if (tpl.budget > 0) params.set("budget", String(tpl.budget));
    if (tpl.currency) params.set("currency", tpl.currency);
    if (tpl.is_urgent) params.set("urgent", "true");
    if (tpl.required_portfolio) params.set("portfolio", "true");
    params.set("template_id", tpl.id);
    params.set("template_name", tpl.name);
    router.push(`/quests/create?${params.toString()}`);
  };

  if (!isAuthenticated || (user && user.role !== "client" && user.role !== "admin")) {
    return (
      <main className="min-h-screen bg-gray-950 text-gray-200 font-inter">
        <Header />
        <div className="container mx-auto px-4 py-16 text-center">
          <p className="text-gray-400">Шаблоны доступны только заказчикам и администраторам</p>
        </div>
      </main>
    );
  }

  return (
    <main className="guild-world-shell min-h-screen bg-gray-950 text-gray-200 font-inter">
      <Header />

      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <GuildStatusStrip
          mode="profile"
          eyebrow="Blueprint archive"
          title="Шаблоны стали частью стратегического слоя публикации контрактов"
          description="Эта страница теперь визуально рифмуется с create-flow: сверху состояние архива, ниже reusable blueprints и их боевое применение."
          stats={[
            { label: "Templates", value: total, note: "в архиве", tone: "purple" },
            { label: "Visible", value: templates.length, note: "загружено сейчас", tone: "cyan" },
            { label: "Form", value: showForm ? 'OPEN' : 'HIDDEN', note: "панель создания", tone: showForm ? 'amber' : 'slate' },
            { label: "Urgent tags", value: templates.filter((template) => template.is_urgent).length, note: "срочные заготовки", tone: "emerald" },
          ]}
          signals={[
            { label: formLoading ? 'archive writing' : 'archive stable', tone: formLoading ? 'cyan' : 'slate' },
            { label: success ? 'recent template action' : 'ready for blueprinting', tone: success ? 'emerald' : 'purple' },
          ]}
          className="mb-6"
        />

        <SeasonFactionRail mode="templates" questCount={templates.length} className="mb-6" />

        {/* Title */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-cinzel font-bold text-gray-100">
              📋 Шаблоны квестов
            </h1>
            <p className="text-gray-500 text-sm mt-1 font-mono">
              Создавайте квесты быстрее с помощью шаблонов
            </p>
          </div>
          <Button
            onClick={() => setShowForm((s) => !s)}
            variant="primary"
            className="font-cinzel tracking-wider"
          >
            {showForm ? (
              <>
                <ChevronUp className="w-4 h-4 mr-2 inline" /> Скрыть
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 mr-2 inline" /> Новый шаблон
              </>
            )}
          </Button>
        </div>

        <WorldPanel
          eyebrow="Archive discipline"
          title="Единый panel primitive держит форму архива и блока создания"
          description="Секции шаблонов теперь выглядят частью одной системы с quest board и contract foundry."
          tone="purple"
          className="mb-6"
          compact
        />

        {/* Alerts */}
        {error && (
          <div className="mb-4 p-3 bg-red-950/40 border border-red-800/50 rounded text-red-400 text-sm font-mono">
            ❌ {error}
          </div>
        )}
        {success && (
          <div className="mb-4 p-3 bg-green-950/40 border border-green-800/50 rounded text-green-400 text-sm font-mono">
            ✅ {success}
          </div>
        )}

        {/* Create template form */}
        {showForm && (
          <Card className="p-0 border-none bg-transparent mb-8">
            <div className="rpg-card p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-cinzel font-bold text-amber-500">
                  {editingId ? "✏️ Редактирование шаблона" : "Новый шаблон"}
                </h2>
                {editingId && (
                  <button
                    onClick={handleCancelEdit}
                    className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition-colors"
                  >
                    <X size={16} /> Отмена
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-widest block mb-1">
                    Название шаблона *
                  </label>
                  <input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="Например: Лендинг на React"
                    className="w-full bg-black/40 border border-gray-800 focus:border-purple-600 rounded px-3 py-2 text-sm text-gray-200 outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-widest block mb-1">
                    Заголовок квеста *
                  </label>
                  <input
                    value={form.title}
                    onChange={(e) =>
                      setForm({ ...form, title: e.target.value })
                    }
                    placeholder="Разработка landing page"
                    className="w-full bg-black/40 border border-gray-800 focus:border-purple-600 rounded px-3 py-2 text-sm text-gray-200 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-gray-500 uppercase tracking-widest block mb-1">
                  Описание
                </label>
                <textarea
                  value={form.description}
                  onChange={(e) =>
                    setForm({ ...form, description: e.target.value })
                  }
                  rows={3}
                  placeholder="Подробное описание задачи..."
                  className="w-full bg-black/40 border border-gray-800 focus:border-purple-600 rounded px-3 py-2 text-sm text-gray-200 outline-none resize-none"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-widest block mb-1">
                    Мин. грейд
                  </label>
                  <select
                    value={form.required_grade}
                    onChange={(e) =>
                      setForm({ ...form, required_grade: e.target.value })
                    }
                    className="w-full bg-black/40 border border-gray-800 rounded px-3 py-2 text-sm text-gray-200 outline-none"
                  >
                    <option value="novice">Novice</option>
                    <option value="junior">Junior</option>
                    <option value="middle">Middle</option>
                    <option value="senior">Senior</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-widest block mb-1">
                    Бюджет
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={1000000}
                    value={form.budget}
                    onChange={(e) =>
                      setForm({ ...form, budget: e.target.value })
                    }
                    placeholder="10000"
                    className="w-full bg-black/40 border border-gray-800 focus:border-purple-600 rounded px-3 py-2 text-sm text-gray-200 outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-widest block mb-1">
                    Валюта
                  </label>
                  <select
                    value={form.currency}
                    onChange={(e) =>
                      setForm({ ...form, currency: e.target.value })
                    }
                    className="w-full bg-black/40 border border-gray-800 rounded px-3 py-2 text-sm text-gray-200 outline-none"
                  >
                    <option value="RUB">RUB</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs text-gray-500 uppercase tracking-widest block mb-1">
                  Навыки (через запятую)
                </label>
                <input
                  value={form.skills}
                  onChange={(e) =>
                    setForm({ ...form, skills: e.target.value })
                  }
                  placeholder="React, TypeScript, Tailwind"
                  className="w-full bg-black/40 border border-gray-800 focus:border-purple-600 rounded px-3 py-2 text-sm text-gray-200 outline-none"
                />
              </div>

              <div className="flex gap-6">
                <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_urgent}
                    onChange={(e) =>
                      setForm({ ...form, is_urgent: e.target.checked })
                    }
                    className="accent-amber-500"
                  />
                  🔥 Срочный
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.required_portfolio}
                    onChange={(e) =>
                      setForm({ ...form, required_portfolio: e.target.checked })
                    }
                    className="accent-purple-500"
                  />
                  📂 Требуется портфолио
                </label>
              </div>

              <Button
                onClick={editingId ? handleUpdate : handleCreate}
                variant="primary"
                className="w-full font-cinzel tracking-wider"
                disabled={formLoading || !form.name.trim() || !form.title.trim()}
              >
                {formLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2 inline" />
                    {editingId ? "Сохранение..." : "Создание..."}
                  </>
                ) : editingId ? (
                  "💾 Сохранить изменения"
                ) : (
                  "✨ Создать шаблон"
                )}
              </Button>
            </div>
          </Card>
        )}

        {/* Template list */}
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
          </div>
        ) : templates.length === 0 ? (
          <Card className="p-0 border-none bg-transparent">
            <div className="rpg-card p-12 text-center">
              <FileText className="w-16 h-16 text-gray-700 mx-auto mb-4" />
              <h2 className="text-xl font-cinzel font-bold text-gray-400 mb-2">
                Нет шаблонов
              </h2>
              <p className="text-gray-500 text-sm mb-4">
                Создайте первый шаблон, чтобы быстро публиковать квесты
              </p>
              {/* Recommended intent groups */}
              <div className="mt-6 text-left max-w-lg mx-auto">
                <p className="text-xs font-mono uppercase tracking-widest text-gray-500 mb-3">Рекомендуемые категории шаблонов:</p>
                <div className="grid grid-cols-2 gap-3">
                  {INTENT_GROUPS.map((g) => (
                    <div key={g.label} className="p-3 bg-gray-900/50 border border-gray-800 rounded-lg">
                      <span className="text-base mr-2">{g.icon}</span>
                      <span className="text-sm text-gray-300 font-cinzel">{g.label}</span>
                      <p className="text-xs text-gray-500 mt-1">{g.hint}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        ) : (
          <div className="space-y-4">
            <p className="text-gray-500 text-xs font-mono uppercase tracking-widest">
              Всего шаблонов: {total}
            </p>
            {templates.map((tpl) => (
              <Card key={tpl.id} className="p-0 border-none bg-transparent">
                <div className="rpg-card p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-cinzel font-bold text-gray-100 truncate">
                        {tpl.name}
                      </h3>
                      <p className="text-sm text-gray-400 mt-1 truncate">
                        Квест: {tpl.title}
                      </p>

                      <div className="flex flex-wrap gap-2 mt-3">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-cinzel font-bold border ${GRADE_COLORS[tpl.required_grade] || GRADE_COLORS.novice}`}
                        >
                          {GRADE_LABELS[tpl.required_grade] ||
                            tpl.required_grade}
                        </span>
                        {tpl.budget > 0 && (
                          <span className="px-2 py-0.5 rounded text-xs font-mono bg-amber-950/40 text-amber-500 border border-amber-800/40">
                            {tpl.budget.toLocaleString("ru-RU")} {tpl.currency}
                          </span>
                        )}
                        {tpl.is_urgent && (
                          <span className="px-2 py-0.5 rounded text-xs bg-red-950/40 text-red-400 border border-red-800/40">
                            🔥 Срочный
                          </span>
                        )}
                        {tpl.skills.length > 0 && (
                          <span className="px-2 py-0.5 rounded text-xs bg-gray-900 text-gray-400 border border-gray-800">
                            {tpl.skills.slice(0, 3).join(", ")}
                            {tpl.skills.length > 3 && ` +${tpl.skills.length - 3}`}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => handleEdit(tpl)}
                        className="p-2 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 transition-colors"
                        title="Редактировать"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleUseInWizard(tpl)}
                        className="flex items-center gap-1.5 px-4 py-2 bg-amber-800/30 hover:bg-amber-700/50 border border-amber-700/40 rounded text-sm text-amber-300 transition-colors font-cinzel"
                        title="Открыть в мастере создания"
                      >
                        <FileText className="w-4 h-4" /> В мастер
                      </button>
                      <button
                        onClick={() => handleUseTemplate(tpl.id)}
                        className="flex items-center gap-1.5 px-4 py-2 bg-purple-800/50 hover:bg-purple-700/70 border border-purple-700/40 rounded text-sm text-purple-200 transition-colors font-cinzel"
                        title="Быстро создать квест из шаблона"
                      >
                        <Rocket className="w-4 h-4" /> Быстрый квест
                      </button>
                      <button
                        onClick={() => handleDelete(tpl.id)}
                        className="p-2 text-gray-600 hover:text-red-400 transition-colors"
                        title="Удалить шаблон"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Back button */}
        <div className="mt-10">
          <Button
            onClick={() => router.push("/profile")}
            variant="secondary"
            className="border-purple-900/50 hover:border-purple-500/50 font-cinzel tracking-wider"
          >
            ← Назад к профилю
          </Button>
        </div>
      </div>
    </main>
  );
}
