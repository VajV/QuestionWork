/**
 * /events — список сезонных ивентов
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import Header from "@/components/layout/Header";
import EventCard from "@/components/events/EventCard";
import { getEvents, joinEvent } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { GameEvent, EventStatus } from "@/types";

const STATUS_TABS: { label: string; value: EventStatus | "" }[] = [
  { label: "Все", value: "" },
  { label: "Активные", value: "active" },
  { label: "Завершённые", value: "ended" },
  { label: "С итогами", value: "finalized" },
];

const PAGE_SIZE = 12;

export default function EventsPage() {
  const { isAuthenticated } = useAuth();
  const [events, setEvents] = useState<GameEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<EventStatus | "">("");
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [joinedIds, setJoinedIds] = useState<Set<string>>(new Set());
  const [joinLoading, setJoinLoading] = useState<string | null>(null);

  const fetchEvents = useCallback(
    async (reset = false) => {
      try {
        setLoading(true);
        setError("");
        const newOffset = reset ? 0 : offset;
        const res = await getEvents({
          status: statusFilter || undefined,
          limit: PAGE_SIZE,
          offset: newOffset,
        });
        if (reset) {
          setEvents(res.items);
          setOffset(res.items.length);
        } else {
          setEvents((prev) => [...prev, ...res.items]);
          setOffset((prev) => prev + res.items.length);
        }
        setTotal(res.total);
        setHasMore(res.has_more);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Ошибка загрузки");
      } finally {
        setLoading(false);
      }
    },
    [statusFilter, offset]
  );

  useEffect(() => {
    setOffset(0);
    setEvents([]);
    const load = async () => {
      try {
        setLoading(true);
        setError("");
        const res = await getEvents({
          status: statusFilter || undefined,
          limit: PAGE_SIZE,
          offset: 0,
        });
        setEvents(res.items);
        setOffset(res.items.length);
        setTotal(res.total);
        setHasMore(res.has_more);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Ошибка загрузки");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [statusFilter]);

  const handleJoin = useCallback(
    async (eventId: string) => {
      if (!isAuthenticated) return;
      try {
        setJoinLoading(eventId);
        await joinEvent(eventId);
        setJoinedIds((prev) => new Set(prev).add(eventId));
        setEvents((prev) =>
          prev.map((e) =>
            e.id === eventId
              ? { ...e, participant_count: e.participant_count + 1 }
              : e
          )
        );
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Ошибка";
        if (msg.includes("Already joined")) {
          setJoinedIds((prev) => new Set(prev).add(eventId));
        } else {
          alert(msg);
        }
      } finally {
        setJoinLoading(null);
      }
    },
    [isAuthenticated]
  );

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-950 via-gray-900 to-gray-950">
      <Header />

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Title */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl md:text-4xl font-cinzel font-bold text-amber-300 tracking-wide mb-2">
            Сезонные ивенты
          </h1>
          <p className="text-gray-400 text-sm max-w-md mx-auto">
            Соревнуйтесь за XP-бонусы, уникальные бейджи и место в таблице лидеров
          </p>
        </div>

        {/* Status tabs */}
        <div className="flex items-center justify-center gap-2 mb-8 flex-wrap">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setStatusFilter(tab.value as EventStatus | "")}
              className={`px-4 py-2 rounded-lg text-sm font-cinzel font-bold tracking-wide transition-all ${
                statusFilter === tab.value
                  ? "bg-amber-600/40 text-amber-300 border border-amber-500/40"
                  : "bg-gray-800/60 text-gray-400 border border-gray-700/40 hover:text-gray-200 hover:border-gray-600/60"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        {error && (
          <div className="text-center py-8">
            <p className="text-red-400 text-sm">{error}</p>
            <button
              onClick={() => fetchEvents(true)}
              className="mt-3 text-xs text-amber-400 hover:underline"
            >
              Попробовать снова
            </button>
          </div>
        )}

        {!error && loading && events.length === 0 && (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!error && !loading && events.length === 0 && (
          <div className="text-center py-16">
            <p className="text-gray-500 text-lg font-cinzel">Ивентов пока нет</p>
            <p className="text-gray-600 text-sm mt-2">
              Скоро здесь будут сезонные челленджи!
            </p>
          </div>
        )}

        {events.length > 0 && (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {events.map((event) => (
                <EventCard
                  key={event.id}
                  event={event}
                  onJoin={isAuthenticated ? handleJoin : undefined}
                  isJoined={joinedIds.has(event.id)}
                  joinLoading={joinLoading === event.id}
                />
              ))}
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between mt-8">
              <p className="text-xs text-gray-500">
                Показано {events.length} из {total}
              </p>
              {hasMore && (
                <button
                  onClick={() => fetchEvents(false)}
                  disabled={loading}
                  className="px-5 py-2 rounded-lg bg-gray-800/60 border border-gray-700/40 text-gray-300 text-sm font-cinzel hover:border-amber-500/40 hover:text-amber-300 transition-all disabled:opacity-50"
                >
                  {loading ? "Загрузка..." : "Ещё"}
                </button>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
