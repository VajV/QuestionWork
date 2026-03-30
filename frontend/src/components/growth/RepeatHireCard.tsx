"use client";

import { useState } from "react";
import Link from "next/link";
import { trackAnalyticsEvent } from "@/lib/analytics";
import type { Quest } from "@/lib/api";

interface Props {
  quest: Quest;
  /** Optional: pre-filled assigned freelancer id for "hire again" CTA */
  freelancerId?: string | null;
}

export default function RepeatHireCard({ quest, freelancerId }: Props) {
  const [clicked, setClicked] = useState(false);

  const createSimilarParams = new URLSearchParams({
    from_quest: quest.id,
    title: quest.title,
    skills: quest.skills.join(","),
    grade: quest.required_grade,
    budget: String(quest.budget),
    currency: quest.currency,
  });

  if (freelancerId) {
    createSimilarParams.set("invite_freelancer", freelancerId);
  }

  function handleClick() {
    if (!clicked) {
      setClicked(true);
      trackAnalyticsEvent("repeat_hire_started", {
        source_quest_id: quest.id,
        freelancer_id: freelancerId ?? undefined,
      });
    }
  }

  return (
    <div className="rounded-2xl border border-purple-500/30 bg-purple-950/10 p-5 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-purple-400 text-lg">🔁</span>
        <h3 className="font-semibold text-white text-sm">Снова нанять / повторить квест</h3>
      </div>
      <p className="text-xs text-gray-400">
        Этот квест выполнен. Создайте похожий квест с теми же параметрами — так быстрее, чем заполнять с нуля.
      </p>
      <div className="flex flex-wrap gap-2">
        <Link
          href={`/quests/create?${createSimilarParams.toString()}`}
          onClick={handleClick}
          className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-xs font-medium px-4 py-2 transition-colors"
        >
          ✨ Создать похожий квест
        </Link>
        {freelancerId && (
          <Link
            href={`/users/${freelancerId}`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-purple-500/40 text-purple-300 hover:text-purple-200 text-xs px-4 py-2 transition-colors"
          >
            👤 Профиль исполнителя
          </Link>
        )}
        <Link
          href="/marketplace"
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-600 text-gray-400 hover:text-gray-200 text-xs px-4 py-2 transition-colors"
        >
          🔍 Найти нового исполнителя
        </Link>
      </div>
    </div>
  );
}
