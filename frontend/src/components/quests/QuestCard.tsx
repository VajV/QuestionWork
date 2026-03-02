/**
 * QuestCard - Карточка квеста для ленты
 * 
 * Отображает основную информацию о квесте:
 * - Заголовок, описание
 * - Бюджет и XP награда
 * - Требуемый грейд
 * - Кнопка отклика
 */

"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Quest, UserGrade } from "@/lib/api";
import QuestStatusBadge from "./QuestStatusBadge";
import { Coins, Sparkles, Shield, Sprout, Target, Crown, FileText, Send, CheckCircle2, Clock, CheckCheck, XCircle } from 'lucide-react';

interface QuestCardProps {
  quest: Quest;
  onApply?: (questId: string) => void;
  isApplied?: boolean;
  canApply?: boolean;
}

/**
 * Получение цвета для грейда
 */
function getGradeColor(grade: UserGrade): string {
  const colors = {
    novice: 'from-gray-500 to-gray-700 text-gray-100',
    junior: 'from-green-500 to-green-700 text-green-100',
    middle: 'from-blue-500 to-blue-700 text-blue-100',
    senior: 'from-purple-500 to-purple-700 text-purple-100',
  };
  return colors[grade] || colors.novice;
}

/**
 * Форматирование даты
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  });
}

/**
 * Сокращение описания
 */
function truncateDescription(text: string, maxLength: number = 150): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

export default function QuestCard({
  quest,
  onApply,
  isApplied = false,
  canApply = true,
}: QuestCardProps) {
  const gradeColor = getGradeColor(quest.required_grade);
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="bg-gray-900/60 backdrop-blur-sm border border-white/8 rounded-2xl p-6 hover:border-purple-500/50 hover:shadow-lg hover:shadow-[0_0_30px_rgba(139,92,246,0.2)] transition-all duration-300"
    >
      {/* Заголовок и статус */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-xl font-bold text-white mb-2">
            {quest.title}
          </h3>
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span>Клиент: {quest.client_username || 'Аноним'}</span>
            <span>•</span>
            <span>{formatDate(quest.created_at)}</span>
          </div>
        </div>
        <QuestStatusBadge status={quest.status} />
      </div>

      {/* Описание */}
      <p className="text-gray-300 mb-4 line-clamp-3">
        {truncateDescription(quest.description)}
      </p>

      {/* Навыки */}
      {quest.skills.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {quest.skills.slice(0, 5).map((skill, index) => (
            <span
              key={index}
              className="px-2 py-1 bg-gray-700/50 rounded text-xs text-gray-300"
            >
              {skill}
            </span>
          ))}
          {quest.skills.length > 5 && (
            <span className="px-2 py-1 text-xs text-gray-500">
              +{quest.skills.length - 5} ещё
            </span>
          )}
        </div>
      )}

      {/* Награды и требования */}
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-700">
        {/* Бюджет и XP */}
        <div className="flex items-center gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-green-400 flex items-center gap-1 justify-center">
              <Coins size={20} className="text-green-400" aria-hidden="true" focusable="false" /> {quest.budget.toLocaleString('ru-RU')}₽
            </div>
            <div className="text-xs text-gray-500">Бюджет</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-400 flex items-center gap-1 justify-center">
              <Sparkles size={20} className="text-purple-400" aria-hidden="true" focusable="false" /> {quest.xp_reward} XP
            </div>
            <div className="text-xs text-gray-500">Награда</div>
          </div>
        </div>

        {/* Требуемый грейд */}
        <div className={`px-3 py-2 rounded-lg bg-gradient-to-r ${gradeColor} font-bold text-sm shadow-lg flex items-center gap-1.5`}>
          {quest.required_grade === 'novice' && <Shield size={14} aria-hidden="true" focusable="false" />}
          {quest.required_grade === 'junior' && <Sprout size={14} aria-hidden="true" focusable="false" />}
          {quest.required_grade === 'middle' && <Target size={14} aria-hidden="true" focusable="false" />}
          {quest.required_grade === 'senior' && <Crown size={14} aria-hidden="true" focusable="false" />}
          <span>{quest.required_grade.toUpperCase()}</span>
        </div>
      </div>

      {/* Действия */}
      <div className="flex items-center gap-3">
        {/* Кнопка деталей */}
        <Link
          href={`/quests/${quest.id}`}
          className="flex-1 flex justify-center items-center px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
        >
          <FileText size={14} className="inline mr-1.5" aria-hidden="true" focusable="false" /> Подробнее
        </Link>

        {/* Кнопка отклика */}
        {canApply && quest.status === 'open' && (
          <>
            {isApplied ? (
              <button
                disabled
                className="px-4 py-2 bg-green-900/50 text-green-300 rounded-lg cursor-not-allowed border border-green-700 flex items-center justify-center"
              >
                <CheckCircle2 size={14} className="inline mr-1.5" aria-hidden="true" focusable="false" /> Отправлен
              </button>
            ) : (
              <button
                onClick={() => onApply?.(quest.id)}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors shadow-lg shadow-purple-500/30 flex items-center justify-center"
              >
                <Send size={14} className="inline mr-1.5" aria-hidden="true" focusable="false" /> Откликнуться
              </button>
            )}
          </>
        )}

        {/* Квест не доступен для отклика */}
        {quest.status !== 'open' && canApply && (
          <button
            disabled
            className="px-4 py-2 bg-gray-700 text-gray-500 rounded-lg cursor-not-allowed flex items-center justify-center"
          >
            {quest.status === 'in_progress' && <><Clock size={14} className="inline mr-1.5" aria-hidden="true" focusable="false" /> В работе</>}
            {quest.status === 'completed' && <><CheckCheck size={14} className="inline mr-1.5" aria-hidden="true" focusable="false" /> Завершён</>}
            {quest.status === 'cancelled' && <><XCircle size={14} className="inline mr-1.5" aria-hidden="true" focusable="false" /> Отменён</>}
          </button>
        )}
      </div>
    </motion.div>
  );
}
