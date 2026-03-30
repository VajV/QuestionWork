"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "@/lib/motion";
import {
  FileText,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Download,
  AlertCircle,
} from "lucide-react";
import { adminGetLogs } from "@/lib/api";
import type { AdminLogEntry, AdminLogValue, AdminLogsResponse } from "@/types";
import GuildStatusStrip from "@/components/ui/GuildStatusStrip";
import WorldPanel from "@/components/ui/WorldPanel";

const PAGE_SIZE = 30;

const ACTION_COLOR: Record<string, string> = {
  withdrawal_approved: "text-emerald-400",
  withdrawal_rejected: "text-red-400",
  notification_cleanup: "text-yellow-400",
};

export default function AdminLogsPage() {
  const [data, setData] = useState<AdminLogsResponse | null>(null);
  const [page, setPage] = useState(1);
  const [adminFilter, setAdminFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const load = useCallback(
    async (p: number, admin: string) => {
      setLoading(true);
      setError(null);
      try {
        const r = await adminGetLogs(p, PAGE_SIZE, admin || undefined);
        setData(r);
      } catch {
        setError("Не удалось загрузить логи.");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    load(page, adminFilter);
  }, [page, adminFilter, load]);

  const uniqueActions = useMemo(() => {
    if (!data?.logs) return [];
    const actions = data.logs.map((l) => l.action);
    return actions.filter((a, i) => actions.indexOf(a) === i).sort();
  }, [data]);

  const filtered = useMemo(() => {
    if (!data?.logs) return [];
    let list = data.logs;
    if (actionFilter) {
      list = list.filter((l) => l.action === actionFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (l) =>
          l.action.toLowerCase().includes(q) ||
          l.target_id.toLowerCase().includes(q) ||
          l.admin_id.toLowerCase().includes(q),
      );
    }
    return list;
  }, [data, actionFilter, search]);

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const s = new Set(prev);
      if (s.has(id)) { s.delete(id); } else { s.add(id); }
      return s;
    });
  };

  const exportCsv = () => {
    if (!filtered.length) return;
    const headers = [
      "ID",
      "Admin ID",
      "Action",
      "Target Type",
      "Target ID",
      "IP",
      "Created At",
      "Old Value",
      "New Value",
    ];
    const rows = filtered.map((l) => [
      l.id,
      l.admin_id,
      l.action,
      l.target_type,
      l.target_id,
      l.ip_address ?? "",
      l.created_at,
      serializeLogPayload(l.old_value),
      serializeLogPayload(l.new_value),
    ]);
    const csv = [headers, ...rows]
      .map((r) =>
        r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","),
      )
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `admin_logs_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const totalPages = data
    ? Math.max(1, Math.ceil(data.total / PAGE_SIZE))
    : 1;

  const serializeLogPayload = (value: AdminLogValue | null): string => {
    if (value === null) return "";
    if (typeof value === "string") return value;
    return JSON.stringify(value);
  };

  const formatLogPayload = (value: AdminLogValue | null): string => {
    if (value === null) return "—";
    if (typeof value === "string") return value;
    return JSON.stringify(value, null, 2);
  };

  return (
    <div className="space-y-6">
      <GuildStatusStrip
        mode="ops"
        eyebrow="Ops audit"
        title="Аудит-лог вынесен в верхний контрольный слой перед сырыми записями"
        description="Контекст по объёму, фильтрам и выбранному режиму виден до таблицы, поэтому ops-аудит читается как command-center, а не как просто dump записей."
        stats={[
          { label: "Total", value: data?.total ?? 0, note: "всего записей", tone: "ops" },
          { label: "Visible", value: filtered.length, note: "после фильтров", tone: "cyan" },
          { label: "Actions", value: uniqueActions.length, note: "типов действий", tone: "purple" },
          { label: "Page", value: `${page}/${totalPages}`, note: "позиция", tone: "slate" },
        ]}
        signals={[
          { label: actionFilter || 'all actions', tone: actionFilter ? 'amber' : 'slate' },
          { label: search.trim() ? 'forensic search active' : 'forensic overview', tone: search.trim() ? 'cyan' : 'emerald' },
        ]}
      />

      <WorldPanel
        eyebrow="Forensic control"
        title="Поиск, admin filter и export приведены к единому ops-panel языку"
        description="Так журналы продолжают ту же визуальную логику, что dashboard, users, quests и withdrawals."
        tone="ops"
        compact
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-cinzel font-bold text-white flex items-center gap-2">
            <FileText size={24} className="text-gray-400" />
            Аудит логи
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            {data ? `Всего записей: ${data.total}` : "Загрузка..."}
          </p>
        </div>
        <button
          onClick={exportCsv}
          disabled={!filtered.length}
          className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 text-gray-300 text-xs px-3 py-2 rounded-lg transition-colors disabled:opacity-30"
        >
          <Download size={14} />
          CSV
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
          />
          <input
            type="text"
            placeholder="Поиск..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-gray-800/60 border border-gray-600 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition"
          />
        </div>
        <input
          type="text"
          placeholder="Фильтр по Admin ID..."
          value={adminFilter}
          onChange={(e) => {
            setAdminFilter(e.target.value);
            setPage(1);
          }}
          className="bg-gray-800/60 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:border-purple-500 outline-none max-w-xs"
        />
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="bg-gray-800/60 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-300 focus:border-purple-500 outline-none"
        >
          <option value="">Все действия</option>
          {uniqueActions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
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
                <th className="px-4 py-3 w-8"></th>
                <th className="px-4 py-3 font-medium">Время</th>
                <th className="px-4 py-3 font-medium">Админ</th>
                <th className="px-4 py-3 font-medium">Действие</th>
                <th className="px-4 py-3 font-medium">Тип цели</th>
                <th className="px-4 py-3 font-medium">ID цели</th>
                <th className="px-4 py-3 font-medium">IP</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-t border-gray-800/50">
                      {Array.from({ length: 7 }).map((_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 bg-gray-800 rounded animate-pulse" />
                        </td>
                      ))}
                    </tr>
                  ))
                : filtered.map((log: AdminLogEntry, i: number) => {
                    const isOpen = expanded.has(log.id);
                    return (
                      <motion.tr
                        key={log.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.02 }}
                        className="data-table-row cursor-pointer border-t border-gray-800/50 hover:bg-gray-800/40 even:bg-gray-900/30"
                        onClick={() => toggleExpand(log.id)}
                      >
                        <td className="px-4 py-3 text-gray-600">
                          {isOpen ? (
                            <ChevronUp size={14} />
                          ) : (
                            <ChevronDown size={14} />
                          )}
                        </td>
                        <td className="px-4 py-3 text-gray-400 text-xs font-mono whitespace-nowrap">
                          {new Date(log.created_at).toLocaleString("ru")}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-gray-300">
                          {log.admin_id.slice(0, 12)}
                        </td>
                        <td
                          className={`px-4 py-3 font-medium ${ACTION_COLOR[log.action] ?? "text-gray-300"}`}
                        >
                          {log.action}
                        </td>
                        <td className="px-4 py-3 text-gray-400">
                          {log.target_type}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-gray-400">
                          {log.target_id.slice(0, 16)}
                        </td>
                        <td className="px-4 py-3 text-gray-500 text-xs font-mono">
                          {log.ip_address ?? "—"}
                        </td>
                      </motion.tr>
                    );
                  })}
            </tbody>
          </table>
        </div>

        {/* Expanded detail rows */}
        <AnimatePresence>
          {filtered
            .filter((l) => expanded.has(l.id))
            .map((log) => (
              <motion.div
                key={`detail-${log.id}`}
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="border-t border-gray-800/50 bg-gray-800/20 overflow-hidden"
              >
                <div className="px-6 py-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <span className="text-xs text-gray-500 uppercase tracking-wider block mb-1">
                      Old Value
                    </span>
                    <pre className="text-xs text-gray-400 bg-gray-900/60 rounded-lg p-3 overflow-x-auto max-h-48 font-mono">
                      {formatLogPayload(log.old_value)}
                    </pre>
                  </div>
                  <div>
                    <span className="text-xs text-gray-500 uppercase tracking-wider block mb-1">
                      New Value
                    </span>
                    <pre className="text-xs text-emerald-400/80 bg-gray-900/60 rounded-lg p-3 overflow-x-auto max-h-48 font-mono">
                      {formatLogPayload(log.new_value)}
                    </pre>
                  </div>
                </div>
              </motion.div>
            ))}
        </AnimatePresence>

        {/* Empty */}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-12">
            <FileText size={36} className="mx-auto text-gray-700 mb-3" />
            <p className="text-gray-500">Логи не найдены</p>
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
    </div>
  );
}
