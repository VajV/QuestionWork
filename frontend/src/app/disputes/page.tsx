"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import api, { getApiErrorMessage } from "@/lib/api";
import type { Dispute } from "@/types";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import DisputeCard from "@/components/disputes/DisputeCard";
import { useSWRFetch } from "@/hooks/useSWRFetch";

const ACTIVE_STATUSES = new Set(["open", "responded", "escalated"]);

export default function DisputesPage() {
  const router = useRouter();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [tab, setTab] = useState<"active" | "resolved">("active");

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace("/auth/login");
    }
  }, [isAuthenticated, authLoading, router]);

  const {
    data,
    error,
    isLoading,
    mutate,
  } = useSWRFetch(
    !authLoading && isAuthenticated ? (["my-disputes", 100, 0] as const) : null,
    () => api.listMyDisputes(100, 0),
    { revalidateOnFocus: false },
  );

  const disputes: Dispute[] = data?.items ?? [];
  const errorMessage = error ? getApiErrorMessage(error, "Не удалось загрузить споры") : null;

  const filtered = disputes.filter((d) =>
    tab === "active" ? ACTIVE_STATUSES.has(d.status) : !ACTIVE_STATUSES.has(d.status)
  );

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <div className="flex items-center gap-3 mb-6">
          <AlertTriangle className="w-6 h-6 text-yellow-400" />
          <h1 className="text-2xl font-bold">Мои споры</h1>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-900 rounded-lg p-1 mb-6 w-fit">
          {(["active", "resolved"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                tab === t
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {t === "active" ? "Активные" : "Завершённые"}
            </button>
          ))}
        </div>

        {(authLoading || (isAuthenticated && isLoading)) && (
          <p className="text-gray-400 text-sm">Загружаем споры...</p>
        )}
        {errorMessage && (
          <Card className="border border-red-500/30 bg-red-500/10 p-4">
            <p className="text-red-400 text-sm">{errorMessage}</p>
            <button
              type="button"
              onClick={() => void mutate()}
              className="mt-3 rounded-md border border-red-400/30 px-3 py-2 text-sm text-red-200 transition-colors hover:bg-red-500/10"
            >
              Повторить
            </button>
          </Card>
        )}
        {!authLoading && !isLoading && !errorMessage && filtered.length === 0 && (
          <Card className="text-center py-10">
            <p className="text-gray-500 text-sm">
              {tab === "active" ? "Нет активных споров" : "Завершённых споров нет"}
            </p>
          </Card>
        )}
        {!authLoading && !isLoading && !errorMessage && (
          <div className="space-y-3">
            {filtered.map((d) => (
              <DisputeCard key={d.id} dispute={d} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
