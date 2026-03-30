/**
 * QuestCard - Карточка квеста для ленты
 */

"use client";

import React from 'react';
import Link from "next/link";
import { motion } from "@/lib/motion";
import { Quest } from "@/lib/api";
import QuestStatusBadge from "./QuestStatusBadge";
import SignalChip from "@/components/ui/SignalChip";
import { Coins, Sparkles, Send, CheckCircle2, Clock, CheckCheck, XCircle, Flame, FileText, Users } from 'lucide-react';

interface QuestCardProps {
  quest: Quest;
  onApply?: (questId: string) => void;
  isApplied?: boolean;
  canApply?: boolean;
}

/**
 * Обертка для обработки кликов, чтобы Link не ломал структуру
 */
function QuestCardInner({
  quest,
  onApply,
  isApplied = false,
  canApply = true,
}: QuestCardProps) {
  const gradeClass = quest.required_grade.toLowerCase();
  const applicationsCount = quest.applications.length;
  const difficultyLabel =
    quest.required_grade === "senior"
      ? "Высокая"
      : quest.required_grade === "middle"
      ? "Средняя"
      : "Базовая";
  const difficultyTextClass =
    quest.required_grade === "senior"
      ? "text-red-300"
      : quest.required_grade === "middle"
      ? "text-violet-300"
      : "text-emerald-300";

  const valueSignals = [
    quest.quest_type === "training" ? { label: "PvE Тренировка", tone: "cyan" as const } : null,
    quest.quest_type === "raid" ? { label: "⚔️ Рейд", tone: "purple" as const } : null,
    quest.chain_id ? { label: "🔗 Легендарная цепочка", tone: "gold" as const } : null,
    quest.is_urgent ? { label: "Горит", tone: "red" as const } : null,
    applicationsCount >= 5 ? { label: `${applicationsCount} откликов`, tone: "purple" as const } : null,
    quest.skills.length >= 4 ? { label: "Редкий стек", tone: "cyan" as const } : null,
    quest.budget >= 50000 ? { label: "Высокая ставка", tone: "gold" as const } : null,
    quest.required_portfolio ? { label: "Нужен кейс", tone: "emerald" as const } : null,
  ].filter(Boolean) as Array<{ label: string; tone: "red" | "purple" | "cyan" | "gold" | "emerald" }>;

  const questTimeline = [
    { label: "Публикация", active: true },
    { label: "Отклики", active: applicationsCount > 0 || quest.status !== "open" },
    { label: "Назначение", active: ["assigned", "in_progress", "completed", "revision_requested", "confirmed"].includes(quest.status) },
    { label: "Сдача", active: ["completed", "revision_requested", "confirmed"].includes(quest.status) },
  ];
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`rpg-card rarity-${gradeClass} p-5 md:p-6 relative group overflow-hidden block`}
    >
      <div className="pointer-events-none absolute inset-0 opacity-70">
        <div className={`absolute inset-y-0 left-0 w-1 ${quest.is_urgent ? "bg-red-500/80" : "bg-amber-500/60"}`} />
        <div className="absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-white/[0.05] to-transparent" />
        {quest.skills.length >= 4 && (
          <div className="absolute inset-0 [background-image:linear-gradient(135deg,rgba(34,211,238,0.08)_0,rgba(34,211,238,0.08)_1px,transparent_1px,transparent_12px)] [background-size:16px_16px]" />
        )}
      </div>

      <div className="mb-4 flex flex-col gap-4 md:flex-row md:justify-between md:items-start relative z-10">
        <div className="flex-1 md:pr-4 min-w-0">
          <Link href={`/quests/${quest.id}`}>
            <h3 className="text-lg md:text-xl font-cinzel text-amber-500 mb-1 group-hover:text-amber-400 transition-colors dropdown-shadow cursor-pointer flex flex-wrap items-center gap-2">
              {quest.is_urgent && (
                <span className="inline-flex items-center gap-1 text-xs bg-red-900/40 text-red-400 border border-red-500/40 px-2 py-0.5 rounded font-mono">
                  <Flame size={12} /> СРОЧНЫЙ
                </span>
              )}
              {quest.title}
            </h3>
          </Link>
          <div className="flex items-center gap-3 text-sm text-gray-400 font-inter">
             <span className="uppercase tracking-widest">Уровень: {quest.required_grade}</span>
             <QuestStatusBadge status={quest.status} />
          </div>
          {valueSignals.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {valueSignals.map((signal) => (
                <SignalChip key={signal.label} tone={signal.tone}>
                  {signal.label}
                </SignalChip>
              ))}
            </div>
          )}
        </div>
        
        <div className="grid grid-cols-2 gap-2 shrink-0 md:flex md:flex-col md:items-end">
          {quest.quest_type === "training" ? (
            <div className="flex items-center gap-1 text-cyan-400 font-mono text-lg font-bold bg-cyan-950/30 px-3 py-1 rounded border border-cyan-700/50">
              <Sparkles size={18} /> {quest.xp_reward} XP
            </div>
          ) : (
            <>
              <div className="flex items-center gap-1 text-yellow-400 font-mono text-lg font-bold bg-yellow-950/30 px-3 py-1 rounded border border-yellow-700/50">
                <Coins size={18} /> {quest.budget.toLocaleString('ru-RU')}₽
              </div>
              <div className="flex items-center gap-1 text-purple-400 font-mono text-lg font-bold bg-purple-950/30 px-3 py-1 rounded border border-purple-700/50">
                <Sparkles size={18} /> {quest.xp_reward} XP
              </div>
            </>
          )}
          {quest.quest_type === "raid" && quest.raid_max_members && (
            <div className="flex items-center gap-1 text-violet-400 font-mono text-sm font-bold bg-violet-950/30 px-3 py-1 rounded border border-violet-700/50">
              <Users size={16} /> {quest.raid_current_members}/{quest.raid_max_members}
            </div>
          )}
        </div>
      </div>

      <p className="text-gray-300 font-inter line-clamp-3 mb-6 relative z-10">
        {quest.description}
      </p>

      <div className={`relative z-10 mb-5 grid gap-3 ${quest.quest_type === "raid" ? "md:grid-cols-4" : "md:grid-cols-3"}`}>
        <div className="rounded-xl border border-white/10 bg-black/25 p-3">
          <div className="text-[10px] uppercase tracking-[0.22em] text-gray-500">Награда</div>
          {quest.quest_type === "training" ? (
            <>
              <div className="mt-2 font-cinzel text-lg text-cyan-300">{quest.xp_reward} XP</div>
              <div className="mt-1 text-xs text-gray-400">Тренировочный квест</div>
            </>
          ) : (
            <>
              <div className="mt-2 font-cinzel text-lg text-amber-300">{quest.budget.toLocaleString('ru-RU')}₽</div>
              <div className="mt-1 text-xs text-gray-400">{quest.xp_reward} XP и денежная ставка</div>
            </>
          )}
        </div>
        {quest.quest_type === "raid" && quest.raid_max_members && (
          <div className="rounded-xl border border-violet-700/30 bg-violet-950/15 p-3">
            <div className="text-[10px] uppercase tracking-[0.22em] text-gray-500">Отряд</div>
            <div className="mt-2 font-cinzel text-lg text-violet-300">{quest.raid_current_members}/{quest.raid_max_members}</div>
            <div className="mt-1 text-xs text-gray-400">{quest.raid_max_members - quest.raid_current_members} мест свободно</div>
          </div>
        )}
        <div className="rounded-xl border border-white/10 bg-black/25 p-3">
          <div className="text-[10px] uppercase tracking-[0.22em] text-gray-500">Срочность</div>
          <div className={`mt-2 font-cinzel text-lg ${quest.is_urgent ? "text-red-300" : "text-cyan-300"}`}>{quest.is_urgent ? "Высокая" : "Плановая"}</div>
          <div className="mt-1 text-xs text-gray-400">{quest.deadline ? `Дедлайн: ${new Date(quest.deadline).toLocaleDateString('ru-RU')}` : "Без жесткого дедлайна"}</div>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/25 p-3">
          <div className="text-[10px] uppercase tracking-[0.22em] text-gray-500">Сложность</div>
          <div className={`mt-2 font-cinzel text-lg ${difficultyTextClass}`}>{difficultyLabel}</div>
          <div className="mt-1 text-xs text-gray-400">{quest.skills.length} навыка в стеке</div>
        </div>
      </div>

      <div className="relative z-10 mb-5 rounded-2xl border border-white/10 bg-black/20 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="text-[10px] uppercase tracking-[0.24em] text-gray-500">Quest pulse</div>
          <div className="text-xs text-gray-400">{applicationsCount > 0 ? `${applicationsCount} отклик(ов)` : "Охота только началась"}</div>
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          {questTimeline.map((step, index) => (
            <div key={step.label} className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/[0.02] px-3 py-2">
              <div className={`h-2.5 w-2.5 rounded-full ${step.active ? "bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.6)]" : "bg-gray-700"}`} />
              <div>
                <div className="text-[10px] uppercase tracking-[0.22em] text-gray-500">{index + 1}</div>
                <div className={`text-xs ${step.active ? "text-stone-200" : "text-gray-500"}`}>{step.label}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      <div className="divider-ornament my-4"></div>

      {/* Футер карточки с кнопкой */}
      <div className="flex flex-col gap-4 md:flex-row md:justify-between md:items-center relative z-10">
        <div className="flex flex-wrap gap-2 md:max-w-[60%]">
          {quest.skills.slice(0, 3).map((skill, idx) => (
            <span key={idx} className="text-xs font-mono text-gray-400 bg-black/40 px-2 py-1 rounded border border-gray-800">
              {skill}
            </span>
          ))}
          {quest.skills.length > 3 && (
            <span className="text-xs font-mono text-gray-500 bg-black/40 px-2 py-1 rounded border border-gray-800">
              +{quest.skills.length - 3}
            </span>
          )}
        </div>
        
        <div className="flex items-center gap-2 md:justify-end">
          {/* Кнопка отклика */}
          {canApply && quest.status === 'open' && (
            <>
              {isApplied ? (
                <button
                  disabled
                  aria-label={`Отклик на квест ${quest.title} уже отправлен`}
                  className="w-full md:w-auto px-6 py-2 bg-green-950/50 text-green-400 font-cinzel font-bold rounded border border-green-700/50 cursor-not-allowed flex items-center justify-center"
                >
                  <CheckCircle2 size={16} className="mr-2" /> Отправлен
                </button>
              ) : (
                <button
                  onClick={() => onApply?.(quest.id)}
                  aria-label={`Откликнуться на квест ${quest.title}`}
                  className="w-full md:w-auto px-6 py-2 bg-gradient-to-r from-amber-700 to-amber-900 text-white font-cinzel font-bold rounded hover:from-amber-600 hover:to-amber-800 border border-amber-500/50 shadow-[0_0_15px_rgba(217,119,6,0.3)] transition-all hover:scale-105 flex items-center justify-center focus:outline-none"
                >
                  <Send size={16} className="mr-2" /> Принять Вызов
                </button>
              )}
            </>
          )}

          {/* Квест не доступен для отклика */}
          {quest.status !== 'open' && canApply && (
            <button
              disabled
              aria-label={`Квест ${quest.title} недоступен для отклика, статус: ${quest.status}`}
              className="w-full md:w-auto px-6 py-2 bg-gray-900 text-gray-500 font-cinzel font-bold rounded border border-gray-700/50 cursor-not-allowed flex items-center justify-center"
            >
              {quest.status === 'assigned' && <><Clock size={16} className="mr-2" /> Назначен</>}
              {quest.status === 'draft' && <><FileText size={16} className="mr-2" /> Черновик</>}
              {quest.status === 'in_progress' && <><Clock size={16} className="mr-2" /> В работе</>}
              {quest.status === 'completed' && <><CheckCheck size={16} className="mr-2" /> Завершён</>}
              {quest.status === 'revision_requested' && <><Clock size={16} className="mr-2" /> Доработка</>}
              {quest.status === 'confirmed' && <><CheckCheck size={16} className="mr-2" /> Подтверждён</>}
              {quest.status === 'cancelled' && <><XCircle size={16} className="mr-2" /> Отменён</>}
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}

const QuestCard = React.memo(QuestCardInner);
export default QuestCard;
