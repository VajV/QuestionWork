"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ScrollText,
  Search,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  AlertCircle,
  Flame,
  Pencil,
} from "lucide-react";
import { getQuests } from "@/lib/api";
import type { Quest, QuestStatus } from "@/lib/api";
import EditQuestModal from "@/components/admin/EditQuestModal";

const PAGE_SIZE = 20;

const STATUS_TABS: { value: QuestStatus | ""; label: string }[] = [
  { value: "", label: "Все" },
  { value: "open", label: "Открытые" },
  { value: "in_progress", label: "В работе" },
  { value: "completed", label: "Завершённые" },
  { value: "confirmed", label: "Подтверждённые" },
  { value: "cancelled", label: "Отменённые" },
];

const STATUS_BADGE: Record<string, { bg: string; text: string }> = {
  open: { bg: "bg-green-500/20", text: "text-green-300" },
  in_progress: { bg: "bg-blue-500/20", text: "text-blue-300" },
  completed: { bg: "bg-yellow-500/20", text: "text-yellow-300" },
  confirmed: { bg: "bg-emerald-500/20", text: "text-emerald-300" },
  cancelled: { bg: "bg-red-500/20", text: "text-red-300" },
};

export default function AdminQuestsPage() {
  const [quests, setQuests] = useState<Quest[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<QuestStatus | "">("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editQuestId, setEditQuestId] = useState<string | null>(null);

  const load = useCallback(
    async (p: number, status: QuestStatus | "") => {
      setLoading(true);
      setError(null);
      try {
        const r = await getQuests(p, PAGE_SIZE, status ? { status } : undefined);
        setQuests(r.quests);
        setTotal(r.total);
      } catch {
        setError("Не удалось загрузить квесты.");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    load(page, statusFilter);
  }, [page, statusFilter, load]);

  const filtered = useMemo(() => {
    if (!search.trim()) return quests;
    const q = search.toLowerCase();
    return quests.filter(
      (quest) =>
        quest.title.toLowerCase().includes(q) ||
        quest.client_username?.toLowerCase().includes(q),
    );
  }, [quests, search]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-cinzel font-bold text-white flex items-center gap-2">
          <ScrollText size={24} className="text-emerald-400" />
          Квесты
        </h1>
        <p className="text-gray-500 text-sm mt-1">Всего: {total}</p>
      </div>

      {/* Status tabs */}
      <div className="flex flex-wrap gap-2">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => {
              setStatusFilter(tab.value as QuestStatus | "");
              setPage(1);
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              statusFilter === tab.value
                ? "bg-purple-600/30 text-purple-300 border border-purple-500/30"
                : "bg-gray-800/60 text-gray-400 border border-gray-700/50 hover:text-white hover:bg-gray-800"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
        />
        <input
          type="text"
          placeholder="Поиск по названию или клиенту..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-gray-800/60 border border-gray-600 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition"
        />
      </div>

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
                <th className="px-4 py-3 font-medium">Название</th>
                <th className="px-4 py-3 font-medium">Клиент</th>
                <th className="px-4 py-3 font-medium">Исполнитель</th>
                <th className="px-4 py-3 font-medium text-right">Бюджет</th>
                <th className="px-4 py-3 font-medium">Статус</th>
                <th className="px-4 py-3 font-medium">Грейд</th>
                <th className="px-4 py-3 font-medium text-right">Создан</th>
                <th className="px-4 py-3 font-medium text-center">Действия</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-t border-gray-800/50">
                      {Array.from({ length: 8 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 bg-gray-800 rounded animate-pulse" />
                        </td>
                      ))}
                    </tr>
                  ))
                : filtered.map((q, i) => {
                    const badge = STATUS_BADGE[q.status] ?? STATUS_BADGE.open;
                    return (
                      <motion.tr
                        key={q.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.03 }}
                        className="border-t border-gray-800/50 hover:bg-gray-800/40 transition-colors even:bg-gray-900/30"
                      >
                        <td className="px-4 py-3 font-medium text-white max-w-[200px] truncate">
                          {q.is_urgent && (
                            <Flame
                              size={14}
                              className="inline mr-1 text-orange-400"
                            />
                          )}
                          {q.title}
                        </td>
                        <td className="px-4 py-3 text-gray-400">
                          {q.client_username ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-gray-400">
                          {q.assigned_to ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-amber-400">
                          {q.budget.toLocaleString()} {q.currency}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`${badge.bg} ${badge.text} text-xs px-2.5 py-1 rounded-full font-medium`}
                          >
                            {q.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs font-mono text-gray-400 uppercase">
                          {q.required_grade}
                        </td>
                        <td className="px-4 py-3 text-right text-gray-500 text-xs">
                          {new Date(q.created_at).toLocaleDateString("ru")}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <div className="flex items-center justify-center gap-2">
                            <button
                              onClick={() => setEditQuestId(q.id)}
                              className="inline-flex items-center gap-1 rounded-lg bg-purple-600/20 px-2.5 py-1.5 text-xs font-medium text-purple-300 hover:bg-purple-600/40 transition-colors"
                              title="Редактировать"
                            >
                              <Pencil size={12} /> Изм.
                            </button>
                            <Link
                              href={`/quests/${q.id}`}
                              className="text-gray-500 hover:text-purple-400 transition-colors"
                              title="Открыть квест"
                            >
                              <ExternalLink size={14} />
                            </Link>
                          </div>
                        </td>
                      </motion.tr>
                    );
                  })}
            </tbody>
          </table>
        </div>

        {/* Empty */}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-12">
            <ScrollText size={36} className="mx-auto text-gray-700 mb-3" />
            <p className="text-gray-500">Квесты не найдены</p>
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

      {/* Edit Quest Modal */}
      {editQuestId && (
        <EditQuestModal
          questId={editQuestId}
          onClose={() => setEditQuestId(null)}
          onUpdated={() => load(page, statusFilter)}
        />
      )}
    </div>
  );
}
