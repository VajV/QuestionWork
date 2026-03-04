"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Wallet,
  Check,
  X,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import {
  adminGetPendingWithdrawals,
  adminGetTransactions,
  adminApproveWithdrawal,
  adminRejectWithdrawal,
} from "@/lib/api";
import type { AdminTransaction, AdminTransactionsResponse } from "@/types";

const PAGE_SIZE = 20;

type Tab = "pending" | "all";

const STATUS_BADGE: Record<string, { bg: string; text: string }> = {
  pending: { bg: "bg-yellow-500/20", text: "text-yellow-300" },
  completed: { bg: "bg-emerald-500/20", text: "text-emerald-300" },
  rejected: { bg: "bg-red-500/20", text: "text-red-300" },
};

export default function AdminWithdrawalsPage() {
  const [tab, setTab] = useState<Tab>("pending");
  const [data, setData] = useState<AdminTransactionsResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Action state
  const [actionId, setActionId] = useState<string | null>(null);
  const [actionType, setActionType] = useState<"approve" | "reject" | null>(
    null,
  );
  const [rejectReason, setRejectReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [toast, setToast] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);

  // Batch
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const load = useCallback(
    async (p: number, t: Tab) => {
      setLoading(true);
      setError(null);
      try {
        const r =
          t === "pending"
            ? await adminGetPendingWithdrawals(p, PAGE_SIZE)
            : await adminGetTransactions(p, PAGE_SIZE);
        setData(r);
      } catch {
        setError("Не удалось загрузить транзакции.");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    load(page, tab);
  }, [page, tab, load]);

  // Toast auto-dismiss
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const showToast = (type: "success" | "error", msg: string) =>
    setToast({ type, msg });

  const handleApprove = async (txId: string) => {
    setActionLoading(true);
    try {
      await adminApproveWithdrawal(txId);
      showToast("success", `Вывод ${txId.slice(0, 12)}… одобрен`);
      load(page, tab);
    } catch {
      showToast("error", "Ошибка при одобрении вывода.");
    } finally {
      setActionLoading(false);
      setActionId(null);
      setActionType(null);
    }
  };

  const handleReject = async (txId: string) => {
    if (rejectReason.trim().length < 5) return;
    setActionLoading(true);
    try {
      await adminRejectWithdrawal(txId, rejectReason.trim());
      showToast("success", `Вывод ${txId.slice(0, 12)}… отклонён`);
      load(page, tab);
    } catch {
      showToast("error", "Ошибка при отклонении вывода.");
    } finally {
      setActionLoading(false);
      setActionId(null);
      setActionType(null);
      setRejectReason("");
    }
  };

  const handleBatchApprove = async () => {
    if (selected.size === 0) return;
    setActionLoading(true);
    let ok = 0;
    let fail = 0;
    const ids = Array.from(selected);
    for (let i = 0; i < ids.length; i++) {
      const id = ids[i];
      try {
        await adminApproveWithdrawal(id);
        ok++;
      } catch {
        fail++;
      }
    }
    showToast(
      fail === 0 ? "success" : "error",
      `Пакетное одобрение: ${ok} успешно${fail ? `, ${fail} ошибок` : ""}`,
    );
    setSelected(new Set());
    setActionLoading(false);
    load(page, tab);
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });
  };

  const toggleAll = () => {
    if (!data) return;
    const pending = data.transactions.filter((t) => t.status === "pending");
    if (selected.size === pending.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(pending.map((t) => t.id)));
    }
  };

  const totalPages = data
    ? Math.max(1, Math.ceil(data.total / PAGE_SIZE))
    : 1;

  const txs = data?.transactions ?? [];

  return (
    <div className="space-y-6">
      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className={`fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-medium shadow-xl border ${
              toast.type === "success"
                ? "bg-emerald-900/90 border-emerald-500/40 text-emerald-200"
                : "bg-red-900/90 border-red-500/40 text-red-200"
            }`}
          >
            {toast.type === "success" ? (
              <CheckCircle2 size={16} />
            ) : (
              <XCircle size={16} />
            )}
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div>
        <h1 className="text-2xl font-cinzel font-bold text-white flex items-center gap-2">
          <Wallet size={24} className="text-yellow-400" />
          Выводы средств
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          {data ? `Всего: ${data.total}` : "Загрузка..."}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {(
          [
            { value: "pending", label: "Ожидающие" },
            { value: "all", label: "Все транзакции" },
          ] as const
        ).map((t) => (
          <button
            key={t.value}
            onClick={() => {
              setTab(t.value);
              setPage(1);
              setSelected(new Set());
            }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t.value
                ? "bg-purple-600/30 text-purple-300 border border-purple-500/30"
                : "bg-gray-800/60 text-gray-400 border border-gray-700/50 hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Batch bar */}
      {tab === "pending" && selected.size > 0 && (
        <div className="flex items-center gap-3 bg-purple-900/20 border border-purple-500/30 rounded-xl px-4 py-3">
          <span className="text-sm text-purple-300">
            Выбрано: {selected.size}
          </span>
          <button
            onClick={handleBatchApprove}
            disabled={actionLoading}
            className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs px-3 py-1.5 rounded-lg font-medium transition-colors disabled:opacity-50"
          >
            {actionLoading ? "Обработка..." : "Одобрить выбранные"}
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-xs text-gray-400 hover:text-white"
          >
            Сбросить
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle className="text-red-400 shrink-0" size={18} />
          <p className="text-red-300 text-sm">{error}</p>
        </div>
      )}

      {/* Table */}
      <div className="bg-gray-900/60 backdrop-blur-md border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-800/80 text-gray-300 text-left">
                {tab === "pending" && (
                  <th className="px-4 py-3 w-10">
                    <input
                      type="checkbox"
                      checked={
                        txs.filter((t) => t.status === "pending").length > 0 &&
                        selected.size ===
                          txs.filter((t) => t.status === "pending").length
                      }
                      onChange={toggleAll}
                      className="rounded border-gray-600 bg-gray-800 text-purple-500 focus:ring-purple-500/20"
                    />
                  </th>
                )}
                <th className="px-4 py-3 font-medium">ID</th>
                <th className="px-4 py-3 font-medium">Пользователь</th>
                <th className="px-4 py-3 font-medium">Тип</th>
                <th className="px-4 py-3 font-medium text-right">Сумма</th>
                <th className="px-4 py-3 font-medium">Статус</th>
                <th className="px-4 py-3 font-medium text-right">Дата</th>
                {tab === "pending" && (
                  <th className="px-4 py-3 font-medium text-center">
                    Действия
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-t border-gray-800/50">
                      {Array.from({
                        length: tab === "pending" ? 8 : 6,
                      }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 bg-gray-800 rounded animate-pulse" />
                        </td>
                      ))}
                    </tr>
                  ))
                : txs.map((tx: AdminTransaction, i: number) => {
                    const badge =
                      STATUS_BADGE[tx.status] ?? STATUS_BADGE.pending;
                    return (
                      <motion.tr
                        key={tx.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.03 }}
                        className="border-t border-gray-800/50 hover:bg-gray-800/40 transition-colors even:bg-gray-900/30"
                      >
                        {tab === "pending" && (
                          <td className="px-4 py-3">
                            {tx.status === "pending" && (
                              <input
                                type="checkbox"
                                checked={selected.has(tx.id)}
                                onChange={() => toggleSelect(tx.id)}
                                className="rounded border-gray-600 bg-gray-800 text-purple-500 focus:ring-purple-500/20"
                              />
                            )}
                          </td>
                        )}
                        <td className="px-4 py-3 font-mono text-xs text-gray-400">
                          {tx.id.slice(0, 12)}…
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-gray-300">
                          {tx.user_id.slice(0, 12)}…
                        </td>
                        <td className="px-4 py-3 text-gray-400">{tx.type}</td>
                        <td className="px-4 py-3 text-right font-mono font-bold text-amber-400">
                          {tx.amount} {tx.currency}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`${badge.bg} ${badge.text} text-xs px-2.5 py-1 rounded-full font-medium`}
                          >
                            {tx.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right text-gray-500 text-xs">
                          {new Date(tx.created_at).toLocaleDateString("ru")}
                        </td>
                        {tab === "pending" && (
                          <td className="px-4 py-3 text-center">
                            {tx.status === "pending" && (
                              <div className="flex items-center justify-center gap-1">
                                <button
                                  onClick={() => {
                                    setActionId(tx.id);
                                    setActionType("approve");
                                  }}
                                  className="p-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-400 transition-colors"
                                  title="Одобрить"
                                >
                                  <Check size={14} />
                                </button>
                                <button
                                  onClick={() => {
                                    setActionId(tx.id);
                                    setActionType("reject");
                                    setRejectReason("");
                                  }}
                                  className="p-1.5 rounded-lg bg-red-600/20 hover:bg-red-600/40 text-red-400 transition-colors"
                                  title="Отклонить"
                                >
                                  <X size={14} />
                                </button>
                              </div>
                            )}
                          </td>
                        )}
                      </motion.tr>
                    );
                  })}
            </tbody>
          </table>
        </div>

        {/* Empty */}
        {!loading && txs.length === 0 && (
          <div className="text-center py-12">
            <Wallet size={36} className="mx-auto text-gray-700 mb-3" />
            <p className="text-gray-500">
              {tab === "pending"
                ? "Нет ожидающих выводов"
                : "Транзакции не найдены"}
            </p>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800/50">
            <span className="text-xs text-gray-500">
              Стр. {page} из {totalPages}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 disabled:opacity-30 transition-colors"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      <AnimatePresence>
        {actionId && actionType && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => {
              setActionId(null);
              setActionType(null);
            }}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md shadow-2xl"
            >
              <h3 className="text-lg font-cinzel font-bold text-white mb-2">
                {actionType === "approve"
                  ? "Одобрить вывод?"
                  : "Отклонить вывод?"}
              </h3>
              <p className="text-sm text-gray-400 mb-4">
                Транзакция: {actionId.slice(0, 16)}…
              </p>

              {actionType === "reject" && (
                <div className="mb-4">
                  <label className="block text-xs text-gray-400 mb-1">
                    Причина отклонения (мин. 5 символов)
                  </label>
                  <textarea
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    className="w-full bg-gray-800/60 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-purple-500 outline-none resize-none h-20"
                    placeholder="Укажите причину отклонения..."
                  />
                </div>
              )}

              <div className="flex items-center gap-3 justify-end">
                <button
                  onClick={() => {
                    setActionId(null);
                    setActionType(null);
                  }}
                  className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm transition-colors border border-gray-600"
                >
                  Отмена
                </button>
                <button
                  onClick={() =>
                    actionType === "approve"
                      ? handleApprove(actionId)
                      : handleReject(actionId)
                  }
                  disabled={
                    actionLoading ||
                    (actionType === "reject" && rejectReason.trim().length < 5)
                  }
                  className={`px-4 py-2 rounded-lg text-white text-sm font-medium transition-colors disabled:opacity-50 ${
                    actionType === "approve"
                      ? "bg-emerald-600 hover:bg-emerald-700"
                      : "bg-red-600 hover:bg-red-700"
                  }`}
                >
                  {actionLoading
                    ? "Обработка..."
                    : actionType === "approve"
                      ? "Одобрить"
                      : "Отклонить"}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
