import useSWR, { type Key, type SWRConfiguration } from "swr";
import type { ApiError } from "@/lib/api";

/**
 * Generic SWR hook wrapping any async API function from `lib/api.ts`.
 *
 * @param key   A unique string key for SWR caching (e.g. "/badges/catalogue").
 *              Pass `null` to skip fetching (conditional fetching).
 * @param fetcher An async function from `lib/api.ts` that returns `T`.
 * @param config  Optional SWR configuration overrides.
 *
 * Usage:
 * ```ts
 * const { data, error, isLoading } = useSWRFetch(
 *   "/badges/catalogue",
 *   () => getBadgeCatalogue(),
 * );
 * ```
 */
export function useSWRFetch<T>(
  key: Key,
  fetcher: () => Promise<T>,
  config?: SWRConfiguration<T, ApiError>,
) {
  return useSWR<T, ApiError>(key, fetcher, {
    revalidateOnFocus: true,
    dedupingInterval: 5000,
    errorRetryCount: 2,
    ...config,
  });
}
