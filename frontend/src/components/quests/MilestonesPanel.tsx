"use client";

import { useEffect, useState } from "react";
import {
  getMilestones,
  createMilestone,
  activateMilestone,
  completeMilestone,
  deleteMilestone,
  Milestone,
  MilestoneCreate,
  isApiError,
} from "@/lib/api";

interface Props {
  questId: string;
  /** "client" can create/activate/delete; "freelancer" can view */
  role: "client" | "freelancer" | "admin";
  currency?: string;
  className?: string;
}

const STATUS_LABEL: Record<string, string> = {
  draft: "Черновик",
  active: "Активен",
  completed: "Завершён",
  cancelled: "Отменён",
};

const STATUS_COLOR: Record<string, string> = {
  draft: "text-white/40",
  active: "text-indigo-400",
  completed: "text-green-400",
  cancelled: "text-red-400",
};

export function MilestonesPanel({ questId, role, currency = "RUB", className = "" }: Props) {
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  // Create form state
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<MilestoneCreate>({ title: "", amount: 0, currency });

  const load = async () => {
    try {
      const data = await getMilestones(questId);
      setMilestones(data);
    } catch (err) {
      setError(isApiError(err) ? (err.detail ?? err.message) : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [questId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCreate = async () => {
    if (!form.title.trim() || form.amount <= 0) return;
    setBusy("create");
    setActionError(null);
    try {
      const m = await createMilestone(questId, { ...form, currency });
      setMilestones((prev) => [...prev, m]);
      setForm({ title: "", amount: 0, currency });
      setShowForm(false);
    } catch (err) {
      setActionError(isApiError(err) ? (err.detail ?? err.message) : "Ошибка создания");
    } finally {
      setBusy(null);
    }
  };

  const handleActivate = async (id: string) => {
    setBusy(id); setActionError(null);
    try {
      const updated = await activateMilestone(questId, id);
      setMilestones((prev) => prev.map((m) => (m.id === id ? updated : m)));
    } catch (err) {
      setActionError(isApiError(err) ? (err.detail ?? err.message) : "Ошибка активации");
    } finally { setBusy(null); }
  };

  const handleComplete = async (id: string) => {
    setBusy(id); setActionError(null);
    try {
      const updated = await completeMilestone(questId, id);
      setMilestones((prev) => prev.map((m) => (m.id === id ? updated : m)));
    } catch (err) {
      setActionError(isApiError(err) ? (err.detail ?? err.message) : "Ошибка завершения");
    } finally { setBusy(null); }
  };

  const handleDelete = async (id: string) => {
    setBusy(id); setActionError(null);
    try {
      await deleteMilestone(questId, id);
      setMilestones((prev) => prev.filter((m) => m.id !== id));
    } catch (err) {
      setActionError(isApiError(err) ? (err.detail ?? err.message) : "Ошибка удаления");
    } finally { setBusy(null); }
  };

  return (
    <div className={`rounded-xl border border-white/10 bg-white/5 p-4 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-white flex items-center gap-2">
          <span>🎯</span> Этапы (Milestones)
        </h3>
        {(role === "client" || role === "admin") && (
          <button
            onClick={() => setShowForm((v) => !v)}
            className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            {showForm ? "Отмена" : "+ Добавить"}
          </button>
        )}
      </div>

      {loading && <div className="h-16 rounded bg-white/5 animate-pulse" />}
      {error && <p className="text-red-400 text-sm">{error}</p>}
      {actionError && <p className="text-red-400 text-sm mb-2">{actionError}</p>}

      {!loading && !error && milestones.length === 0 && !showForm && (
        <p className="text-white/40 text-sm text-center py-4">Этапов нет</p>
      )}

      <div className="space-y-3">
        {milestones.map((m) => (
          <div key={m.id} className="flex items-start justify-between gap-2 rounded-lg border border-white/5 bg-white/3 p-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-medium ${STATUS_COLOR[m.status] ?? "text-white/50"}`}>
                  {STATUS_LABEL[m.status] ?? m.status}
                </span>
                <span className="text-sm text-white truncate">{m.title}</span>
              </div>
              {m.description && <p className="text-xs text-white/40 mt-0.5">{m.description}</p>}
              <p className="text-xs text-indigo-300 mt-1 tabular-nums">
                {m.amount.toLocaleString()} {m.currency}
              </p>
            </div>
            {(role === "client" || role === "admin") && (
              <div className="flex flex-col gap-1 shrink-0">
                {m.status === "draft" && (
                  <>
                    <button
                      onClick={() => handleActivate(m.id)}
                      disabled={busy === m.id}
                      className="text-xs px-2 py-0.5 rounded bg-indigo-600/50 hover:bg-indigo-600 text-white disabled:opacity-50 transition-colors"
                    >
                      Активировать
                    </button>
                    <button
                      onClick={() => handleDelete(m.id)}
                      disabled={busy === m.id}
                      className="text-xs px-2 py-0.5 rounded bg-red-900/40 hover:bg-red-800/60 text-red-400 disabled:opacity-50 transition-colors"
                    >
                      Удалить
                    </button>
                  </>
                )}
                {m.status === "active" && (
                  <button
                    onClick={() => handleComplete(m.id)}
                    disabled={busy === m.id}
                    className="text-xs px-2 py-0.5 rounded bg-green-700/50 hover:bg-green-700 text-white disabled:opacity-50 transition-colors"
                  >
                    Завершить
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {showForm && (
        <div className="mt-4 rounded-lg border border-white/10 bg-white/5 p-3 space-y-2">
          <input
            type="text"
            placeholder="Название этапа"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            className="w-full rounded bg-white/10 border border-white/10 px-3 py-1.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-indigo-500"
          />
          <input
            type="number"
            placeholder={`Сумма (${currency})`}
            min={0}
            value={form.amount || ""}
            onChange={(e) => setForm((f) => ({ ...f, amount: parseFloat(e.target.value) || 0 }))}
            className="w-full rounded bg-white/10 border border-white/10 px-3 py-1.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-indigo-500"
          />
          <textarea
            placeholder="Описание (опционально)"
            rows={2}
            value={form.description ?? ""}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            className="w-full rounded bg-white/10 border border-white/10 px-3 py-1.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-indigo-500 resize-none"
          />
          <button
            onClick={handleCreate}
            disabled={busy === "create" || !form.title.trim() || form.amount <= 0}
            className="w-full py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
          >
            {busy === "create" ? "Создание..." : "Создать этап"}
          </button>
        </div>
      )}
    </div>
  );
}
