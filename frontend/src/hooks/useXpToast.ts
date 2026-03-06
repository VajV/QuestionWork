/**
 * useXpToast — управляет состоянием XP-тоста.
 *
 * Использование:
 *   const { toastState, showXpToast } = useXpToast();
 *   showXpToast({ xp_gained: 150, level_up: true, new_level: 6, classMultiplier: 1.2 });
 *
 * Передай toastState в <XpToast />.
 */

"use client";

import { useState, useRef, useCallback } from "react";

export interface XpToastData {
  xp_gained: number;
  level_up: boolean;
  new_level: number;
  /** Optional class XP multiplier — shown when > 1.0 or < 1.0 */
  classMultiplier?: number;
  /** Class color hex (e.g. "#f59e0b") for the multiplier label */
  classColor?: string;
}

interface UseXpToastResult {
  toastState: XpToastData | null;
  showXpToast: (data: XpToastData) => void;
  hideXpToast: () => void;
}

const TOAST_DURATION_MS = 3500;

export function useXpToast(): UseXpToastResult {
  const [toastState, setToastState] = useState<XpToastData | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const hideXpToast = useCallback(() => {
    setToastState(null);
  }, []);

  const showXpToast = useCallback(
    (data: XpToastData) => {
      // Cancel any existing timer
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      setToastState(data);
      timerRef.current = setTimeout(() => {
        setToastState(null);
        timerRef.current = null;
      }, TOAST_DURATION_MS);
    },
    [],
  );

  return { toastState, showXpToast, hideXpToast };
}
