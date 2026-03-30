"use client";

import { useState } from "react";
import { Gavel, X } from "lucide-react";
import api, { getApiErrorMessage } from "@/lib/api";
import type { Dispute, ResolutionType } from "@/types";

interface ResolveModalProps {
  disputeId: string;
  onClose: () => void;
  onResolved: (dispute: Dispute) => void;
}

const RESOLUTION_OPTIONS: { value: ResolutionType; label: string; desc: string }[] = [
  {
    value: "refund",
    label: "Возврат клиенту",
    desc: "Вся сумма возвращается клиенту. Квест отменяется.",
  },
  {
    value: "partial",
    label: "Частичная выплата",
    desc: "Указанный % выплачивается фрилансеру, остаток — клиенту.",
  },
  {
    value: "freelancer",
    label: "Выплата фрилансеру",
    desc: "Полная сумма выплачивается фрилансеру. Квест подтверждается.",
  },
];

export default function ResolveModal({
  disputeId,
  onClose,
  onResolved,
}: ResolveModalProps) {
  const [resolutionType, setResolutionType] = useState<ResolutionType>("refund");
  const [partialPercent, setPartialPercent] = useState<string>("50");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (note.trim().length < 5) {
      setError("Примечание должно содержать минимум 5 символов");
      return;
    }
    if (resolutionType === "partial") {
      const pct = Number(partialPercent);
      if (!pct || pct < 1 || pct > 99) {
        setError("Процент должен быть от 1 до 99");
        return;
      }
    }
    setLoading(true);
    setError(null);
    try {
      const dispute = await api.adminResolveDispute(
        disputeId,
        resolutionType,
        note.trim(),
        resolutionType === "partial" ? Number(partialPercent) : undefined
      );
      onResolved(dispute);
    } catch (err) {
      setError(getApiErrorMessage(err, "Не удалось разрешить спор"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="bg-gray-900 border border-purple-800/50 rounded-xl w-full max-w-lg shadow-xl">
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div className="flex items-center gap-2 text-purple-400">
            <Gavel className="w-5 h-5" />
            <h2 className="text-lg font-semibold">Разрешить спор</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Resolution type */}
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-300">Решение</p>
            {RESOLUTION_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  resolutionType === opt.value
                    ? "border-purple-500 bg-purple-500/10"
                    : "border-gray-700 hover:border-gray-600"
                }`}
              >
                <input
                  type="radio"
                  name="resolution"
                  value={opt.value}
                  checked={resolutionType === opt.value}
                  onChange={() => setResolutionType(opt.value)}
                  className="mt-0.5 accent-purple-500"
                />
                <div>
                  <p className="text-sm font-medium text-white">{opt.label}</p>
                  <p className="text-xs text-gray-400">{opt.desc}</p>
                </div>
              </label>
            ))}
          </div>

          {/* Partial percent */}
          {resolutionType === "partial" && (
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Процент фрилансеру (1–99%)
              </label>
              <input
                type="number"
                min={1}
                max={99}
                value={partialPercent}
                onChange={(e) => setPartialPercent(e.target.value)}
                className="w-32 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
              />
            </div>
          )}

          {/* Note */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Примечание модератора
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="Объясните основание для данного решения..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm resize-none focus:outline-none focus:border-purple-500"
            />
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
            disabled={loading}
            className="flex-1 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
          >
            {loading ? "Применяем..." : "Применить решение"}
          </button>
        </div>
      </div>
    </div>
  );
}
