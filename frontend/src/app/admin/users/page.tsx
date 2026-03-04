"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Users as UsersIcon,
  AlertCircle,
  Pencil,
  Ban,
  ShieldAlert,
} from "lucide-react";
import { adminGetUsers } from "@/lib/api";
import type { AdminUserRow, AdminUsersResponse } from "@/types";
import EditUserModal from "@/components/admin/EditUserModal";

const PAGE_SIZE = 20;

const ROLE_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  admin: { bg: "bg-purple-500/20", text: "text-purple-300", label: "Админ" },
  client: { bg: "bg-blue-500/20", text: "text-blue-300", label: "Клиент" },
  freelancer: {
    bg: "bg-emerald-500/20",
    text: "text-emerald-300",
    label: "Фрилансер",
  },
};

const GRADE_COLOR: Record<string, string> = {
  novice: "text-gray-400",
  junior: "text-green-400",
  middle: "text-blue-400",
  senior: "text-purple-400",
};

export default function AdminUsersPage() {
  const [data, setData] = useState<AdminUsersResponse | null>(null);
  const [page, setPage] = useState(1);
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editUserId, setEditUserId] = useState<string | null>(null);

  const load = useCallback(async (p: number, role: string) => {
    setLoading(true);
    setError(null);
    try {
      const r = await adminGetUsers(p, PAGE_SIZE, role || undefined);
      setData(r);
    } catch {
      setError("Не удалось загрузить список пользователей.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(page, roleFilter);
  }, [page, roleFilter, load]);

  const filtered = useMemo(() => {
    if (!data?.users || !search.trim()) return data?.users ?? [];
    const q = search.toLowerCase();
    return data.users.filter(
      (u) =>
        u.username.toLowerCase().includes(q) ||
        (u.email && u.email.toLowerCase().includes(q)),
    );
  }, [data, search]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-cinzel font-bold text-white flex items-center gap-2">
          <UsersIcon size={24} className="text-blue-400" />
          Пользователи
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          {data ? `Всего: ${data.total}` : "Загрузка..."}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
          />
          <input
            type="text"
            placeholder="Поиск по имени или email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-gray-800/60 border border-gray-600 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 outline-none transition"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => {
            setRoleFilter(e.target.value);
            setPage(1);
          }}
          className="bg-gray-800/60 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-300 focus:border-purple-500 outline-none"
        >
          <option value="">Все роли</option>
          <option value="client">Клиент</option>
          <option value="freelancer">Фрилансер</option>
          <option value="admin">Админ</option>
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
                <th className="px-4 py-3 font-medium">Пользователь</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Роль</th>
                <th className="px-4 py-3 font-medium">Грейд</th>
                <th className="px-4 py-3 font-medium text-center">Ур.</th>
                <th className="px-4 py-3 font-medium text-right">XP</th>
                <th className="px-4 py-3 font-medium text-right">Регистрация</th>
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
                : filtered.map((u: AdminUserRow, i: number) => (
                    <motion.tr
                      key={u.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.03 }}
                      className="border-t border-gray-800/50 hover:bg-gray-800/40 transition-colors even:bg-gray-900/30"
                    >
                      <td className="px-4 py-3 font-medium text-white">
                        <div className="flex items-center gap-2">
                          {u.username}
                          {u.is_banned && (
                            <span className="inline-flex items-center gap-1 rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] font-bold text-red-400">
                              <Ban size={10} /> BAN
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-400">
                        {u.email ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        {(() => {
                          const badge = ROLE_BADGE[u.role] ?? ROLE_BADGE.client;
                          return (
                            <span
                              className={`${badge.bg} ${badge.text} text-xs px-2.5 py-1 rounded-full font-medium`}
                            >
                              {badge.label}
                            </span>
                          );
                        })()}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`font-mono text-xs uppercase ${GRADE_COLOR[u.grade] ?? "text-gray-400"}`}
                        >
                          {u.grade}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center font-mono text-amber-400">
                        {u.level}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-gray-300">
                        {u.xp.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-500 text-xs">
                        {new Date(u.created_at).toLocaleDateString("ru")}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={() => setEditUserId(u.id)}
                          className="inline-flex items-center gap-1 rounded-lg bg-purple-600/20 px-2.5 py-1.5 text-xs font-medium text-purple-300 hover:bg-purple-600/40 transition-colors"
                          title="Редактировать"
                        >
                          <Pencil size={12} /> Изм.
                        </button>
                      </td>
                    </motion.tr>
                  ))}
            </tbody>
          </table>
        </div>

        {/* Empty state */}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-12">
            <UsersIcon size={36} className="mx-auto text-gray-700 mb-3" />
            <p className="text-gray-500">Пользователи не найдены</p>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800/50">
            <span className="text-xs text-gray-500">
              Страница {page} из {totalPages}
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
      {/* Edit User Modal */}
      {editUserId && (
        <EditUserModal
          userId={editUserId}
          onClose={() => setEditUserId(null)}
          onUpdated={() => load(page, roleFilter)}
        />
      )}
    </div>
  );
}
