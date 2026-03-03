/**
 * QuestCard - Карточка квеста для ленты
 */

"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Quest } from "@/lib/api";
import QuestStatusBadge from "./QuestStatusBadge";
import { Coins, Sparkles, Send, CheckCircle2, Clock, CheckCheck, XCircle } from 'lucide-react';

interface QuestCardProps {
  quest: Quest;
  onApply?: (questId: string) => void;
  isApplied?: boolean;
  canApply?: boolean;
}

/**
 * Обертка для обработки кликов, чтобы Link не ломал структуру
 */
export default function QuestCard({
  quest,
  onApply,
  isApplied = false,
  canApply = true,
}: QuestCardProps) {
  const gradeClass = quest.required_grade.toLowerCase();
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`rpg-card rarity-${gradeClass} p-6 relative group overflow-hidden block`}
    >
      <div className="flex justify-between items-start mb-4 relative z-10">
        <div className="flex-1 pr-4">
          <Link href={`/quests/${quest.id}`}>
            <h3 className="text-xl font-cinzel text-amber-500 mb-1 group-hover:text-amber-400 transition-colors dropdown-shadow cursor-pointer">
              {quest.title}
            </h3>
          </Link>
          <div className="flex items-center gap-3 text-sm text-gray-400 font-inter">
             <span className="uppercase tracking-widest">Уровень: {quest.required_grade}</span>
             <QuestStatusBadge status={quest.status} />
          </div>
        </div>
        
        <div className="flex flex-col items-end gap-2 shrink-0">
          <div className="flex items-center gap-1 text-yellow-400 font-mono text-lg font-bold bg-yellow-950/30 px-3 py-1 rounded border border-yellow-700/50">
            <Coins size={18} /> {quest.budget.toLocaleString('ru-RU')}₽
          </div>
          <div className="flex items-center gap-1 text-purple-400 font-mono text-lg font-bold bg-purple-950/30 px-3 py-1 rounded border border-purple-700/50">
            <Sparkles size={18} /> {quest.xp_reward} XP
          </div>
        </div>
      </div>

      <p className="text-gray-300 font-inter line-clamp-3 mb-6 relative z-10">
        {quest.description}
      </p>
      
      <div className="divider-ornament my-4"></div>

      {/* Футер карточки с кнопкой */}
      <div className="flex justify-between items-center relative z-10">
        <div className="flex flex-wrap gap-2 max-w-[60%]">
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
        
        <div className="flex items-center gap-2">
          {/* Кнопка отклика */}
          {canApply && quest.status === 'open' && (
            <>
              {isApplied ? (
                <button
                  disabled
                  className="px-6 py-2 bg-green-950/50 text-green-400 font-cinzel font-bold rounded border border-green-700/50 cursor-not-allowed flex items-center"
                >
                  <CheckCircle2 size={16} className="mr-2" /> Отправлен
                </button>
              ) : (
                <button
                  onClick={() => onApply?.(quest.id)}
                  className="px-6 py-2 bg-gradient-to-r from-amber-700 to-amber-900 text-white font-cinzel font-bold rounded hover:from-amber-600 hover:to-amber-800 border border-amber-500/50 shadow-[0_0_15px_rgba(217,119,6,0.3)] transition-all hover:scale-105 flex items-center focus:outline-none"
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
              className="px-6 py-2 bg-gray-900 text-gray-500 font-cinzel font-bold rounded border border-gray-700/50 cursor-not-allowed flex items-center"
            >
              {quest.status === 'in_progress' && <><Clock size={16} className="mr-2" /> В работе</>}
              {quest.status === 'completed' && <><CheckCheck size={16} className="mr-2" /> Завершён</>}
              {quest.status === 'cancelled' && <><XCircle size={16} className="mr-2" /> Отменён</>}
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}
