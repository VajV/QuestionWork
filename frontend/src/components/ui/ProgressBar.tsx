"use client";

import { motion } from "framer-motion";

interface ProgressBarProps {
  value: number;
  max: number;
  label?: string;
  color?: 'purple' | 'green' | 'blue' | 'red' | 'emerald' | 'amber';
  showPercent?: boolean;
  className?: string;
}

export default function ProgressBar({
  value,
  max,
  label,
  color = 'purple',
  showPercent = true,
  className = '',
}: ProgressBarProps) {
  const percent = Math.min((value / max) * 100, 100);
  
  const colorStyles = {
    purple: 'from-purple-600 to-purple-400 shadow-purple-500/30',
    green: 'from-green-600 to-green-400 shadow-green-500/30',
    blue: 'from-blue-600 to-blue-400 shadow-blue-500/30',
    red: 'from-red-600 to-red-400 shadow-red-500/30', emerald: 'from-emerald-600 to-emerald-400 shadow-emerald-500/30', amber: 'from-amber-600 to-amber-400 shadow-amber-500/30',
  };

  return (
    <div className={`w-full ${className}`}>
      {(label || showPercent) && (
        <div className="flex justify-between text-sm mb-1">
          {label && <span className="text-gray-300">{label}</span>}
          {showPercent && (
            <span className="text-gray-300">{Math.round(percent)}%</span>
          )}
        </div>
      )}
      <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className={`h-full bg-gradient-to-r ${colorStyles[color]} shadow-lg`}
        />
      </div>
    </div>
  );
}
