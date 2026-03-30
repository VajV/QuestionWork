"use client";

import { CheckCircle, Circle } from "lucide-react";

export interface OnboardingItem {
  key: string;
  label: string;
  hint: string;
  done: boolean;
}

interface Props {
  items: OnboardingItem[];
}

export default function FreelancerOnboardingChecklist({ items }: Props) {
  const doneCount = items.filter((i) => i.done).length;
  const pct = items.length > 0 ? Math.round((doneCount / items.length) * 100) : 0;

  return (
    <div className="rounded-2xl border border-white/10 bg-gradient-to-b from-white/[0.04] to-black/30 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-cinzel text-lg text-amber-400">Готовность профиля</h3>
        <span className="text-sm text-stone-400 font-mono">
          {doneCount}/{items.length} ({pct}%)
        </span>
      </div>
      <div className="h-2 rounded-full bg-white/10 mb-6 overflow-hidden">
        <div
          className="h-full rounded-full bg-gradient-to-r from-amber-500 to-emerald-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.key} className="flex items-start gap-3">
            {item.done ? (
              <CheckCircle size={18} className="text-emerald-400 mt-0.5 shrink-0" />
            ) : (
              <Circle size={18} className="text-stone-600 mt-0.5 shrink-0" />
            )}
            <div>
              <p className={`text-sm font-medium ${item.done ? "text-stone-300" : "text-white"}`}>
                {item.label}
              </p>
              <p className="text-xs text-stone-500 mt-0.5">{item.hint}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
