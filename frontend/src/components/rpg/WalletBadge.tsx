/**
 * WalletBadge — compact balance indicator for the Header.
 *
 * Shows wallet icon + balance in user's preferred currency.
 * Clicking cycles through RUB → USD → EUR.
 * Only rendered for authenticated users.
 */

"use client";

import { useEffect, useState, useCallback } from "react";
import { Wallet } from "lucide-react";
import { getWalletBalance } from "@/lib/api";
import {
  type CurrencyCode,
  CURRENCY_LIST,
  CURRENCIES,
  getPreferredCurrency,
  setPreferredCurrency,
  convertCurrency,
  formatBalanceCompact,
} from "@/lib/currency";

interface WalletBadgeProps {
  /** If false, the component renders nothing. */
  enabled?: boolean;
}

export default function WalletBadge({ enabled = true }: WalletBadgeProps) {
  const [balanceRUB, setBalanceRUB] = useState<number | null>(null);
  const [currency, setCurrency] = useState<CurrencyCode>("RUB");
  const [loading, setLoading] = useState(true);

  // Read preferred currency from localStorage on mount
  useEffect(() => {
    setCurrency(getPreferredCurrency());
  }, []);

  // Fetch balance
  const fetchBalance = useCallback(async () => {
    try {
      const data = await getWalletBalance();
      // Sum all currency balances converted to RUB (server stores in RUB primarily)
      const rubEntry = data.balances.find((b) => b.currency === "RUB");
      setBalanceRUB(rubEntry?.balance ?? 0);
    } catch {
      // Silently fail — badge just won't show a number
      setBalanceRUB(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (enabled) {
      fetchBalance();
      // Refresh every 60 seconds
      const interval = setInterval(fetchBalance, 60_000);
      return () => clearInterval(interval);
    }
  }, [enabled, fetchBalance]);

  if (!enabled || balanceRUB === null) return null;

  const displayAmount = convertCurrency(balanceRUB, "RUB", currency);

  const cycleCurrency = () => {
    const idx = CURRENCY_LIST.indexOf(currency);
    const next = CURRENCY_LIST[(idx + 1) % CURRENCY_LIST.length];
    setCurrency(next);
    setPreferredCurrency(next);
  };

  return (
    <button
      onClick={cycleCurrency}
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-md
                 bg-amber-950/60 border border-amber-800/40
                 hover:bg-amber-900/50 hover:border-amber-700/60
                 transition-all group cursor-pointer select-none"
      title={`Баланс • Нажмите чтобы сменить валюту (${CURRENCIES[currency].label})`}
      aria-label={`Баланс: ${formatBalanceCompact(displayAmount, currency)}`}
    >
      <Wallet
        size={15}
        className="text-amber-500 group-hover:text-amber-400 transition-colors shrink-0"
      />
      {loading ? (
        <span className="text-xs font-mono text-gray-500 animate-pulse">...</span>
      ) : (
        <span className="text-xs font-mono text-amber-300 group-hover:text-amber-200 transition-colors whitespace-nowrap">
          {formatBalanceCompact(displayAmount, currency)}
        </span>
      )}
    </button>
  );
}
