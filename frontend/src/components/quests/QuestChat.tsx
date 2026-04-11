/**
 * QuestChat — inline chat panel for quest participants.
 *
 * Visible only when quest is assigned / in_progress / completed / revision_requested / confirmed
 * and the current user is either the client or the assigned freelancer.
 *
 * Features:
 * - Chronological message list with auto-scroll
 * - 10-second polling for new messages
 * - Optimistic send (immediate local append)
 * - Cursor-based "load earlier" pagination
 */

"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { createQuestChatWsTicket, getApiErrorMessage, getQuestMessages, sendQuestMessage, QuestMessage } from "@/lib/api";
import { MessageCircle, Send, ChevronUp, Loader2 } from "lucide-react";

interface QuestChatProps {
  questId: string;
  currentUserId: string;
}

const POLL_INTERVAL_MS = 10_000;
const WS_BASE_URL = (() => {
  if (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL;
  }
  const apiUrl =
    (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) || "http://127.0.0.1:8001/api/v1";
  const origin = apiUrl.replace(/\/api\/v1\/?$/, "");
  return origin.replace(/^https:/, "wss:").replace(/^http:/, "ws:");
})();

export default function QuestChat({ questId, currentUserId }: QuestChatProps) {
  const [messages, setMessages] = useState<QuestMessage[]>([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [loadingEarlier, setLoadingEarlier] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const latestRef = useRef<string | null>(null);
  const visibleRef = useRef(true);
  const wsRef = useRef<WebSocket | null>(null);

  // Scroll to bottom when messages change
  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Fetch messages
  const fetchMessages = useCallback(
    async (silent = false) => {
      try {
        if (!visibleRef.current && silent) return;
        if (!silent) setLoading(true);
        const res = await getQuestMessages(questId, 50);
        // P2-28: preserve pending optimistic messages during poll
        setMessages((prev) => {
          const pending = prev.filter((m) => m.id.startsWith("tmp_"));
          if (pending.length === 0) return res.messages;
          const serverIds = new Set(res.messages.map((m) => m.id));
          const stillPending = pending.filter((m) => !serverIds.has(m.id));
          return [...res.messages, ...stillPending];
        });
        setTotal(res.total);
        setUnreadCount(res.unread_count);
        if (silent) {
          setError(null);
        }
        if (res.messages.length > 0) {
          latestRef.current = res.messages[res.messages.length - 1].created_at;
        }
      } catch (err: unknown) {
        if (!silent) setError(getApiErrorMessage(err, "Не удалось загрузить сообщения"));
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [questId],
  );

  // Initial load
  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  // Auto-scroll on new messages
  useEffect(() => {
    scrollToBottom();
  }, [messages.length, scrollToBottom]);

  // Polling
  useEffect(() => {
    const handleVisibilityChange = () => {
      visibleRef.current = !document.hidden;
      if (visibleRef.current) {
        void fetchMessages(true);
      }
    };

    visibleRef.current = !document.hidden;
    document.addEventListener("visibilitychange", handleVisibilityChange);
    pollRef.current = setInterval(() => fetchMessages(true), POLL_INTERVAL_MS);

    // WebSocket upgrade — supplements polling with real-time push
    let isDisposed = false;

    const connectWebSocket = async () => {
      try {
        const ticket = await createQuestChatWsTicket(questId);
        if (isDisposed) {
          return;
        }

        const ws = new WebSocket(`${WS_BASE_URL}/ws/chat/${questId}`);
        wsRef.current = ws;

        ws.onopen = () => {
          ws.send(JSON.stringify({ type: "auth", ticket: ticket.ticket }));
        };

        ws.onmessage = (ev: MessageEvent) => {
          try {
            const msg = JSON.parse(ev.data as string) as QuestMessage;
            setMessages((prev) => {
              if (prev.some((m) => m.id === msg.id)) return prev;
              return [...prev, msg];
            });
          } catch {
            // Ignore malformed payloads
          }
        };

        ws.onerror = () => { wsRef.current = null; };
        ws.onclose = () => { wsRef.current = null; };
      } catch {
        // Polling remains the fallback path.
      }
    };

    void connectWebSocket();

    return () => {
      isDisposed = true;
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (pollRef.current) clearInterval(pollRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [fetchMessages, questId]);

  // Load earlier messages
  const loadEarlier = async () => {
    if (messages.length === 0) return;
    const oldest = messages[0].created_at;
    try {
      setLoadingEarlier(true);
      const res = await getQuestMessages(questId, 50, oldest);
      if (res.messages.length > 0) {
        setMessages((prev) => [...res.messages, ...prev]);
        setTotal(res.total);
        setUnreadCount(res.unread_count);
      }
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Не удалось загрузить ранние сообщения"));
    } finally {
      setLoadingEarlier(false);
    }
  };

  // Send message
  const handleSend = async () => {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    setSending(true);
    setError(null);
    setText("");

    // Optimistic append
    const optimistic: QuestMessage = {
      id: `tmp_${crypto.randomUUID()}`,
      quest_id: questId,
      author_id: currentUserId,
      author_username: null,
      text: trimmed,
      created_at: new Date().toISOString(),
      message_type: "user",
    };
    setMessages((prev) => [...prev, optimistic]);

    try {
      const real = await sendQuestMessage(questId, { text: trimmed });
      setMessages((prev) =>
        prev.map((m) => (m.id === optimistic.id ? real : m)),
      );
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Ошибка отправки"));
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setText(trimmed);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString("ru-RU", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="rpg-card overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between p-5 hover:bg-purple-900/10 transition-colors"
      >
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-cinzel font-bold text-purple-400 flex items-center gap-3">
            <MessageCircle className="w-5 h-5 opacity-70" />
            Чат квеста
            {total > 0 && (
              <span className="text-xs font-mono bg-purple-900/40 text-purple-300 px-2 py-0.5 rounded ml-1">
                {total}
              </span>
            )}
          </h2>
          {unreadCount > 0 && (
            <span className="rounded-full bg-amber-500/20 px-2 py-1 text-[10px] font-mono text-amber-300">
              +{unreadCount} новых
            </span>
          )}
          <Link
            href="/messages"
            className="hidden rounded-lg border border-gray-800 px-2 py-1 text-[10px] font-mono uppercase tracking-wider text-gray-400 hover:border-purple-700/40 hover:text-purple-300 md:inline-flex"
            onClick={(e) => e.stopPropagation()}
          >
            Диалоги
          </Link>
        </div>
        <ChevronUp
          className={`w-5 h-5 text-gray-500 transition-transform ${collapsed ? "rotate-180" : ""}`}
        />
      </button>

      {!collapsed && (
        <>
          {/* Messages area */}
          <div
            ref={containerRef}
            className="max-h-80 overflow-y-auto px-5 pb-3 space-y-3 scrollbar-thin scrollbar-thumb-purple-900/40"
          >
            {/* Load earlier */}
            {messages.length < total && (
              <button
                onClick={loadEarlier}
                disabled={loadingEarlier}
                className="w-full text-center py-2 text-xs text-purple-400 hover:text-purple-300 font-mono transition-colors"
              >
                {loadingEarlier ? "Загружаем историю..." : "↑ Загрузить ранние"}
              </button>
            )}

            {loading && messages.length === 0 ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-6 h-6 text-purple-500 animate-spin" />
              </div>
            ) : messages.length === 0 ? (
              <p className="text-center text-gray-500 font-mono text-sm py-8">
                Сообщений пока нет — начните общение!
              </p>
            ) : (
              messages.map((msg) => {
                if (msg.message_type === "system") {
                  return (
                    <div key={msg.id} className="flex flex-col items-center">
                      <div className="max-w-[90%] rounded-full border border-amber-500/20 bg-amber-950/10 px-4 py-2 text-center text-xs text-amber-200">
                        ✨ {msg.text}
                      </div>
                      <span className="text-[10px] text-gray-600 font-mono mt-1 px-1">
                        {formatTime(msg.created_at)}
                      </span>
                    </div>
                  );
                }

                const isMine = msg.author_id === currentUserId;
                return (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${isMine ? "items-end" : "items-start"}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg px-4 py-2.5 ${
                        isMine
                          ? "bg-purple-900/40 border border-purple-700/40 text-gray-200"
                          : "bg-black/50 border border-gray-800 text-gray-300"
                      }`}
                    >
                      {!isMine && msg.author_username && (
                        <p className="text-xs font-cinzel font-bold text-amber-500 mb-1">
                          {msg.author_username}
                        </p>
                      )}
                      <p className="text-sm whitespace-pre-wrap break-words leading-relaxed">
                        {msg.text}
                      </p>
                    </div>
                    <span className="text-[10px] text-gray-600 font-mono mt-1 px-1">
                      {formatTime(msg.created_at)}
                    </span>
                  </div>
                );
              })
            )}
            <div ref={bottomRef} />
          </div>

          {/* Error */}
          {error && (
            <div className="mx-5 mb-2 flex items-center justify-between gap-3 rounded-lg border border-red-500/20 bg-red-950/10 px-3 py-2 text-xs text-red-300 font-mono">
              <span>{error}</span>
              <button
                type="button"
                onClick={() => fetchMessages()}
                className="text-amber-300 hover:underline"
              >
                Повторить
              </button>
            </div>
          )}

          {/* Input */}
          <div className="border-t border-gray-800 p-4 flex gap-3 items-end">
            <div className="flex-1">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                maxLength={5000}
                placeholder="Написать сообщение..."
                className="w-full bg-black/40 border border-gray-800 focus:border-purple-600 rounded-lg px-4 py-2.5 text-sm text-gray-200 placeholder-gray-600 resize-none outline-none transition-colors font-inter"
              />
              <div className="mt-1 flex items-center justify-between text-[10px] text-gray-600 font-mono">
                <span>Enter — отправить, Shift+Enter — новая строка</span>
                <span>{text.length}/5000</span>
              </div>
            </div>
            <button
              onClick={handleSend}
              disabled={!text.trim() || sending}
              className="shrink-0 p-2.5 rounded-lg bg-purple-800/60 hover:bg-purple-700/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors border border-purple-700/40"
              title="Отправить"
            >
              {sending ? (
                <Loader2 className="w-5 h-5 text-purple-300 animate-spin" />
              ) : (
                <Send className="w-5 h-5 text-purple-300" />
              )}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
