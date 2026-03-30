"use client";

/**
 * useNotifications — polls /notifications every 30 seconds,
 * and upgrades to WebSocket push when available.
 *
 * Returns the notification list, unread count, and helper actions to
 * mark individual or all notifications as read.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import {
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  createNotificationsWsTicket,
  getApiErrorMessage,
  getApiErrorStatus,
} from "@/lib/api";
import type { Notification } from "@/lib/api";

const POLL_INTERVAL_MS = 30_000;

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function resolveNotificationsWsUrl(): string | null {
  const configured =
    typeof process !== "undefined" ? process.env?.NEXT_PUBLIC_WS_URL?.trim() : undefined;

  if (!configured) {
    return null;
  }

  try {
    const url = new URL(configured);
    if (url.protocol === "http:") {
      url.protocol = "ws:";
    } else if (url.protocol === "https:") {
      url.protocol = "wss:";
    }
    return trimTrailingSlash(url.toString());
  } catch {
    return null;
  }
}

export interface UseNotificationsReturn {
  notifications: Notification[];
  unreadCount: number;
  loading: boolean;
  error: string | null;
  markRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
  refresh: () => void;
}

export function useNotifications(enabled = true): UseNotificationsReturn {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const visibleRef = useRef(true);
  const wsRef = useRef<WebSocket | null>(null);
  const notificationsWsUrlRef = useRef<string | null>(resolveNotificationsWsUrl());

  const fetch = useCallback(async () => {
    if (!enabled || !visibleRef.current) return;
    try {
      setLoading(true);
      const data = await getNotifications(50, 0, false);
      setNotifications(data.notifications);
      setUnreadCount(data.unread_count);
      setError(null);
    } catch (err: unknown) {
      // Silently ignore auth errors (e.g. user not logged in)
      if (getApiErrorStatus(err) !== 401) {
        setError(getApiErrorMessage(err, "Не удалось загрузить уведомления"));
      }
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;

    const handleVisibilityChange = () => {
      visibleRef.current = !document.hidden;
      if (visibleRef.current) {
        void fetch();
      }
    };

    visibleRef.current = !document.hidden;
    document.addEventListener("visibilitychange", handleVisibilityChange);
    void fetch();  // Always fetch on mount, regardless of visibility
    timerRef.current = setInterval(fetch, POLL_INTERVAL_MS);

    // WebSocket upgrade — supplements polling with real-time push
    const notificationsWsUrl = notificationsWsUrlRef.current;
    let isDisposed = false;

    const connectWebSocket = async () => {
      if (!notificationsWsUrl) {
        return;
      }

      try {
        const ticket = await createNotificationsWsTicket();
        if (isDisposed) {
          return;
        }

        const ws = new WebSocket(`${notificationsWsUrl}/ws/notifications`);
        wsRef.current = ws;

        ws.onopen = () => {
          ws.send(JSON.stringify({ type: "auth", ticket: ticket.ticket }));
        };

        ws.onmessage = (ev: MessageEvent) => {
          try {
            const notif = JSON.parse(ev.data as string) as Notification;
            setNotifications((prev) => {
              if (prev.some((n) => n.id === notif.id)) return prev;
              return [notif, ...prev.slice(0, 49)];
            });
            setUnreadCount((c) => c + 1);
          } catch {
            // Ignore malformed payloads
          }
        };

        ws.onerror = () => {
          wsRef.current = null;
        };
        ws.onclose = () => {
          wsRef.current = null;
        };
      } catch {
        // Polling remains the fallback path.
      }
    };

    void connectWebSocket();

    return () => {
      isDisposed = true;
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (timerRef.current) clearInterval(timerRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    }
  }, [enabled, fetch]);

  const markRead = useCallback(
    async (id: string) => {
      await markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    },
    [],
  );

  const markAllRead = useCallback(async () => {
    await markAllNotificationsRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
  }, []);

  return {
    notifications,
    unreadCount,
    loading,
    error,
    markRead,
    markAllRead,
    refresh: fetch,
  };
}
