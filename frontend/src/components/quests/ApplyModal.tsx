/**
 * ApplyModal - Модальное окно для отклика на квест
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { QuestApplicationCreate, getApiErrorMessage } from "@/lib/api";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";

interface ApplyModalProps {
  questTitle: string;
  onSubmit: (data: QuestApplicationCreate) => Promise<void>;
  onClose: () => void;
}

export default function ApplyModal({
  questTitle,
  onSubmit,
  onClose,
}: ApplyModalProps) {
  const [coverLetter, setCoverLetter] = useState("");
  const [proposedPrice, setProposedPrice] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  /**
   * Валидация сопроводительного письма
   */
  const validateCoverLetter = (text: string): string | null => {
    if (text.trim().length < 10) {
      return "Сопроводительное письмо должно содержать минимум 10 символов";
    }
    if (text.trim().length > 1000) {
      return "Сопроводительное письмо не должно превышать 1000 символов";
    }
    return null;
  };

  /**
   * Обработка отправки
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);


    // Валидация
    const validationError = validateCoverLetter(coverLetter);
    if (validationError) {
      setError(validationError);
      setLoading(false);
      return;
    }


    try {
      await onSubmit({
        cover_letter: coverLetter.trim() || undefined,
        proposed_price: proposedPrice ? Number(proposedPrice) : undefined,
      });
      // Успех — модальное окно закроет родитель
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Ошибка отправки"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="w-full max-w-3xl" onClick={(event) => event.stopPropagation()}>
        <Card className="p-6 border-purple-500/50 shadow-xl shadow-purple-500/20">
          <div role="dialog" aria-modal="true" aria-labelledby="apply-modal-title" className="grid gap-6 lg:grid-cols-[1.2fr,0.8fr]">
          <div>
          {/* Заголовок */}
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
            <h2 id="apply-modal-title" className="text-2xl font-bold mb-2">📩 Отклик на квест</h2>
            <p className="text-gray-400 text-sm line-clamp-1">
              {questTitle}
            </p>
            </div>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              aria-label="Закрыть окно отклика"
              className="rounded-lg border border-gray-700 px-3 py-2 text-sm text-gray-400 transition-colors hover:border-gray-500 hover:text-white"
            >
              ✕
            </button>
          </div>

          {/* Сообщение об ошибке */}
          {error && (
            <div className="mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg text-red-200 text-sm">
              ⚠️ {error}
              <button 
                onClick={() => setError(null)}
                className="ml-2 text-red-300 hover:text-red-100"
              >
                ✕
              </button>
            </div>
          )}

          {/* Форма */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Сопроводительное письмо */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Сопроводительное письмо <span className="text-red-400">*</span>
              </label>
              <textarea
                value={coverLetter}
                onChange={(e) => { setCoverLetter(e.target.value); setError(null); }}
                placeholder="Расскажите, почему вы подходите для этого квеста..."
                rows={5}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500 resize-none"
                maxLength={1000}
                disabled={loading}
                required
              />
              <div className="flex justify-between items-center mt-1">
                <span className="text-xs text-gray-500">
                  Минимум 10 символов
                </span>
                <span className={`text-xs ${coverLetter.length < 10 ? 'text-red-400' : 'text-gray-500'}`}>
                  {coverLetter.length}/1000
                </span>
              </div>
            </div>

            {/* Предлагаемая цена */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Предлагаемая цена (₽) <span className="text-gray-500">опционально</span>
              </label>
              <input
                type="number"
                value={proposedPrice}
                onChange={(e) => { setProposedPrice(e.target.value); setError(null); }}
                placeholder="5000"
                min="0"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-purple-500 text-white placeholder-gray-500"
                disabled={loading}
              />
              <p className="text-xs text-gray-500 mt-1">
                Оставьте пустым, если цена фиксирована
              </p>
            </div>

            {/* Кнопки */}
            <div className="flex gap-3 pt-4">
              <Button
                type="button"
                onClick={onClose}
                variant="secondary"
                className="flex-1"
                disabled={loading}
              >
                Отмена
              </Button>
              <Button
                type="submit"
                variant="primary"
                className="flex-1"
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Отправка...
                  </span>
                ) : (
                  "📩 Отправить отклик"
                )}
              </Button>
            </div>
          </form>
          </div>

          <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
            <div className="text-xs uppercase tracking-[0.25em] text-purple-300/80">Guild pitch</div>
            <h3 className="mt-3 text-lg font-cinzel font-bold text-white">Как усилить отклик</h3>
            <ul className="mt-4 space-y-3 text-sm leading-relaxed text-gray-400">
              <li>• Кратко покажите релевантный опыт и стек.</li>
              <li>• Если хотите изменить бюджет, обоснуйте цену.</li>
              <li>• Укажите сроки и формат коммуникации.</li>
            </ul>

            <div className="mt-6 rounded-xl border border-amber-500/20 bg-amber-950/10 p-4">
              <div className="text-[11px] uppercase tracking-[0.2em] text-amber-400/80">Статус отклика</div>
              <div className="mt-2 text-sm text-gray-300">
                {loading ? "Отправляем заявку в гильдию..." : "Готово к отправке"}
              </div>
              <div className="mt-3 text-xs text-gray-500">
                После отправки заказчик увидит письмо, ставку и сможет назначить вас исполнителем.
              </div>
            </div>
          </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
