"use client";

/**
 * NotificationBell — shows unread notification count badge in the header.
 *
 * Clicking it opens a dropdown panel with recent notifications and
 * a "Mark all as read" action.
 */

import { useState, useRef, useEffect } from "react";
import { useNotifications } from "@/hooks/useNotifications";
import type { Notification } from "@/lib/api";

interface NotificationBellProps {
  /** Enable polling (only when user is authenticated). */
  enabled?: boolean;
}

export default function NotificationBell({
  enabled = true,
}: NotificationBellProps) {
  const { notifications, unreadCount, loading, markRead, markAllRead } =
    useNotifications(enabled);
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

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

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell button */}
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
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
        <div className="absolute right-0 mt-2 w-80 max-h-96 overflow-y-auto bg-gray-900 rounded-xl shadow-lg border border-gray-700 z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
            <span className="font-semibold text-sm text-gray-100">
              Notifications
            </span>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                className="text-xs text-amber-400 hover:underline"
              >
                Mark all as read
              </button>
            )}
          </div>

          {/* Body */}
          {loading && notifications.length === 0 ? (
            <p className="p-4 text-sm text-gray-400">
              Loading…
            </p>
          ) : notifications.length === 0 ? (
            <p className="p-4 text-sm text-gray-400">
              No notifications yet.
            </p>
          ) : (
            <ul>
              {notifications.slice(0, 20).map((n) => (
                <NotifItem key={n.id} notification={n} onRead={markRead} />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function NotifItem({
  notification: n,
  onRead,
}: {
  notification: Notification;
  onRead: (id: string) => void;
}) {
  return (
    <li
      className={`px-4 py-3 border-b last:border-0 border-gray-700 cursor-pointer hover:bg-gray-800/50 transition-colors ${
        !n.is_read ? "bg-amber-900/20" : ""
      }`}
      onClick={() => !n.is_read && onRead(n.id)}
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
    </li>
  );
}
