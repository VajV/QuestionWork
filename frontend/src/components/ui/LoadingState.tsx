"use client";

import React from "react";

interface LoadingStateProps {
  /** Text shown under the spinner */
  label?: string;
  /** Full-page (default) or inline mode */
  inline?: boolean;
  className?: string;
}

/**
 * Unified loading indicator — replaces scattered spinners / skeleton text.
 * L-01: single reusable component for consistent loading UX.
 */
export default function LoadingState({
  label = "Загрузка…",
  inline = false,
  className = "",
}: LoadingStateProps) {
  if (inline) {
    return (
      <div className={`flex items-center gap-2 ${className}`} role="status" aria-live="polite">
        <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
        <span className="text-sm text-gray-400">{label}</span>
      </div>
    );
  }

  return (
    <div
      className={`rounded-2xl border border-gray-800 bg-gray-900/60 p-10 text-center ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className="mx-auto mb-4 h-12 w-12 rounded-full border-4 border-amber-500 border-t-transparent animate-spin" />
      <p className="text-gray-400">{label}</p>
    </div>
  );
}
