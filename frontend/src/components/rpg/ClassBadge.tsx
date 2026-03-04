"use client";

import { motion } from "framer-motion";
import type { UserClassInfo } from "@/lib/api";

interface ClassBadgeProps {
  classInfo: UserClassInfo;
  size?: "sm" | "md" | "lg";
  showLevel?: boolean;
}

const CLASS_COLORS: Record<string, string> = {
  berserk: "#dc2626",
};

export default function ClassBadge({
  classInfo,
  size = "md",
  showLevel = true,
}: ClassBadgeProps) {
  const color = CLASS_COLORS[classInfo.class_id] || classInfo.color;
  const sizeClasses = {
    sm: "w-8 h-8 text-sm",
    md: "w-12 h-12 text-lg",
    lg: "w-16 h-16 text-2xl",
  };
  const levelSize = {
    sm: "text-[10px]",
    md: "text-xs",
    lg: "text-sm",
  };

  return (
    <div className="flex items-center gap-2">
      <motion.div
        className={`relative ${sizeClasses[size]} rounded-lg border-2 flex items-center justify-center`}
        style={{
          borderColor: color,
          backgroundColor: `${color}15`,
          boxShadow: `0 0 12px ${color}40`,
        }}
        whileHover={{ scale: 1.1 }}
        transition={{ type: "spring", stiffness: 400 }}
      >
        <span>{classInfo.icon}</span>
        {classInfo.is_burnout && (
          <div
            className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-orange-500 animate-pulse"
            title="Выгорание активно"
          />
        )}
        {classInfo.is_trial && (
          <div
            className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-yellow-400 animate-pulse"
            title="Пробный период"
          />
        )}
      </motion.div>
      {showLevel && (
        <div className="flex flex-col">
          <span
            className="font-cinzel font-bold tracking-wide"
            style={{ color }}
          >
            {classInfo.name_ru}
          </span>
          <span className={`${levelSize[size]} text-gray-400`}>
            Ур. {classInfo.class_level}
            {classInfo.is_trial && (
              <span className="ml-1 text-yellow-400">(пробный)</span>
            )}
          </span>
        </div>
      )}
    </div>
  );
}
