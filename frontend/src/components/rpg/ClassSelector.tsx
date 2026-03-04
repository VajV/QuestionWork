"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Shield, Zap, Lock, Check, AlertTriangle } from "lucide-react";
import type { CharacterClassInfo, ClassListResponse, UserClassInfo } from "@/lib/api";
import { getClasses, selectClass, confirmClass, resetClass, getMyClass } from "@/lib/api";

interface ClassSelectorProps {
  isOpen: boolean;
  onClose: () => void;
  userLevel: number;
  currentClass: string | null;
  onClassSelected?: (classInfo: UserClassInfo) => void;
}

const CLASS_ICONS: Record<string, typeof Shield> = {
  berserk: Zap,
};

export default function ClassSelector({
  isOpen,
  onClose,
  userLevel,
  currentClass,
  onClassSelected,
}: ClassSelectorProps) {
  const [classes, setClasses] = useState<CharacterClassInfo[]>([]);
  const [myClassInfo, setMyClassInfo] = useState<UserClassInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const data: ClassListResponse = await getClasses();
      setClasses(data.classes);
      if (currentClass) {
        try {
          const info = await getMyClass();
          setMyClassInfo(info);
        } catch {
          /* no class yet */
        }
      }
    } catch {
      setError("Не удалось загрузить классы");
    }
  }, [currentClass]);

  useEffect(() => {
    if (isOpen) {
      fetchData();
      setError(null);
      setSuccess(null);
    }
  }, [isOpen, fetchData]);

  const handleSelect = async (classId: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await selectClass(classId);
      setSuccess(result.message);
      setMyClassInfo(result.class_info);
      onClassSelected?.(result.class_info);
    } catch (err) {
      const msg =
        err instanceof Response ? err.statusText : "Ошибка выбора класса";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await confirmClass();
      setSuccess(result.message);
      setMyClassInfo(result.class_info);
      onClassSelected?.(result.class_info);
    } catch (err) {
      const msg =
        err instanceof Response
          ? err.statusText
          : "Ошибка подтверждения класса";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await resetClass();
      setSuccess(result.message);
      setMyClassInfo(null);
      onClassSelected?.(null as unknown as UserClassInfo);
    } catch (err) {
      const msg =
        err instanceof Response ? err.statusText : "Ошибка сброса класса";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="rpg-card w-full max-w-2xl max-h-[85vh] overflow-y-auto m-4"
          initial={{ scale: 0.9, y: 20 }}
          animate={{ scale: 1, y: 0 }}
          exit={{ scale: 0.9, y: 20 }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-amber-900/30">
            <h2 className="text-2xl font-cinzel text-amber-500 flex items-center gap-2">
              <Shield size={28} />
              Выбор класса
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <X size={24} />
            </button>
          </div>

          <div className="p-6 space-y-6">
            {/* Status messages */}
            {error && (
              <div className="p-3 rounded-lg bg-red-900/30 border border-red-500/30 text-red-400 text-sm">
                {error}
              </div>
            )}
            {success && (
              <div className="p-3 rounded-lg bg-emerald-900/30 border border-emerald-500/30 text-emerald-400 text-sm">
                {success}
              </div>
            )}

            {/* Current class info */}
            {myClassInfo && (
              <div
                className="p-4 rounded-lg border"
                style={{
                  borderColor: `${myClassInfo.color}50`,
                  backgroundColor: `${myClassInfo.color}10`,
                }}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{myClassInfo.icon}</span>
                    <div>
                      <h3
                        className="font-cinzel font-bold"
                        style={{ color: myClassInfo.color }}
                      >
                        {myClassInfo.name_ru}
                      </h3>
                      <span className="text-xs text-gray-400">
                        Ур. {myClassInfo.class_level} &bull;{" "}
                        {myClassInfo.class_xp} XP
                        {myClassInfo.is_trial && (
                          <span className="ml-1 text-yellow-400">
                            (пробный период)
                          </span>
                        )}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {myClassInfo.is_trial && (
                      <button
                        onClick={handleConfirm}
                        disabled={loading}
                        className="rpg-button-sm bg-emerald-900/30 border border-emerald-500/50 text-emerald-400 hover:bg-emerald-800/40 px-3 py-1 rounded text-sm flex items-center gap-1"
                      >
                        <Check size={14} />
                        Подтвердить
                      </button>
                    )}
                    <button
                      onClick={handleReset}
                      disabled={loading}
                      className="rpg-button-sm bg-red-900/20 border border-red-500/30 text-red-400 hover:bg-red-800/30 px-3 py-1 rounded text-sm"
                    >
                      Сбросить
                    </button>
                  </div>
                </div>

                {/* XP progress bar */}
                <div className="mt-2">
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>Class XP</span>
                    <span>
                      {myClassInfo.class_xp} / {myClassInfo.class_xp + myClassInfo.class_xp_to_next}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ backgroundColor: myClassInfo.color }}
                      initial={{ width: 0 }}
                      animate={{
                        width: `${
                          myClassInfo.class_xp_to_next > 0
                            ? (myClassInfo.class_xp /
                                (myClassInfo.class_xp + myClassInfo.class_xp_to_next)) *
                              100
                            : 100
                        }%`,
                      }}
                      transition={{ duration: 0.8 }}
                    />
                  </div>
                </div>

                {/* Burnout warning */}
                {myClassInfo.is_burnout && (
                  <div className="mt-3 p-2 rounded bg-orange-900/20 border border-orange-500/30 text-orange-400 text-xs flex items-center gap-2">
                    <AlertTriangle size={14} />
                    Выгорание активно до{" "}
                    {new Date(myClassInfo.burnout_until!).toLocaleString("ru")}
                  </div>
                )}
              </div>
            )}

            {/* Class list */}
            <div className="space-y-4">
              {classes.map((cls) => {
                const isLocked = userLevel < cls.min_unlock_level;
                const isActive = currentClass === cls.class_id;
                const isSelected = selectedClassId === cls.class_id;
                const IconComp = CLASS_ICONS[cls.class_id] || Shield;

                return (
                  <motion.div
                    key={cls.class_id}
                    className={`p-4 rounded-lg border cursor-pointer transition-all ${
                      isLocked
                        ? "opacity-50 cursor-not-allowed border-gray-700 bg-gray-900/30"
                        : isActive
                        ? "border-opacity-70"
                        : "border-gray-700/50 hover:border-opacity-50 bg-gray-900/20"
                    }`}
                    style={
                      !isLocked
                        ? {
                            borderColor: isActive || isSelected ? cls.color : undefined,
                            backgroundColor:
                              isActive || isSelected ? `${cls.color}10` : undefined,
                          }
                        : undefined
                    }
                    onClick={() => {
                      if (!isLocked && !isActive) {
                        setSelectedClassId(
                          isSelected ? null : cls.class_id,
                        );
                      }
                    }}
                    whileHover={!isLocked ? { scale: 1.01 } : undefined}
                  >
                    <div className="flex items-start gap-4">
                      <div
                        className="w-14 h-14 rounded-lg border-2 flex items-center justify-center flex-shrink-0"
                        style={{
                          borderColor: isLocked ? "#374151" : cls.color,
                          backgroundColor: isLocked
                            ? "#11182750"
                            : `${cls.color}15`,
                        }}
                      >
                        {isLocked ? (
                          <Lock size={24} className="text-gray-500" />
                        ) : (
                          <span className="text-2xl">{cls.icon}</span>
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3
                            className="font-cinzel font-bold text-lg"
                            style={{ color: isLocked ? "#6b7280" : cls.color }}
                          >
                            {cls.name_ru}
                          </h3>
                          {isLocked && (
                            <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">
                              Ур. {cls.min_unlock_level}+
                            </span>
                          )}
                          {isActive && (
                            <span className="text-xs text-emerald-400 bg-emerald-900/30 px-2 py-0.5 rounded">
                              Активен
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-400 mb-3">
                          {cls.description_ru}
                        </p>

                        {/* Bonuses */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                          {cls.bonuses.map((b) => (
                            <div
                              key={b.key}
                              className="text-xs flex items-center gap-1"
                            >
                              <span className="text-emerald-400">+</span>
                              <span className="text-gray-300">{b.label}</span>
                            </div>
                          ))}
                          {cls.weaknesses.map((w) => (
                            <div
                              key={w.key}
                              className="text-xs flex items-center gap-1"
                            >
                              <span className="text-red-400">−</span>
                              <span className="text-gray-400">{w.label}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Select button */}
                    {isSelected && !isLocked && !isActive && (
                      <motion.div
                        className="mt-4 flex justify-end"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                      >
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelect(cls.class_id);
                          }}
                          disabled={loading}
                          className="px-4 py-2 rounded font-cinzel text-sm border transition-colors"
                          style={{
                            borderColor: cls.color,
                            color: cls.color,
                            backgroundColor: `${cls.color}15`,
                          }}
                        >
                          {loading
                            ? "Выбираем..."
                            : "Начать пробный период (24ч)"}
                        </button>
                      </motion.div>
                    )}
                  </motion.div>
                );
              })}
            </div>

            {userLevel < 5 && (
              <div className="text-center text-gray-500 text-sm p-4 border border-gray-700/30 rounded-lg">
                <Lock size={20} className="inline mr-2" />
                Система классов доступна с 5 уровня. Ваш уровень: {userLevel}
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
