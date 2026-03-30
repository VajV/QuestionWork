"use client";

import Link from "next/link";
import type { Dispute } from "@/types";

const STATUS_LABELS: Record<string, string> = {
  open: "Открыт",
  responded: "Ответ получен",
  escalated: "У модератора",
  resolved: "Разрешён",
  closed: "Закрыт",
};

const STATUS_COLORS: Record<string, string> = {
  open: "text-yellow-400 bg-yellow-400/10 border-yellow-700/40",
  responded: "text-blue-400 bg-blue-400/10 border-blue-700/40",
  escalated: "text-orange-400 bg-orange-400/10 border-orange-700/40",
  resolved: "text-green-400 bg-green-400/10 border-green-700/40",
  closed: "text-gray-400 bg-gray-700/40 border-gray-600/40",
};

const RESOLUTION_LABELS: Record<string, string> = {
  refund: "Возврат клиенту",
  partial: "Частичная выплата",
  freelancer: "Выплата фрилансеру",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

interface DisputeCardProps {
  dispute: Dispute;
}

export default function DisputeCard({ dispute }: DisputeCardProps) {
  const colorClass =
    STATUS_COLORS[dispute.status] ?? STATUS_COLORS.closed;

  return (
    <Link
      href={`/disputes/${dispute.id}`}
      className="block bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-4 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-gray-400 truncate">
            Квест:{" "}
            <span className="text-white font-medium">{dispute.quest_id}</span>
          </p>
          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
            {dispute.reason}
          </p>
        </div>
        <span
          className={`shrink-0 text-xs font-medium px-2 py-1 rounded-full border ${colorClass}`}
        >
          {STATUS_LABELS[dispute.status] ?? dispute.status}
        </span>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
        <span>Открыт {formatDate(dispute.created_at)}</span>
        {dispute.resolution_type && (
          <span className="text-green-400">
            {RESOLUTION_LABELS[dispute.resolution_type]}
          </span>
        )}
        {!dispute.resolution_type && dispute.status === "escalated" && (
          <span className="text-orange-400">Ожидает модератора</span>
        )}
      </div>
    </Link>
  );
}
