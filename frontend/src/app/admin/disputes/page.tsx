"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Gavel } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import api, { getApiErrorMessage } from "@/lib/api";
import type { Dispute, DisputeStatus } from "@/types";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import DisputeCard from "@/components/disputes/DisputeCard";
import ResolveModal from "@/components/disputes/ResolveModal";

const STATUS_TABS: { value: DisputeStatus | "all"; label: string }[] = [
  { value: "all", label: "Все" },
  { value: "open", label: "Открытые" },
  { value: "responded", label: "С ответом" },
  { value: "escalated", label: "Эскалированные" },
  { value: "resolved", label: "Разрешённые" },
];

export default function AdminDisputesPage() {
  const router = useRouter();
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<DisputeStatus | "all">("escalated");
  const [resolving, setResolving] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && (!isAuthenticated || user?.role !== "admin")) {
      router.replace("/");
    }
  }, [isAuthenticated, authLoading, user, router]);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== "admin") return;
    setLoading(true);
    const s = statusFilter === "all" ? undefined : statusFilter;
    api
      .adminListDisputes(s, 100, 0)
      .then((res) => {
        setDisputes(res.items);
        setTotal(res.total);
      })
      .catch((err) => setError(getApiErrorMessage(err, "Не удалось загрузить споры")))
      .finally(() => setLoading(false));
  }, [isAuthenticated, user, statusFilter]);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Header />
      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center gap-3 mb-6">
          <Gavel className="w-6 h-6 text-purple-400" />
          <h1 className="text-2xl font-bold">Очередь споров</h1>
          {total > 0 && (
            <span className="ml-auto text-sm text-gray-400">{total} шт.</span>
          )}
        </div>

        {/* Status filter tabs */}
        <div className="flex flex-wrap gap-1 bg-gray-900 rounded-lg p-1 mb-6">
          {STATUS_TABS.map((t) => (
            <button
              key={t.value}
              onClick={() => setStatusFilter(t.value)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                statusFilter === t.value
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading && <p className="text-gray-400 text-sm">Загружаем...</p>}
        {error && (
          <p className="text-red-400 text-sm bg-red-400/10 rounded-lg px-3 py-2">{error}</p>
        )}
        {!loading && !error && disputes.length === 0 && (
          <Card className="text-center py-10">
            <p className="text-gray-500 text-sm">Споров с данным статусом нет</p>
          </Card>
        )}

        {!loading && !error && (
          <div className="space-y-3">
            {disputes.map((d) => (
              <div key={d.id} className="space-y-1">
                <DisputeCard dispute={d} />
                {d.status === "escalated" && (
                  <button
                    onClick={() => setResolving(d.id)}
                    className="w-full text-sm text-center py-2 rounded-lg border border-purple-700 text-purple-400 hover:bg-purple-900/20 transition-colors"
                  >
                    Разрешить спор
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </main>

      {resolving && (
        <ResolveModal
          disputeId={resolving}
          onClose={() => setResolving(null)}
          onResolved={(updated) => {
            setDisputes((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
            setResolving(null);
          }}
        />
      )}
    </div>
  );
}
