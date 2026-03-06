/**
 * QuestChat — inline chat panel for quest participants.
 *
 * Visible only when quest is in_progress / completed / confirmed
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
import { getQuestMessages, sendQuestMessage, QuestMessage } from "@/lib/api";
import { MessageCircle, Send, ChevronUp, Loader2 } from "lucide-react";

interface QuestChatProps {
  questId: string;
  currentUserId: string;
}

const POLL_INTERVAL_MS = 10_000;

export default function QuestChat({ questId, currentUserId }: QuestChatProps) {
  const [messages, setMessages] = useState<QuestMessage[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const latestRef = useRef<string | null>(null);

  // Scroll to bottom when messages change
  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Fetch messages
  const fetchMessages = useCallback(
    async (silent = false) => {
      try {
        if (!silent) setLoading(true);
        const res = await getQuestMessages(questId, 50);
        setMessages(res.messages);
        setTotal(res.total);
        if (res.messages.length > 0) {
          latestRef.current = res.messages[res.messages.length - 1].created_at;
        }
      } catch {
        if (!silent) setError("Не удалось загрузить сообщения");
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
    pollRef.current = setInterval(() => fetchMessages(true), POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchMessages]);

  // Load earlier messages
  const loadEarlier = async () => {
    if (messages.length === 0) return;
    const oldest = messages[0].created_at;
    try {
      const res = await getQuestMessages(questId, 50, oldest);
      if (res.messages.length > 0) {
        setMessages((prev) => [...res.messages, ...prev]);
        setTotal(res.total);
      }
    } catch {
      // silently ignore
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
      id: `tmp_${Date.now()}`,
      quest_id: questId,
      author_id: currentUserId,
      author_username: null,
      text: trimmed,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);

    try {
      const real = await sendQuestMessage(questId, { text: trimmed });
      setMessages((prev) =>
        prev.map((m) => (m.id === optimistic.id ? real : m)),
      );
    } catch {
      setError("Ошибка отправки");
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
        <h2 className="text-xl font-cinzel font-bold text-purple-400 flex items-center gap-3">
          <MessageCircle className="w-5 h-5 opacity-70" />
          Чат квеста
          {total > 0 && (
            <span className="text-xs font-mono bg-purple-900/40 text-purple-300 px-2 py-0.5 rounded ml-1">
              {total}
            </span>
          )}
        </h2>
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
                className="w-full text-center py-2 text-xs text-purple-400 hover:text-purple-300 font-mono transition-colors"
              >
                ↑ Загрузить ранние
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
            <div className="mx-5 mb-2 text-xs text-red-400 font-mono">
              {error}
            </div>
          )}

          {/* Input */}
          <div className="border-t border-gray-800 p-4 flex gap-3 items-end">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              maxLength={5000}
              placeholder="Написать сообщение..."
              className="flex-1 bg-black/40 border border-gray-800 focus:border-purple-600 rounded-lg px-4 py-2.5 text-sm text-gray-200 placeholder-gray-600 resize-none outline-none transition-colors font-inter"
            />
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
