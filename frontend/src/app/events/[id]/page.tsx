/**
 * /events/[id] — детальная страница ивента
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Header from "@/components/layout/Header";
import EventStatusBadge from "@/components/events/EventStatusBadge";
import EventLeaderboard from "@/components/events/EventLeaderboard";
import { getEvent, joinEvent, getApiErrorMessage } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { GameEvent } from "@/types";
import { ArrowLeft, Sparkles, Users, Clock, Trophy, Calendar } from "lucide-react";

function formatTimeLeft(endAt: string): string {
  const diff = new Date(endAt).getTime() - Date.now();
  if (diff <= 0) return "Завершён";
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  if (hours > 0) return `${hours}ч ${minutes}м осталось`;
  return `${minutes}м осталось`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function EventDetailPage() {
  const params = useParams();
  const eventId = params?.id as string;
  const { isAuthenticated } = useAuth();

  const [event, setEvent] = useState<GameEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [joined, setJoined] = useState(false);
  const [joinLoading, setJoinLoading] = useState(false);
  const [timeLeft, setTimeLeft] = useState("");

  const fetchEvent = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getEvent(eventId);
      setEvent(res);
      if (res.status === "active") {
        setTimeLeft(formatTimeLeft(res.end_at));
      }
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Ошибка загрузки"));
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    if (eventId) fetchEvent();
  }, [eventId, fetchEvent]);

  useEffect(() => {
    if (!event || event.status !== "active") return;
    const timer = setInterval(() => setTimeLeft(formatTimeLeft(event.end_at)), 30000);
    return () => clearInterval(timer);
  }, [event]);

  const handleJoin = useCallback(async () => {
    if (!isAuthenticated || !eventId) return;
    try {
      setJoinLoading(true);
      await joinEvent(eventId);
      setJoined(true);
      setEvent((prev) =>
        prev ? { ...prev, participant_count: prev.participant_count + 1 } : prev
      );
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, "Ошибка");
      if (msg.includes("Already joined")) {
        setJoined(true);
      } else {
        setError(msg);
      }
    } finally {
      setJoinLoading(false);
    }
  }, [isAuthenticated, eventId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-950 via-gray-900 to-gray-950">
        <Header />
        <div className="flex items-center justify-center py-32">
          <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (error || !event) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-950 via-gray-900 to-gray-950">
        <Header />
        <div className="max-w-4xl mx-auto px-4 py-16 text-center">
          <p className="text-red-400 text-lg mb-4">{error || "Ивент не найден"}</p>
          <Link href="/events" className="text-amber-400 hover:underline text-sm">
            Вернуться к списку
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-950 via-gray-900 to-gray-950">
      <Header />

      <main className="max-w-4xl mx-auto px-4 py-8">
        {/* Back link */}
        <Link
          href="/events"
          className="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-amber-300 transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Все ивенты
        </Link>

        {/* Header */}
        <div className="rpg-card rounded-xl border border-gray-700/60 bg-gray-900/80 backdrop-blur-sm p-6 mb-6">
          <div className="flex items-start justify-between gap-4 mb-4">
            <EventStatusBadge status={event.status} size="lg" />

            {Number(event.xp_multiplier) > 1 && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/20 border border-amber-500/30">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <span className="text-sm font-bold text-amber-300 font-cinzel">
                  x{Number(event.xp_multiplier)} XP
                </span>
              </div>
            )}
          </div>

          <h1 className="text-2xl md:text-3xl font-cinzel font-bold text-gray-100 mb-4">
            {event.title}
          </h1>

          <p className="text-gray-300 leading-relaxed mb-6 whitespace-pre-wrap">
            {event.description}
          </p>

          {/* Stats row */}
          <div className="flex flex-wrap items-center gap-5 text-sm text-gray-400 mb-6">
            <span className="flex items-center gap-1.5">
              <Users className="w-4 h-4" />
              {event.participant_count} участников
              {event.max_participants && ` из ${event.max_participants}`}
            </span>

            <span className="flex items-center gap-1.5">
              <Calendar className="w-4 h-4" />
              {formatDate(event.start_at)} — {formatDate(event.end_at)}
            </span>

            {event.status === "active" && timeLeft && (
              <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
                <Clock className="w-4 h-4" />
                {timeLeft}
              </span>
            )}

            {event.badge_reward_id && (
              <span className="flex items-center gap-1.5 text-purple-400">
                <Trophy className="w-4 h-4" />
                Бейдж для топ-3
              </span>
            )}
          </div>

          {/* Join button */}
          {event.status === "active" && isAuthenticated && !joined && (
            <button
              onClick={handleJoin}
              disabled={joinLoading}
              className="px-6 py-3 rounded-lg bg-emerald-600/80 hover:bg-emerald-500/80 text-white font-cinzel font-bold tracking-wide transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {joinLoading ? "Присоединяемся..." : "Участвовать в ивенте"}
            </button>
          )}

          {joined && event.status === "active" && (
            <div className="px-6 py-3 rounded-lg bg-amber-600/20 border border-amber-500/30 text-amber-300 font-cinzel font-bold tracking-wide inline-block">
              Вы участвуете!
            </div>
          )}

          {!isAuthenticated && event.status === "active" && (
            <Link
              href="/auth/login"
              className="inline-block px-6 py-3 rounded-lg bg-gray-800/60 border border-gray-700/40 text-gray-300 font-cinzel font-bold tracking-wide hover:border-amber-500/40 hover:text-amber-300 transition-all"
            >
              Войдите, чтобы участвовать
            </Link>
          )}
        </div>

        {/* Leaderboard */}
        <div className="rpg-card rounded-xl border border-gray-700/60 bg-gray-900/80 backdrop-blur-sm p-6">
          <EventLeaderboard eventId={eventId} />
        </div>
      </main>
    </div>
  );
}
