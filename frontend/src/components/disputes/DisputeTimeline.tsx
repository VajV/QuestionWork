"use client";

import { CheckCircle2, Circle, Clock } from "lucide-react";
import type { Dispute } from "@/types";

const STEPS = [
  { key: "open", label: "Спор открыт" },
  { key: "responded", label: "Ответ получен" },
  { key: "escalated", label: "Передан модератору" },
  { key: "resolved", label: "Разрешён" },
] as const;

const STATUS_ORDER: Record<string, number> = {
  open: 0,
  responded: 1,
  escalated: 2,
  resolved: 3,
  closed: 4,
};

function formatDate(iso?: string) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface DisputeTimelineProps {
  dispute: Dispute;
}

export default function DisputeTimeline({ dispute }: DisputeTimelineProps) {
  const currentOrder = STATUS_ORDER[dispute.status] ?? 0;

  const stepDates: Record<string, string | undefined> = {
    open: dispute.created_at,
    responded: dispute.responded_at,
    escalated: dispute.escalated_at,
    resolved: dispute.resolved_at,
  };

  return (
    <div className="space-y-0">
      {STEPS.map((step, idx) => {
        const stepOrder = idx;
        const done = stepOrder < currentOrder;
        const active = stepOrder === currentOrder;
        const pending = stepOrder > currentOrder;

        const date = stepDates[step.key];

        return (
          <div key={step.key} className="flex gap-4">
            {/* Icon + line */}
            <div className="flex flex-col items-center">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                  done
                    ? "bg-green-500/20 text-green-400"
                    : active
                    ? "bg-blue-500/20 text-blue-400"
                    : "bg-gray-800 text-gray-600"
                }`}
              >
                {done ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : active ? (
                  <Clock className="w-4 h-4" />
                ) : (
                  <Circle className="w-4 h-4" />
                )}
              </div>
              {idx < STEPS.length - 1 && (
                <div
                  className={`w-px flex-1 min-h-6 ${
                    done ? "bg-green-600/40" : "bg-gray-700"
                  }`}
                />
              )}
            </div>

            {/* Content */}
            <div className={`pb-5 ${pending ? "opacity-40" : ""}`}>
              <p
                className={`text-sm font-medium ${
                  active ? "text-blue-300" : done ? "text-green-300" : "text-gray-400"
                }`}
              >
                {step.label}
              </p>
              {date && (
                <p className="text-xs text-gray-500 mt-0.5">{formatDate(date)}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
