"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "@/lib/motion";
import {
  X,
  Save,
  XCircle as CancelIcon,
  CheckCircle,
  Trash2,
  Loader2,
  XCircle,
  AlertTriangle,
} from "lucide-react";
import {
  adminGetQuestDetail,
  adminUpdateQuest,
  adminForceCancel,
  adminForceComplete,
  adminDeleteQuest,
} from "@/lib/api";
import type { ApiError } from "@/lib/api";
import type { AdminQuestDetail } from "@/types";

interface Props {
  questId: string;
  onClose: () => void;
  onUpdated: () => void;
}

function getApiErrorMessage(error: unknown, fallback = "Ошибка"): string {
  const apiError = error as Partial<ApiError>;
  if (typeof apiError.detail === "string" && apiError.detail.trim()) {
    return apiError.detail;
  }
  if (typeof apiError.message === "string" && apiError.message.trim()) {
    return apiError.message;
  }
  return fallback;
}

function Toast({ msg, type }: { msg: string; type: "ok" | "err" }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className={`fixed top-4 right-4 z-[200] flex items-center gap-2 rounded-lg px-4 py-3 text-sm shadow-lg ${
        type === "ok" ? "bg-green-600/90 text-white" : "bg-red-600/90 text-white"
      }`}
    >
      {type === "ok" ? <CheckCircle size={16} /> : <XCircle size={16} />}
      {msg}
    </motion.div>
  );
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  open: { label: "Открыт", color: "text-green-400" },
  assigned: { label: "Назначен", color: "text-cyan-300" },
  in_progress: { label: "В работе", color: "text-blue-400" },
  completed: { label: "Выполнен", color: "text-yellow-400" },
  revision_requested: { label: "На доработке", color: "text-orange-300" },
  confirmed: { label: "Подтверждён", color: "text-purple-400" },
  cancelled: { label: "Отменён", color: "text-red-400" },
};

export default function EditQuestModal({ questId, onClose, onUpdated }: Props) {
  const [quest, setQuest] = useState<AdminQuestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);

  // Edit fields
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState(0);
  const [xpReward, setXpReward] = useState(0);
  const [requiredGrade, setRequiredGrade] = useState("novice");
  const [isUrgent, setIsUrgent] = useState(false);
  const [requiredPortfolio, setRequiredPortfolio] = useState(false);

  // Force action
  const [forceReason, setForceReason] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  const flash = useCallback((msg: string, type: "ok" | "err") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const loadQuest = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminGetQuestDetail(questId);
      setQuest(data);
      setTitle(data.title);
      setDescription(data.description);
      setBudget(data.budget);
      setXpReward(data.xp_reward);
      setRequiredGrade(data.required_grade);
      setIsUrgent(data.is_urgent);
      setRequiredPortfolio(data.required_portfolio);
    } catch {
      flash("Не удалось загрузить квест", "err");
    } finally {
      setLoading(false);
    }
  }, [questId, flash]);

  useEffect(() => {
    loadQuest();
  }, [loadQuest]);

  const handleSave = async () => {
    if (!quest) return;
    setSaving(true);
    try {
      const fields: Record<string, unknown> = {};
      if (title !== quest.title) fields.title = title;
      if (description !== quest.description) fields.description = description;
      if (budget !== quest.budget) fields.budget = budget;
      if (xpReward !== quest.xp_reward) fields.xp_reward = xpReward;
      if (requiredGrade !== quest.required_grade) fields.required_grade = requiredGrade;
      if (isUrgent !== quest.is_urgent) fields.is_urgent = isUrgent;
      if (requiredPortfolio !== quest.required_portfolio) fields.required_portfolio = requiredPortfolio;
      if (Object.keys(fields).length === 0) {
        flash("Нет изменений", "err"); return;
      }
      await adminUpdateQuest(questId, fields);
      flash("Квест обновлён", "ok");
      await loadQuest();
      onUpdated();
    } catch (e: unknown) {
      flash(getApiErrorMessage(e), "err");
    } finally {
      setSaving(false);
    }
  };

  const handleForceCancel = async () => {
    if (forceReason.length < 3) { flash("Введите причину (мин. 3 символа)", "err"); return; }
    if (!window.confirm("Вы уверены? Квест будет принудительно отменён.")) return;
    setSaving(true);
    try {
      const r = await adminForceCancel(questId, forceReason);
      flash(`Статус: ${r.old_status} → cancelled`, "ok");
      setForceReason("");
      await loadQuest();
      onUpdated();
    } catch (e: unknown) {
      flash(getApiErrorMessage(e), "err");
    } finally {
      setSaving(false);
    }
  };

  const handleForceComplete = async () => {
    if (forceReason.length < 3) { flash("Введите причину (мин. 3 символа)", "err"); return; }
    if (!window.confirm("Вы уверены? Квест будет принудительно завершён и фрилансеру начислена оплата.")) return;
    setSaving(true);
    try {
      const r = await adminForceComplete(questId, forceReason);
      flash(`Статус: ${r.old_status} → confirmed`, "ok");
      setForceReason("");
      await loadQuest();
      onUpdated();
    } catch (e: unknown) {
      flash(getApiErrorMessage(e), "err");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) { setDeleteConfirm(true); return; }
    setSaving(true);
    try {
      await adminDeleteQuest(questId);
      flash("Квест удалён", "ok");
      onUpdated();
      setTimeout(onClose, 1000);
    } catch (e: unknown) {
      flash(getApiErrorMessage(e), "err");
    } finally {
      setSaving(false);
      setDeleteConfirm(false);
    }
  };

  const inputCls = "w-full rounded-lg border border-gray-600 bg-gray-700 px-3 py-2 text-sm text-gray-100 focus:border-purple-500 focus:outline-none";
  const btnPrimary = "inline-flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50";
  const btnDanger = "inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50";
  const btnWarning = "inline-flex items-center gap-2 rounded-lg bg-yellow-600 px-4 py-2 text-sm font-medium text-white hover:bg-yellow-700 disabled:opacity-50";
  const btnSecondary = "inline-flex items-center gap-2 rounded-lg border border-gray-600 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-700 disabled:opacity-50";
  const labelCls = "block text-xs font-medium text-gray-400 mb-1";

  return (
    <>
      <AnimatePresence>{toast && <Toast msg={toast.msg} type={toast.type} />}</AnimatePresence>

      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-gray-700 bg-gray-800 shadow-2xl"
        >
          {/* Header */}
          <div className="sticky top-0 z-10 flex items-center justify-between border-b border-gray-700 bg-gray-800/95 px-6 py-4 backdrop-blur">
            <div>
              <h2 className="text-lg font-bold text-white">
                {quest ? quest.title : "Загрузка…"}
              </h2>
              {quest && (
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <span>ID: {quest.id}</span>
                  <span className={STATUS_LABELS[quest.status]?.color || "text-gray-400"}>
                    {STATUS_LABELS[quest.status]?.label || quest.status}
                  </span>
                  {quest.is_urgent && <span className="text-orange-400">🔥 Срочный</span>}
                </div>
              )}
            </div>
            <button onClick={onClose} className="rounded-lg p-2 text-gray-400 hover:bg-gray-700 hover:text-white">
              <X size={20} />
            </button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="animate-spin text-purple-400" size={32} />
            </div>
          ) : quest ? (
            <div className="space-y-6 p-6">
              {/* Edit fields */}
              <div className="space-y-4">
                <div>
                  <label className={labelCls}>Название</label>
                  <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>Описание</label>
                  <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} className={inputCls} />
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className={labelCls}>Бюджет</label>
                    <input type="number" min={100} max={1000000} value={budget} onChange={(e) => setBudget(+e.target.value)} className={inputCls} />
                  </div>
                  <div>
                    <label className={labelCls}>XP Награда</label>
                    <input type="number" min={10} max={500} value={xpReward} onChange={(e) => setXpReward(+e.target.value)} className={inputCls} />
                  </div>
                  <div>
                    <label className={labelCls}>Грейд</label>
                    <select value={requiredGrade} onChange={(e) => setRequiredGrade(e.target.value)} className={inputCls}>
                      <option value="novice">Novice</option>
                      <option value="junior">Junior</option>
                      <option value="middle">Middle</option>
                      <option value="senior">Senior</option>
                    </select>
                  </div>
                </div>
                <div className="flex gap-6">
                  <label className="flex items-center gap-2 text-sm text-gray-300">
                    <input type="checkbox" checked={isUrgent} onChange={(e) => setIsUrgent(e.target.checked)} className="rounded border-gray-600 bg-gray-700" />
                    Срочный
                  </label>
                  <label className="flex items-center gap-2 text-sm text-gray-300">
                    <input type="checkbox" checked={requiredPortfolio} onChange={(e) => setRequiredPortfolio(e.target.checked)} className="rounded border-gray-600 bg-gray-700" />
                    Портфолио
                  </label>
                </div>
                <button onClick={handleSave} disabled={saving} className={btnPrimary}>
                  {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                  Сохранить изменения
                </button>
              </div>

              {/* Applications */}
              {quest.applications.length > 0 && (
                <div className="rounded-lg border border-gray-700 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-gray-300">
                    Заявки ({quest.applications.length})
                  </h3>
                  <div className="space-y-2 max-h-40 overflow-y-auto">
                    {quest.applications.map((app) => (
                      <div key={app.id} className="flex items-center justify-between rounded-lg bg-gray-700/50 px-3 py-2 text-xs">
                        <div>
                          <span className="font-medium text-white">{app.freelancer_username}</span>
                          <span className="ml-2 text-gray-400">{app.freelancer_grade}</span>
                        </div>
                        {app.proposed_price && (
                          <span className="text-green-400">{app.proposed_price}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(quest.delivery_note || quest.delivery_url || quest.delivery_submitted_at || quest.revision_reason) && (
                <div className="rounded-lg border border-cyan-900/40 bg-cyan-950/10 p-4 text-sm text-gray-300 space-y-3">
                  <h3 className="font-semibold text-cyan-300">Сдача и правки</h3>
                  {quest.delivery_submitted_at && (
                    <div>
                      <span className="text-gray-500">Сдано:</span>{" "}
                      {new Date(quest.delivery_submitted_at).toLocaleString("ru-RU")}
                    </div>
                  )}
                  {quest.delivery_note && (
                    <div className="whitespace-pre-wrap rounded-lg border border-cyan-900/30 bg-black/20 p-3">
                      {quest.delivery_note}
                    </div>
                  )}
                  {quest.delivery_url && (() => { try { const p = new URL(quest.delivery_url).protocol; return p === 'http:' || p === 'https:'; } catch { return false; } })() && (
                    <a href={quest.delivery_url} target="_blank" rel="noreferrer" className="text-cyan-300 hover:text-cyan-200 underline">
                      Открыть результат
                    </a>
                  )}
                  {quest.revision_reason && (
                    <div className="rounded-lg border border-orange-900/40 bg-orange-950/20 p-3 text-orange-200 whitespace-pre-wrap">
                      <div className="mb-1 text-xs uppercase tracking-wider text-orange-400">Причина доработки</div>
                      {quest.revision_reason}
                      {quest.revision_requested_at && (
                        <div className="mt-2 text-xs text-orange-400/80">
                          {new Date(quest.revision_requested_at).toLocaleString("ru-RU")}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Force actions */}
              <div className="rounded-lg border border-red-800/50 bg-red-900/10 p-4">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-red-400">
                  <AlertTriangle size={16} /> Принудительные действия
                </h3>
                <div className="mb-3">
                  <label className={labelCls}>Причина (для отмены/завершения)</label>
                  <input value={forceReason} onChange={(e) => setForceReason(e.target.value)} placeholder="Причина..." className={inputCls} />
                </div>
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={handleForceCancel}
                    disabled={saving || quest.status === "cancelled"}
                    className={btnDanger}
                  >
                    {saving ? <Loader2 size={16} className="animate-spin" /> : <CancelIcon size={16} />}
                    Принудительная отмена
                  </button>
                  <button
                    onClick={handleForceComplete}
                    disabled={saving || quest.status === "confirmed" || quest.status === "cancelled"}
                    className={btnWarning}
                  >
                    {saving ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />}
                    Принудительное завершение
                  </button>
                  <button
                    onClick={handleDelete}
                    disabled={saving}
                    className={btnDanger}
                  >
                    {saving ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                    {deleteConfirm ? "Подтвердить удаление" : "Удалить квест"}
                  </button>
                  {deleteConfirm && (
                    <button onClick={() => setDeleteConfirm(false)} className={btnSecondary}>
                      Отмена
                    </button>
                  )}
                </div>
              </div>

              {/* Meta info */}
              <div className="grid grid-cols-2 gap-3 text-xs text-gray-400">
                <div>Клиент: <span className="text-white">{quest.client_username}</span></div>
                <div>Исполнитель: <span className="text-white">{quest.assigned_to || "—"}</span></div>
                <div>Создан: <span className="text-white">{new Date(quest.created_at).toLocaleString()}</span></div>
                {quest.completed_at && (
                  <div>Завершён: <span className="text-white">{new Date(quest.completed_at).toLocaleString()}</span></div>
                )}
                {quest.delivery_submitted_at && (
                  <div>Результат сдан: <span className="text-white">{new Date(quest.delivery_submitted_at).toLocaleString()}</span></div>
                )}
              </div>

              {(quest.delivery_note || quest.delivery_url) && (
                <div className="rounded-lg border border-cyan-800/40 bg-cyan-950/10 p-4 text-sm">
                  <h3 className="mb-2 font-semibold text-cyan-300">Сдача результата</h3>
                  {quest.delivery_note && (
                    <p className="whitespace-pre-wrap text-gray-300">{quest.delivery_note}</p>
                  )}
                  {quest.delivery_url && (() => { try { const p = new URL(quest.delivery_url).protocol; return p === 'http:' || p === 'https:'; } catch { return false; } })() && (
                    <a
                      href={quest.delivery_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-block text-cyan-300 hover:text-cyan-200 underline"
                    >
                      Открыть результат
                    </a>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center py-20 text-red-400">
              Квест не найден
            </div>
          )}
        </motion.div>
      </div>
    </>
  );
}
