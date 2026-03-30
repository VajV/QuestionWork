"use client";

import { useState } from "react";
import { MessageSquare, X } from "lucide-react";
import api, { getApiErrorMessage } from "@/lib/api";
import type { Dispute } from "@/types";

interface RespondModalProps {
  disputeId: string;
  onClose: () => void;
  onSubmitted: (dispute: Dispute) => void;
}

export default function RespondModal({
  disputeId,
  onClose,
  onSubmitted,
}: RespondModalProps) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const MIN_CHARS = 10;
  const MAX_CHARS = 2000;

  async function handleSubmit() {
    if (text.trim().length < MIN_CHARS) {
      setError(`Ответ должен содержать минимум ${MIN_CHARS} символов`);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const dispute = await api.respondDispute(disputeId, text.trim());
      onSubmitted(dispute);
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось отправить ответ"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="bg-gray-900 border border-blue-800/50 rounded-xl w-full max-w-lg shadow-xl">
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div className="flex items-center gap-2 text-blue-400">
            <MessageSquare className="w-5 h-5" />
            <h2 className="text-lg font-semibold">Ответить на спор</h2>
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
            Опишите свою позицию. Ваш ответ будет виден фрилансеру и
            модератору.
          </p>
          <div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={MAX_CHARS}
              rows={5}
              placeholder="Ваш ответ на претензию..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm resize-none focus:outline-none focus:border-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1 text-right">
              {text.length}/{MAX_CHARS}
            </p>
          </div>
          {error && (
            <p className="text-sm text-red-400 bg-red-400/10 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
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
            disabled={loading || text.trim().length < MIN_CHARS}
            className="flex-1 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
          >
            {loading ? "Отправляем..." : "Отправить ответ"}
          </button>
        </div>
      </div>
    </div>
  );
}
