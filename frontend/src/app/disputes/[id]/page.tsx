"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ArrowLeft, ChevronUp } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import api, { getApiErrorMessage } from "@/lib/api";
import type { Dispute } from "@/types";
import Header from "@/components/layout/Header";
import Card from "@/components/ui/Card";
import DisputeTimeline from "@/components/disputes/DisputeTimeline";
import RespondModal from "@/components/disputes/RespondModal";

export default function DisputeDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [dispute, setDispute] = useState<Dispute | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRespondModal, setShowRespondModal] = useState(false);
  const [escalating, setEscalating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.replace("/auth/login");
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (!isAuthenticated || !params.id) return;
    api
      .getDispute(params.id)
      .then(setDispute)
      .catch((err) => setError(getApiErrorMessage(err, "Не удалось загрузить спор")))
      .finally(() => setLoading(false));
  }, [isAuthenticated, params.id]);

  async function handleEscalate() {
    if (!dispute) return;
    setEscalating(true);
    setActionError(null);
    try {
      const updated = await api.escalateDispute(dispute.id);
      setDispute(updated);
    } catch (err) {
      setActionError(getApiErrorMessage(err, "Не удалось эскалировать спор"));
    } finally {
      setEscalating(false);
    }
  }

  const isRespondent = user?.id === dispute?.respondent_id;
  const isParty = user?.id === dispute?.initiator_id || user?.id === dispute?.respondent_id;
  const canRespond = isRespondent && dispute?.status === "open";
  const canEscalate = isParty && (dispute?.status === "open" || dispute?.status === "responded");

  const RESOLUTION_LABELS: Record<string, string> = {
    refund: "Возврат клиенту",
    partial: `Частичная выплата`,
    freelancer: "Выплата фрилансеру",
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-gray-400 hover:text-white text-sm mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Назад
        </button>

        {loading && <p className="text-gray-400 text-sm">Загружаем спор...</p>}
        {error && (
          <p className="text-red-400 text-sm bg-red-400/10 rounded-lg px-3 py-2">{error}</p>
        )}

        {dispute && (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-6 h-6 text-yellow-400 shrink-0" />
              <h1 className="text-xl font-bold truncate">Спор по квесту</h1>
            </div>

            {/* Timeline */}
            <Card>
              <DisputeTimeline dispute={dispute} />
            </Card>

            {/* Reason */}
            <Card>
              <h2 className="text-sm font-semibold text-gray-300 mb-2">Причина спора</h2>
              <p className="text-sm text-gray-400 whitespace-pre-wrap">{dispute.reason}</p>
            </Card>

            {/* Response */}
            {dispute.response_text && (
              <Card>
                <h2 className="text-sm font-semibold text-gray-300 mb-2">Ответ клиента</h2>
                <p className="text-sm text-gray-400 whitespace-pre-wrap">
                  {dispute.response_text}
                </p>
              </Card>
            )}

            {/* Resolution */}
            {dispute.status === "resolved" && dispute.resolution_type && (
              <Card className="border-green-800/40 bg-green-900/10">
                <h2 className="text-sm font-semibold text-green-300 mb-2">Решение модератора</h2>
                <p className="text-sm font-medium text-white mb-1">
                  {RESOLUTION_LABELS[dispute.resolution_type]}
                  {dispute.resolution_type === "partial" && dispute.partial_percent
                    ? ` (${dispute.partial_percent}% фрилансеру)`
                    : ""}
                </p>
                {dispute.resolution_note && (
                  <p className="text-sm text-gray-400 whitespace-pre-wrap">
                    {dispute.resolution_note}
                  </p>
                )}
              </Card>
            )}

            {/* Action error */}
            {actionError && (
              <p className="text-sm text-red-400 bg-red-400/10 rounded-lg px-3 py-2">
                {actionError}
              </p>
            )}

            {/* Actions */}
            {(canRespond || canEscalate) && (
              <div className="flex gap-3">
                {canRespond && (
                  <button
                    onClick={() => setShowRespondModal(true)}
                    className="flex-1 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors"
                  >
                    Ответить на спор
                  </button>
                )}
                {canEscalate && (
                  <button
                    onClick={handleEscalate}
                    disabled={escalating}
                    className="flex-1 px-4 py-2.5 rounded-lg border border-orange-700 text-orange-400 hover:bg-orange-900/20 disabled:opacity-50 text-sm font-medium transition-colors flex items-center justify-center gap-2"
                  >
                    <ChevronUp className="w-4 h-4" />
                    {escalating ? "Передаём..." : "Эскалировать модератору"}
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {showRespondModal && dispute && (
          <RespondModal
            disputeId={dispute.id}
            onClose={() => setShowRespondModal(false)}
            onSubmitted={(updated) => {
              setDispute(updated);
              setShowRespondModal(false);
            }}
          />
        )}
      </main>
    </div>
  );
}
