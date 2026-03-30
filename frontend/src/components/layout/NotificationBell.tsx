"use client";

/**
 * NotificationBell — shows unread notification count badge in the header.
 *
 * Clicking it opens a dropdown panel with recent notifications and
 * a "Mark all as read" action.
 */

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useNotifications } from "@/hooks/useNotifications";
import type { Notification } from "@/lib/api";

interface NotificationBellProps {
  /** Enable polling (only when user is authenticated). */
  enabled?: boolean;
}

export default function NotificationBell({
  enabled = true,
}: NotificationBellProps) {
  const { notifications, unreadCount, loading, error, markRead, markAllRead, refresh } =
    useNotifications(enabled);
  const [open, setOpen] = useState(false);
  const [selectedNotification, setSelectedNotification] = useState<Notification | null>(null);
  const [mounted, setMounted] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeModalButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Close panel when clicking outside
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  useEffect(() => {
    if (!selectedNotification) {
      return;
    }

    closeModalButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSelectedNotification(null);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [selectedNotification]);

  const handleOpenNotification = async (notification: Notification) => {
    setSelectedNotification(notification);
    setOpen(false);
    if (!notification.is_read) {
      await markRead(notification.id);
    }
  };

  const notificationModal = selectedNotification ? (
    <div className="fixed inset-0 z-[999] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="notification-dialog-title"
        className="w-full max-w-lg rounded-2xl border border-gray-700 bg-gray-900 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-gray-800 px-5 py-4">
          <div className="min-w-0 flex-1">
            <h3 id="notification-dialog-title" className="text-base font-semibold text-white break-words">
              {selectedNotification.title}
            </h3>
            <p className="mt-1 text-xs text-gray-500">
              {new Date(selectedNotification.created_at).toLocaleString("ru-RU")}
            </p>
          </div>
          <button
            ref={closeModalButtonRef}
            type="button"
            aria-label="Закрыть уведомление"
            onClick={() => setSelectedNotification(null)}
            className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-white"
          >
            ✕
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">
          <p className="whitespace-pre-wrap break-words text-sm leading-6 text-gray-300">
            {selectedNotification.message}
          </p>
        </div>
        <div className="flex justify-between gap-3 border-t border-gray-800 px-5 py-4">
          <Link
            href="/notifications"
            className="text-sm text-amber-400 hover:underline"
            onClick={() => {
              setSelectedNotification(null);
              setOpen(false);
            }}
          >
            Открыть центр уведомлений
          </Link>
          <button
            type="button"
            onClick={() => setSelectedNotification(null)}
            className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 transition-colors hover:bg-gray-800"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  ) : null;

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell button */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={`Уведомления${unreadCount > 0 ? ` (${unreadCount} непрочитанных)` : ""}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="relative p-2 rounded-full hover:bg-gray-800 transition-colors"
      >
        <svg
          className="w-5 h-5 text-gray-300"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-red-500 rounded-full">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          role="dialog"
          aria-label="Список уведомлений"
          className="absolute right-0 mt-2 w-80 max-h-96 overflow-y-auto bg-gray-900 rounded-xl shadow-lg border border-gray-700 z-50"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
            <Link
              href="/notifications"
              className="font-semibold text-sm text-gray-100 hover:text-amber-400 transition-colors"
              onClick={() => setOpen(false)}
            >
              Уведомления
            </Link>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                className="text-xs text-amber-400 hover:underline"
              >
                Прочитать все
              </button>
            )}
          </div>

          {/* Body */}
          {loading && notifications.length === 0 ? (
            <p className="p-4 text-sm text-gray-400">
              Загружаем…
            </p>
          ) : error ? (
            <div className="p-4 space-y-2">
              <p className="text-sm text-red-400">{error}</p>
              <button
                type="button"
                onClick={refresh}
                className="inline-flex mr-3 text-xs text-amber-400 hover:underline"
              >
                Повторить
              </button>
              <Link
                href="/notifications"
                className="inline-flex text-xs text-amber-400 hover:underline"
                onClick={() => setOpen(false)}
              >
                Открыть центр уведомлений
              </Link>
            </div>
          ) : notifications.length === 0 ? (
            <p className="p-4 text-sm text-gray-400">
              Пока уведомлений нет.
            </p>
          ) : (
            <ul>
              {notifications.slice(0, 20).map((n) => (
                <NotifItem key={n.id} notification={n} onOpen={handleOpenNotification} />
              ))}
            </ul>
          )}


        </div>
      )}

      {mounted && notificationModal ? createPortal(notificationModal, document.body) : null}
    </div>
  );
}

function NotifItem({
  notification: n,
  onOpen,
}: {
  notification: Notification;
  onOpen: (notification: Notification) => void | Promise<void>;
}) {
  return (
    <li className="border-b last:border-0 border-gray-700">
      <button
        type="button"
        aria-label={`Открыть уведомление: ${n.title}`}
        className={`w-full px-4 py-3 text-left hover:bg-gray-800/50 transition-colors ${
          !n.is_read ? "bg-amber-900/20" : ""
        }`}
        onClick={() => void onOpen(n)}
      >
        <p className="text-sm font-medium text-gray-100">
          {n.title}
        </p>
        <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">
          {n.message}
        </p>
        {!n.is_read && (
          <span className="inline-block mt-1 w-2 h-2 rounded-full bg-amber-500" />
        )}
      </button>
    </li>
  );
}
