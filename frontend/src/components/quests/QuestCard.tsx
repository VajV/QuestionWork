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
      className="bg-gray-800/50 backdrop-blur-sm border border-gray-700 rounded-xl p-6 hover:border-purple-500/50 hover:shadow-lg hover:shadow-purple-500/10 transition-all duration-300"
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
            <div className="text-2xl font-bold text-green-400">
              💰 {quest.budget.toLocaleString('ru-RU')}₽
            </div>
            <div className="text-xs text-gray-500">Бюджет</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-400">
              ⚡ {quest.xp_reward} XP
            </div>
            <div className="text-xs text-gray-500">Награда</div>
          </div>
        </div>

        {/* Требуемый грейд */}
        <div className={`px-3 py-2 rounded-lg bg-gradient-to-r ${gradeColor} font-bold text-sm shadow-lg`}>
          {quest.required_grade === 'novice' && '🔰'}
          {quest.required_grade === 'junior' && '🌱'}
          {quest.required_grade === 'middle' && '🎯'}
          {quest.required_grade === 'senior' && '👑'}
          {' '}{quest.required_grade.toUpperCase()}
        </div>
      </div>

      {/* Действия */}
      <div className="flex items-center gap-3">
        {/* Кнопка деталей */}
        <Link
          href={`/quests/${quest.id}`}
          className="flex-1 text-center px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
        >
          📄 Подробнее
        </Link>

        {/* Кнопка отклика */}
        {canApply && quest.status === 'open' && (
          <>
            {isApplied ? (
              <button
                disabled
                className="px-4 py-2 bg-green-900/50 text-green-300 rounded-lg cursor-not-allowed border border-green-700"
              >
                ✅ Отправлен
              </button>
            ) : (
              <button
                onClick={() => onApply?.(quest.id)}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors shadow-lg shadow-purple-500/30"
              >
                📩 Откликнуться
              </button>
            )}
          </>
        )}

        {/* Квест не доступен для отклика */}
        {quest.status !== 'open' && canApply && (
          <button
            disabled
            className="px-4 py-2 bg-gray-700 text-gray-500 rounded-lg cursor-not-allowed"
          >
            {quest.status === 'in_progress' && '⏳ В работе'}
            {quest.status === 'completed' && '✅ Завершён'}
            {quest.status === 'cancelled' && '❌ Отменён'}
          </button>
        )}
      </div>
    </motion.div>
  );
}
