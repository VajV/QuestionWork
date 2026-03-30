/**
 * Safe money parsing utility.
 *
 * Rejects strings that `parseFloat` would silently truncate
 * (e.g. "100abc" → 100) or that have more than 2 decimal places.
 */

/**
 * Parse a user-entered money string into a number.
 *
 * Returns `null` when the value is not a valid monetary amount:
 * - Must consist of digits with an optional single decimal point
 * - At most 2 decimal places
 * - Must be finite and >= 0
 *
 * @example
 * safeParseMoney("100")      // 100
 * safeParseMoney("10.50")    // 10.5
 * safeParseMoney("100abc")   // null
 * safeParseMoney("10.005")   // null
 * safeParseMoney("")          // null
 */
export function safeParseMoney(value: string): number | null {
  const trimmed = value.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null;
  const num = Number(trimmed);
  return Number.isFinite(num) && num >= 0 ? num : null;
}
