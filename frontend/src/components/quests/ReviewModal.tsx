"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Star, X, Send, Sparkles } from "lucide-react";
import { createReview } from "@/lib/api";
import type { Review } from "@/lib/api";

interface ReviewModalProps {
  questId: string;
  revieweeId: string;
  revieweeName: string;
  onClose: () => void;
  onSubmitted: (review: Review) => void;
}

export default function ReviewModal({
  questId,
  revieweeId,
  revieweeName,
  onClose,
  onSubmitted,
}: ReviewModalProps) {
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const displayRating = hoverRating || rating;

  const STAR_LABELS: Record<number, string> = {
    1: "Плохо",
    2: "Ниже среднего",
    3: "Нормально",
    4: "Хорошо",
    5: "Отлично!",
  };

  const handleSubmit = useCallback(async () => {
    if (rating === 0) {
      setError("Укажите рейтинг");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const review = await createReview({
        quest_id: questId,
        reviewee_id: revieweeId,
        rating,
        comment: comment.trim() || undefined,
      });
      onSubmitted(review);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ошибка при отправке отзыва");
    } finally {
      setLoading(false);
    }
  }, [questId, revieweeId, rating, comment, onSubmitted]);

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        {/* Backdrop */}
        <div
          className="absolute inset-0 bg-black/70 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Modal */}
        <motion.div
          className="relative w-full max-w-md bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden"
          initial={{ scale: 0.9, y: 20 }}
          animate={{ scale: 1, y: 0 }}
          exit={{ scale: 0.9, y: 20 }}
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-5 border-b border-gray-800">
            <h2 className="font-cinzel font-bold text-lg text-white">
              ⭐ Оставить отзыв
            </h2>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-5 space-y-5">
            {/* Reviewee */}
            <p className="text-sm text-gray-400">
              Оценка для{" "}
              <span className="text-amber-400 font-bold">{revieweeName}</span>
            </p>

            {/* Star rating */}
            <div className="space-y-2">
              <div className="flex items-center justify-center gap-1.5">
                {[1, 2, 3, 4, 5].map((star) => (
                  <motion.button
                    key={star}
                    type="button"
                    className="p-0.5 focus:outline-none"
                    onMouseEnter={() => setHoverRating(star)}
                    onMouseLeave={() => setHoverRating(0)}
                    onClick={() => setRating(star)}
                    whileTap={{ scale: 0.85 }}
                    whileHover={{ scale: 1.15 }}
                  >
                    <Star
                      className="w-10 h-10 transition-colors"
                      fill={star <= displayRating ? "#f59e0b" : "none"}
                      stroke={star <= displayRating ? "#f59e0b" : "#4b5563"}
                      strokeWidth={1.5}
                    />
                  </motion.button>
                ))}
              </div>
              {displayRating > 0 && (
                <motion.p
                  key={displayRating}
                  className="text-center text-sm font-medium"
                  style={{ color: displayRating >= 4 ? "#f59e0b" : displayRating >= 3 ? "#9ca3af" : "#ef4444" }}
                  initial={{ opacity: 0, y: -5 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  {STAR_LABELS[displayRating]}
                </motion.p>
              )}
              {displayRating === 5 && (
                <motion.p
                  className="text-center text-xs text-purple-400 flex items-center justify-center gap-1"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <Sparkles className="w-3 h-3" /> +10 XP бонус за 5 звёзд!
                </motion.p>
              )}
            </div>

            {/* Comment */}
            <div className="space-y-1.5">
              <label className="text-xs text-gray-500 uppercase tracking-wider">
                Комментарий (необязательно)
              </label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Расскажите о работе..."
                rows={3}
                maxLength={2000}
                className="w-full px-3 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:border-amber-600 focus:outline-none focus:ring-1 focus:ring-amber-600/30 resize-none"
              />
              <div className="text-right text-[10px] text-gray-600">
                {comment.length} / 2000
              </div>
            </div>

            {/* Error */}
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg px-3 py-2"
              >
                {error}
              </motion.div>
            )}
          </div>

          {/* Footer */}
          <div className="p-5 border-t border-gray-800 flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-lg border border-gray-700 text-sm text-gray-300 hover:bg-gray-800 transition-colors"
              disabled={loading}
            >
              Отмена
            </button>
            <motion.button
              onClick={handleSubmit}
              className="flex-1 px-4 py-2.5 rounded-lg text-sm font-bold transition-colors flex items-center justify-center gap-2"
              style={{
                backgroundColor: rating > 0 ? "#d97706" : "#374151",
                color: rating > 0 ? "#fff" : "#6b7280",
                cursor: rating > 0 ? "pointer" : "not-allowed",
              }}
              whileTap={rating > 0 ? { scale: 0.97 } : {}}
              disabled={loading || rating === 0}
            >
              {loading ? (
                <span className="animate-pulse">Отправка…</span>
              ) : (
                <>
                  <Send className="w-4 h-4" /> Отправить
                </>
              )}
            </motion.button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
