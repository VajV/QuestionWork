"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "@/lib/motion";
import { Star, MessageSquare, ChevronDown } from "lucide-react";
import { getApiErrorMessage, getUserReviews, type Review } from "@/lib/api";

interface ReviewListProps {
  userId: string;
  /** Max items per load */
  pageSize?: number;
}

function StarRow({ rating }: { rating: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <Star
          key={s}
          className="w-3.5 h-3.5"
          fill={s <= rating ? "#f59e0b" : "none"}
          stroke={s <= rating ? "#f59e0b" : "#4b5563"}
          strokeWidth={1.5}
        />
      ))}
    </div>
  );
}

function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return "только что";
  if (mins < 60) return `${mins} мин. назад`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} ч. назад`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} дн. назад`;
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" });
}

export default function ReviewList({ userId, pageSize = 10 }: ReviewListProps) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [total, setTotal] = useState(0);
  const [avgRating, setAvgRating] = useState<number | null>(null);
  const [reviewCount, setReviewCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  const load = useCallback(
    async (offset: number, append: boolean) => {
      if (append) { setLoadingMore(true); } else { setLoading(true); }
      setError(null);
      try {
        const res = await getUserReviews(userId, pageSize, offset);
        setReviews((prev) => (append ? [...prev, ...res.reviews] : res.reviews));
        setTotal(res.total);
        setAvgRating(res.avg_rating);
        setReviewCount(res.review_count);
      } catch (err: unknown) {
        setError(getApiErrorMessage(err, "Не удалось загрузить отзывы"));
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [userId, pageSize],
  );

  useEffect(() => {
    load(0, false);
  }, [load]);

  useEffect(() => {
    setMounted(true);
  }, []);

  const formatStableDate = (iso: string) =>
    new Date(iso).toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      timeZone: "UTC",
    });

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-lg bg-gray-800/40 animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/20 bg-red-950/10 px-4 py-5 text-center">
        <p className="text-sm text-red-300">{error}</p>
        <button
          type="button"
          onClick={() => load(0, false)}
          className="mt-3 text-sm text-amber-400 hover:underline"
        >
          Повторить
        </button>
      </div>
    );
  }

  if (reviews.length === 0) {
    return (
      <div className="text-center py-8">
        <MessageSquare className="mx-auto mb-2 text-gray-600" size={32} />
        <p className="text-sm text-gray-500">Отзывов пока нет</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 px-4 py-4">
          <div className="flex items-center gap-2">
            <Star className="h-4 w-4 text-amber-400" fill="#f59e0b" stroke="#f59e0b" />
            <span className="text-xs font-mono uppercase tracking-[0.24em] text-gray-500">Средняя оценка</span>
          </div>
          <div className="mt-3 flex items-end gap-3">
            <span className="font-cinzel text-3xl text-amber-300">
              {avgRating ? avgRating.toFixed(1) : "-"}
            </span>
            {avgRating ? <StarRow rating={Math.round(avgRating)} /> : <span className="text-sm text-gray-500">пока нет</span>}
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-sky-300" />
            <span className="text-xs font-mono uppercase tracking-[0.24em] text-gray-500">Подтверждений</span>
          </div>
          <div className="mt-3 font-cinzel text-3xl text-stone-100">{reviewCount}</div>
          <p className="mt-1 text-sm text-gray-400">публичных отзывов от заказчиков и союзников</p>
        </div>
      </div>

      {reviews.map((r, i) => (
        <motion.div
          key={r.id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04 }}
          className="p-4 rounded-lg bg-gray-800/40 border border-gray-700/50"
        >
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm font-bold text-amber-400 truncate">
                {r.reviewer_username ?? "Пользователь"}
              </span>
              <StarRow rating={r.rating} />
            </div>
            <span className="text-[10px] text-gray-500 shrink-0 whitespace-nowrap">
              {mounted ? timeAgo(r.created_at) : formatStableDate(r.created_at)}
            </span>
          </div>
          {r.comment && (
            <p className="text-sm text-gray-300 leading-relaxed line-clamp-3">
              {r.comment}
            </p>
          )}
        </motion.div>
      ))}

      {reviews.length < total && (
        <button
          onClick={() => load(reviews.length, true)}
          disabled={loadingMore}
          className="w-full flex items-center justify-center gap-1.5 py-2.5 text-sm text-gray-400 hover:text-amber-400 border border-gray-700/50 hover:border-amber-500/50 rounded-lg transition-colors disabled:opacity-50"
        >
          {loadingMore ? (
            <span className="animate-pulse">Загрузка…</span>
          ) : (
            <>
              <ChevronDown size={14} /> Показать ещё ({total - reviews.length})
            </>
          )}
        </button>
      )}
    </div>
  );
}
