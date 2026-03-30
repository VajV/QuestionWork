/**
 * Format a numeric money value for display.
 *
 * @param value  - the amount
 * @param suffix - optional currency suffix (e.g. "₽")
 * @param decimals - fraction digits (default 0)
 */
export function formatMoney(
  value: number,
  { suffix = "", decimals = 0 }: { suffix?: string; decimals?: number } = {},
): string {
  const formatted = value.toLocaleString("ru-RU", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return suffix ? `${formatted}${suffix}` : formatted;
}
