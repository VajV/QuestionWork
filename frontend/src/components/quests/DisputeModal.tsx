"use client";

import { useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import api, { getApiErrorMessage } from "@/lib/api";
import type { Dispute } from "@/types";

interface DisputeModalProps {
  questId: string;
  questTitle: string;
  onClose: () => void;
  onSubmitted: (dispute: Dispute) => void;
}

export default function DisputeModal({
  questId,
  questTitle,
  onClose,
  onSubmitted,
}: DisputeModalProps) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const MIN_CHARS = 10;
  const MAX_CHARS = 2000;

  async function handleSubmit() {
    if (reason.trim().length < MIN_CHARS) {
      setError(`Описание должно содержать минимум ${MIN_CHARS} символов`);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const dispute = await api.openDispute(questId, reason.trim());
      onSubmitted(dispute);
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось открыть спор"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="bg-gray-900 border border-red-800/50 rounded-xl w-full max-w-lg shadow-xl">
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div className="flex items-center gap-2 text-red-400">
            <AlertTriangle className="w-5 h-5" />
            <h2 className="text-lg font-semibold">Открыть спор</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <p className="text-sm text-gray-400">
            Квест:{" "}
            <span className="text-white font-medium">{questTitle}</span>
          </p>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Причина спора
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={MAX_CHARS}
              rows={5}
              placeholder="Опишите, почему клиент не подтверждает выполнение и чего вы ожидаете..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm resize-none focus:outline-none focus:border-red-500"
            />
            <p className="text-xs text-gray-500 mt-1 text-right">
              {reason.length}/{MAX_CHARS}
            </p>
          </div>

          {error && (
            <p className="text-sm text-red-400 bg-red-400/10 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="bg-yellow-900/20 border border-yellow-700/40 rounded-lg px-4 py-3 text-sm text-yellow-300">
            После открытия спора у клиента будет <strong>72 часа</strong> на
            ответ. Если ответа не будет — спор автоматически передаётся
            модератору.
          </div>
        </div>

        <div className="flex gap-3 p-5 border-t border-gray-800">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 rounded-lg border border-gray-700 text-gray-300 text-sm hover:bg-gray-800 transition-colors"
          >
            Отмена
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || reason.trim().length < MIN_CHARS}
            className="flex-1 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
          >
            {loading ? "Открываем..." : "Открыть спор"}
          </button>
        </div>
      </div>
    </div>
  );
}
