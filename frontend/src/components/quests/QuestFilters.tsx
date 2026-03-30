/**
 * QuestFilters - Панель фильтров для ленты квестов
 * 
 * Фильтры применяются только по кнопке "Применить"
 */

"use client";

import { useState } from "react";
import { UserGrade, QuestStatus } from "@/lib/api";
import type { QuestFilterState } from "@/types";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

interface QuestFiltersProps {
  onFilterChange: (filters: QuestFilterState) => void;
  initialFilters?: QuestFilterState;
}

const GRADE_OPTIONS: { value: UserGrade; label: string; icon: string }[] = [
  { value: 'novice', label: 'Novice', icon: '🔰' },
  { value: 'junior', label: 'Junior', icon: '🌱' },
  { value: 'middle', label: 'Middle', icon: '🎯' },
  { value: 'senior', label: 'Senior', icon: '👑' },
];

const STATUS_OPTIONS: { value: QuestStatus; label: string; icon: string }[] = [
  { value: 'draft', label: 'Черновик', icon: '📝' },
  { value: 'open', label: 'Открыт', icon: '🟢' },
  { value: 'assigned', label: 'Назначен', icon: '📌' },
  { value: 'in_progress', label: 'В работе', icon: '🔵' },
  { value: 'completed', label: 'Завершён', icon: '🟣' },
  { value: 'revision_requested', label: 'На доработке', icon: '🛠️' },
  { value: 'cancelled', label: 'Отменён', icon: '⚫' },
];

export default function QuestFilters({ onFilterChange, initialFilters }: QuestFiltersProps) {
  // Локальные состояния для полей ввода
  const [grade, setGrade] = useState<UserGrade | ''>(initialFilters?.grade || '');
  const [status, setStatus] = useState<QuestStatus | ''>(initialFilters?.status || 'open');
  const [skill, setSkill] = useState(initialFilters?.skill || '');
  const [minBudget, setMinBudget] = useState(initialFilters?.minBudget?.toString() || '');
  const [maxBudget, setMaxBudget] = useState(initialFilters?.maxBudget?.toString() || '');

  /**
   * Применение фильтров (только по кнопке)
   */
  const applyFilters = () => {
    const newFilters: QuestFilterState = {
      grade: grade || undefined,
      status: status || undefined,
      skill: skill.trim() || undefined,
      minBudget: minBudget ? Number(minBudget) : undefined,
      maxBudget: maxBudget ? Number(maxBudget) : undefined,
    };
    onFilterChange(newFilters);
  };

  /**
   * Сброс всех фильтров
   */
  const resetFilters = () => {
    setGrade('');
    setStatus('open');
    setSkill('');
    setMinBudget('');
    setMaxBudget('');
    onFilterChange({
      grade: undefined,
      status: 'open',
      skill: undefined,
      minBudget: undefined,
      maxBudget: undefined,
    });
  };

  return (
    <Card className="mb-6 border-purple-900/20 bg-gradient-to-br from-gray-900 to-gray-950 p-4 md:p-5">
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
        <h3 className="text-lg font-bold flex items-center gap-2">
          <span>🔍</span> Фильтры
        </h3>
        <p className="mt-1 text-sm text-gray-400">Подберите миссии по рангу, навыку и диапазону награды.</p>
        </div>
        <Button onClick={resetFilters} variant="secondary" className="text-sm py-1 px-3">
          🔄 Сбросить
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
        {/* Фильтр по грейду */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            📊 Грейд
          </label>
          <select
            value={grade}
            onChange={(e) => setGrade(e.target.value as UserGrade | '')}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white"
          >
            <option value="">Любой</option>
            {GRADE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.icon} {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Фильтр по статусу */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            📋 Статус
          </label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as QuestStatus | '')}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white"
          >
            <option value="">Любой</option>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.icon} {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Фильтр по навыку */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            🛠️ Навык
          </label>
          <input
            type="text"
            value={skill}
            onChange={(e) => setSkill(e.target.value)}
            placeholder="Python..."
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500"
          />
        </div>

        {/* Фильтр по бюджету (min) */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            💰 От
          </label>
          <input
            type="number"
            value={minBudget}
            onChange={(e) => setMinBudget(e.target.value)}
            placeholder="0"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500"
          />
        </div>

        {/* Фильтр по бюджету (max) */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            💰 До
          </label>
          <input
            type="number"
            value={maxBudget}
            onChange={(e) => setMaxBudget(e.target.value)}
            placeholder="∞"
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500"
          />
        </div>
      </div>

      {/* Кнопка применения */}
      <div className="mt-4 flex justify-end">
        <Button
          onClick={applyFilters}
          variant="primary"
          className="w-full md:w-auto px-8"
        >
          🔎 Применить фильтры
        </Button>
      </div>
    </Card>
  );
}
