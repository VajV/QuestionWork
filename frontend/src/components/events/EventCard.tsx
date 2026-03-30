/**
 * EventCard — карточка ивента для ленты
 */

"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "@/lib/motion";
import { GameEvent } from "@/types";
import EventStatusBadge from "./EventStatusBadge";
import { Sparkles, Users, Clock, Trophy } from "lucide-react";

interface EventCardProps {
  event: GameEvent;
  onJoin?: (eventId: string) => void;
  isJoined?: boolean;
  joinLoading?: boolean;
}

function formatTimeLeft(endAt: string): string {
  const diff = new Date(endAt).getTime() - Date.now();
  if (diff <= 0) return "Завершён";
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  if (hours > 0) return `${hours}ч ${minutes}м`;
  return `${minutes}м`;
}

function EventCardInner({ event, onJoin, isJoined = false, joinLoading = false }: EventCardProps) {
  const [timeLeft, setTimeLeft] = useState(() => formatTimeLeft(event.end_at));

  useEffect(() => {
    if (event.status !== "active") return;
    const timer = setInterval(() => setTimeLeft(formatTimeLeft(event.end_at)), 30000);
    return () => clearInterval(timer);
  }, [event.end_at, event.status]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="rpg-card group relative overflow-hidden rounded-xl border border-gray-700/60 bg-gray-900/80 backdrop-blur-sm p-5 hover:border-amber-500/40 transition-all duration-300"
    >
      {/* XP multiplier glow */}
      {Number(event.xp_multiplier) > 1 && (
        <div className="absolute top-3 right-3 flex items-center gap-1 px-2 py-1 rounded-lg bg-amber-500/20 border border-amber-500/30">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-xs font-bold text-amber-300 font-cinzel">
            x{Number(event.xp_multiplier)} XP
          </span>
        </div>
      )}

      <div className="flex items-start gap-3 mb-3">
        <EventStatusBadge status={event.status} size="sm" />
      </div>

      <Link href={`/events/${event.id}`} className="block">
        <h3 className="text-lg font-cinzel font-bold text-gray-100 mb-2 group-hover:text-amber-300 transition-colors line-clamp-2">
          {event.title}
        </h3>
      </Link>

      <p className="text-sm text-gray-400 mb-4 line-clamp-2">
        {event.description}
      </p>

      <div className="flex items-center gap-4 text-xs text-gray-500 mb-4">
        <span className="flex items-center gap-1">
          <Users className="w-3.5 h-3.5" />
          {event.participant_count}
          {event.max_participants && `/${event.max_participants}`}
        </span>

        {event.status === "active" && (
          <span className="flex items-center gap-1 text-emerald-400">
            <Clock className="w-3.5 h-3.5" />
            {timeLeft}
          </span>
        )}

        {event.badge_reward_id && (
          <span className="flex items-center gap-1 text-purple-400">
            <Trophy className="w-3.5 h-3.5" />
            Бейдж
          </span>
        )}
      </div>

      {event.status === "active" && onJoin && !isJoined && (
        <button
          onClick={(e) => {
            e.preventDefault();
            onJoin(event.id);
          }}
          disabled={joinLoading}
          className="w-full py-2 px-4 rounded-lg bg-emerald-600/80 hover:bg-emerald-500/80 text-white text-sm font-cinzel font-bold tracking-wide transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {joinLoading ? "..." : "Участвовать"}
        </button>
      )}

      {isJoined && event.status === "active" && (
        <Link
          href={`/events/${event.id}`}
          className="block w-full py-2 px-4 rounded-lg bg-amber-600/30 border border-amber-500/30 text-amber-300 text-sm font-cinzel font-bold tracking-wide text-center hover:bg-amber-600/50 transition-all"
        >
          Вы участвуете
        </Link>
      )}

      {(event.status === "ended" || event.status === "finalized") && (
        <Link
          href={`/events/${event.id}`}
          className="block w-full py-2 px-4 rounded-lg bg-purple-600/20 border border-purple-500/30 text-purple-300 text-sm font-cinzel font-bold tracking-wide text-center hover:bg-purple-600/40 transition-all"
        >
          Смотреть результаты
        </Link>
      )}
    </motion.div>
  );
}

const EventCard = React.memo(EventCardInner);
export default EventCard;
