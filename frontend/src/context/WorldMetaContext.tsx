"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { getWorldMeta, type WorldMetaSnapshot } from "@/lib/api";

interface WorldMetaContextType {
  snapshot: WorldMetaSnapshot | null;
  loading: boolean;
  refreshWorldMeta: () => Promise<void>;
}

const WorldMetaContext = createContext<WorldMetaContextType | undefined>(undefined);

export function WorldMetaProvider({ children }: { children: React.ReactNode }) {
  const [snapshot, setSnapshot] = useState<WorldMetaSnapshot | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshWorldMeta = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getWorldMeta();
      setSnapshot(data);
    } catch {
      // Keep UI resilient; rail components will fall back to local copy if needed.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshWorldMeta();
    const intervalId = window.setInterval(() => {
      void refreshWorldMeta();
    }, 90_000);

    return () => window.clearInterval(intervalId);
  }, [refreshWorldMeta]);

  const value = useMemo(
    () => ({ snapshot, loading, refreshWorldMeta }),
    [snapshot, loading, refreshWorldMeta],
  );

  return <WorldMetaContext.Provider value={value}>{children}</WorldMetaContext.Provider>;
}

export function useWorldMeta() {
  const context = useContext(WorldMetaContext);
  if (!context) {
    throw new Error("useWorldMeta must be used within WorldMetaProvider");
  }
  return context;
}