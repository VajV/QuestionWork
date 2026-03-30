"use client";

import { motion } from "@/lib/motion";

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
    purple: 'stat-bar-fill-int shadow-purple-500/50',
    green: 'bg-gradient-to-r from-green-600 to-green-400 shadow-green-500/50',
    blue: 'stat-bar-fill-int shadow-blue-500/50',
    red: 'bg-gradient-to-r from-red-600 to-red-400 shadow-red-500/50',
    emerald: 'stat-bar-fill-dex shadow-emerald-500/50',
    amber: 'stat-bar-fill-cha shadow-amber-500/50',
  };

  return (
    <div className={`w-full ${className}`}>
      {(label || showPercent) && (
        <div className="flex justify-between font-mono text-sm mb-1 uppercase tracking-widest text-gray-400">
          {label && <span>{label}</span>}
          {showPercent && (
            <span>{Math.round(percent)}%</span>
          )}
        </div>
      )}
      <div className="stat-bar border-gray-700 h-3">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className={`stat-bar-fill ${colorStyles[color]} shadow-[0_0_8px_currentColor]`}
        />
      </div>
    </div>
  );
}
