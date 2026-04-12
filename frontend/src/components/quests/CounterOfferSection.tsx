"use client";

import { useState } from "react";
import { sendCounterOffer, respondToCounterOffer, isApiError } from "@/lib/api";

interface CounterOfferSectionProps {
  questId: string;
  applicationId: string;
  /** Who is viewing this panel */
  viewerRole: "client" | "freelancer";
  /** Current counter-offer state from the application */
  counterOfferPrice: number | null;
  counterOfferStatus: "pending" | "accepted" | "declined" | null;
  counterOfferMessage: string | null;
  proposedPrice: number | null;
  currency?: string;
  onUpdate?: (updates: {
    counter_offer_price: number | null;
    counter_offer_status: "pending" | "accepted" | "declined" | null;
    counter_offer_message: string | null;
  }) => void;
}

export function CounterOfferSection({
  questId,
  applicationId,
  viewerRole,
  counterOfferPrice,
  counterOfferStatus,
  counterOfferMessage,
  proposedPrice,
  currency = "RUB",
  onUpdate,
}: CounterOfferSectionProps) {
  const [price, setPrice] = useState<string>("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSendCounter = async () => {
    const numPrice = parseFloat(price);
    if (!numPrice || numPrice <= 0) { setErr("Укажите корректную сумму"); return; }
    setBusy(true); setErr(null);
    try {
      const res = await sendCounterOffer(questId, applicationId, {
        counter_price: numPrice,
        message: message.trim() || undefined,
      });
      onUpdate?.({
        counter_offer_price: res.counter_offer_price,
        counter_offer_status: res.counter_offer_status,
        counter_offer_message: res.counter_offer_message,
      });
      setPrice(""); setMessage("");
    } catch (e) {
      setErr(isApiError(e) ? (e.detail ?? e.message) : "Ошибка отправки");
    } finally { setBusy(false); }
  };

  const handleRespond = async (accept: boolean) => {
    setBusy(true); setErr(null);
    try {
      const res = await respondToCounterOffer(questId, applicationId, accept);
      onUpdate?.({
        counter_offer_price: res.counter_offer_price,
        counter_offer_status: res.counter_offer_status,
        counter_offer_message: res.counter_offer_message,
      });
    } catch (e) {
      setErr(isApiError(e) ? (e.detail ?? e.message) : "Ошибка ответа");
    } finally { setBusy(false); }
  };

  // Client view: send counter OR display outcome
  if (viewerRole === "client") {
    if (counterOfferStatus === "pending") {
      return (
        <div className="rounded-lg border border-indigo-500/30 bg-indigo-950/30 p-3 text-sm space-y-1">
          <p className="text-indigo-300 font-medium">Контр-оффер отправлен</p>
          <p className="text-white/60">
            Сумма: <span className="text-white tabular-nums">{counterOfferPrice?.toLocaleString()} {currency}</span>
          </p>
          {counterOfferMessage && (
            <p className="text-white/50 italic">«{counterOfferMessage}»</p>
          )}
          <p className="text-white/40 text-xs">Ожидаем ответа фрилансера…</p>
        </div>
      );
    }
    if (counterOfferStatus === "accepted") {
      return (
        <div className="rounded-lg border border-green-500/30 bg-green-950/30 p-3 text-sm">
          <p className="text-green-400 font-medium">✓ Контр-оффер принят</p>
          <p className="text-white/60">
            Согласованная цена:{" "}
            <span className="text-white tabular-nums">{counterOfferPrice?.toLocaleString()} {currency}</span>
          </p>
        </div>
      );
    }
    if (counterOfferStatus === "declined") {
      return (
        <div className="rounded-lg border border-red-500/20 bg-red-950/20 p-3 text-sm">
          <p className="text-red-400 font-medium">✗ Контр-оффер отклонён</p>
          <p className="text-white/40 text-xs">Фрилансер предложил другую цену.</p>
        </div>
      );
    }

    // No counter-offer yet — show send form
    return (
      <div className="rounded-lg border border-white/10 bg-white/5 p-3 space-y-2">
        <p className="text-sm text-white/70 font-medium">Предложить другую цену</p>
        {proposedPrice != null && (
          <p className="text-xs text-white/40">
            Предложение фрилансера: <span className="tabular-nums">{proposedPrice.toLocaleString()} {currency}</span>
          </p>
        )}
        <input
          type="number"
          min={0}
          placeholder={`Ваша цена (${currency})`}
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          className="w-full rounded bg-white/10 border border-white/10 px-3 py-1.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-indigo-500"
        />
        <textarea
          rows={2}
          placeholder="Комментарий (опционально)"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className="w-full rounded bg-white/10 border border-white/10 px-3 py-1.5 text-sm text-white placeholder-white/30 focus:outline-none focus:border-indigo-500 resize-none"
        />
        {err && <p className="text-red-400 text-xs">{err}</p>}
        <button
          onClick={handleSendCounter}
          disabled={busy}
          className="w-full py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
        >
          {busy ? "Отправка…" : "Предложить цену"}
        </button>
      </div>
    );
  }

  // Freelancer view: see pending counter-offer + accept/decline
  if (viewerRole === "freelancer") {
    if (counterOfferStatus === "pending" && counterOfferPrice != null) {
      return (
        <div className="rounded-lg border border-yellow-500/30 bg-yellow-950/20 p-3 space-y-2">
          <p className="text-yellow-300 font-medium text-sm">💬 Клиент предлагает другую цену</p>
          <p className="text-white/80 text-sm tabular-nums">
            {counterOfferPrice.toLocaleString()} {currency}
          </p>
          {counterOfferMessage && (
            <p className="text-white/50 text-xs italic">«{counterOfferMessage}»</p>
          )}
          {err && <p className="text-red-400 text-xs">{err}</p>}
          <div className="flex gap-2">
            <button
              onClick={() => handleRespond(true)}
              disabled={busy}
              className="flex-1 py-1.5 rounded bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white text-sm font-medium transition-colors"
            >
              Принять
            </button>
            <button
              onClick={() => handleRespond(false)}
              disabled={busy}
              className="flex-1 py-1.5 rounded bg-red-900/60 hover:bg-red-800/60 disabled:opacity-50 text-red-300 text-sm font-medium transition-colors"
            >
              Отклонить
            </button>
          </div>
        </div>
      );
    }
    if (counterOfferStatus === "accepted") {
      return (
        <div className="rounded-lg border border-green-500/30 bg-green-950/30 p-3 text-sm">
          <p className="text-green-400">✓ Цена согласована: {counterOfferPrice?.toLocaleString()} {currency}</p>
        </div>
      );
    }
    if (counterOfferStatus === "declined") {
      return (
        <div className="rounded-lg border border-red-500/20 bg-red-950/20 p-3 text-sm">
          <p className="text-red-400">Контр-оффер отклонён</p>
        </div>
      );
    }
  }

  return null;
}
