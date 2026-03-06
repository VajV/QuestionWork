/**
 * Currency utilities — conversion, formatting, localStorage persistence.
 *
 * Stores amounts internally in RUB; converts on display using static rates (MVP).
 * Later can be swapped for a real exchange-rate API.
 */

export type CurrencyCode = "RUB" | "USD" | "EUR";

interface CurrencyMeta {
  code: CurrencyCode;
  symbol: string;
  label: string;
  /** How many units of this currency = 1 RUB  */
  rateFromRUB: number;
}

/**
 * Static exchange rates (approximate as of 2026-03).
 * 1 RUB → X units of target currency.
 */
export const CURRENCIES: Record<CurrencyCode, CurrencyMeta> = {
  RUB: { code: "RUB", symbol: "₽", label: "Рубли",   rateFromRUB: 1 },
  USD: { code: "USD", symbol: "$", label: "Доллары",  rateFromRUB: 0.011 },
  EUR: { code: "EUR", symbol: "€", label: "Евро",     rateFromRUB: 0.010 },
};

export const CURRENCY_LIST: CurrencyCode[] = ["RUB", "USD", "EUR"];

const STORAGE_KEY = "qw_preferred_currency";

/** Read user's preferred currency from localStorage (defaults to RUB). */
export function getPreferredCurrency(): CurrencyCode {
  if (typeof window === "undefined") return "RUB";
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && saved in CURRENCIES) return saved as CurrencyCode;
  return "RUB";
}

/** Persist the user's currency choice. */
export function setPreferredCurrency(code: CurrencyCode): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, code);
}

/**
 * Convert an amount from one currency to another.
 * Under the hood everything goes through RUB as the base.
 */
export function convertCurrency(
  amount: number,
  from: CurrencyCode,
  to: CurrencyCode,
): number {
  if (from === to) return amount;
  // Convert to RUB first, then to target
  const inRUB = amount / CURRENCIES[from].rateFromRUB;
  return inRUB * CURRENCIES[to].rateFromRUB;
}

/**
 * Format a numeric amount with the currency symbol.
 * Examples: "1 250,00 ₽", "$13.75", "€12.50"
 */
export function formatBalance(amount: number, currency: CurrencyCode = "RUB"): string {
  const meta = CURRENCIES[currency];
  const locale = currency === "RUB" ? "ru-RU" : "en-US";
  const formatted = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);

  if (currency === "RUB") return `${formatted} ${meta.symbol}`;
  return `${meta.symbol}${formatted}`;
}

/**
 * Compact format for header badge — no decimals, shorter.
 * Examples: "1 250 ₽", "$14", "€13"
 */
export function formatBalanceCompact(amount: number, currency: CurrencyCode = "RUB"): string {
  const meta = CURRENCIES[currency];
  const locale = currency === "RUB" ? "ru-RU" : "en-US";
  const formatted = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Math.round(amount));

  if (currency === "RUB") return `${formatted} ${meta.symbol}`;
  return `${meta.symbol}${formatted}`;
}
