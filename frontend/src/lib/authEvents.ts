/**
 * authEvents — lightweight forced-logout event bus.
 *
 * Lets api.ts notify AuthContext of an expired/invalid session without
 * creating a circular import between the two modules.
 *
 * Usage:
 *   AuthContext registers a callback on mount via registerLogoutHandler().
 *   api.ts calls triggerLogout() when a token refresh attempt fails.
 */

let _logoutHandler: (() => void) | null = null;

/**
 * Register the handler to call when a forced logout is needed.
 * Should be called once by AuthContext on mount.
 */
export function registerLogoutHandler(fn: () => void): void {
  _logoutHandler = fn;
}

/**
 * Trigger the registered logout handler.
 * Called by api.ts when refresh fails for an authenticated request.
 */
export function triggerLogout(): void {
  if (_logoutHandler) {
    _logoutHandler();
  }
}
