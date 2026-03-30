/**
 * useMyClass — загружает и кеширует UserClassInfo текущего пользователя.
 *
 * Возвращает { classInfo, loading }.
 * Загрузка происходит один раз при аутентификации; повторный вызов
 * refetch() принудительно обновляет данные.
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { getMyClass } from "@/lib/api";
import type { UserClassInfo } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

interface UseMyClassResult {
  classInfo: UserClassInfo | null;
  loading: boolean;
  refetch: () => Promise<void>;
}

export function useMyClass(): UseMyClassResult {
  const { isAuthenticated, user } = useAuth();
  const [classInfo, setClassInfo] = useState<UserClassInfo | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchClass = useCallback(async () => {
    if (!isAuthenticated) {
      setClassInfo(null);
      return;
    }
    setLoading(true);
    try {
      const info = await getMyClass();
      setClassInfo(info.has_class ? info : null);
    } catch {
      // User has no class or not authenticated — that's fine
      setClassInfo(null);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated && user) {
      fetchClass();
    } else {
      setClassInfo(null);
    }
  }, [isAuthenticated, user, fetchClass]);

  return { classInfo, loading, refetch: fetchClass };
}
