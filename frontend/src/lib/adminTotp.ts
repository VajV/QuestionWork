export interface AdminTotpState {
  token: string | null;
  error: string | null;
}

type AdminTotpListener = (state: AdminTotpState) => void;

let adminTotpToken: string | null = null;
let adminTotpError: string | null = null;
let adminTotpExpiryTimer: ReturnType<typeof setTimeout> | null = null;
const ADMIN_TOTP_TTL_MS = 5 * 60 * 1000; // 5 minutes

const listeners = new Set<AdminTotpListener>();

const ADMIN_TOTP_ERROR_MARKERS = [
  "x-totp-token",
  "invalid or expired totp",
  "totp token already used",
  "admin 2fa not configured",
];

function emitAdminTotpState() {
  const state = getAdminTotpState();
  listeners.forEach((listener) => listener(state));
}

export function getAdminTotpState(): AdminTotpState {
  return {
    token: adminTotpToken,
    error: adminTotpError,
  };
}

export function getAdminTotpToken(): string | null {
  return adminTotpToken;
}

export function getAdminTotpError(): string | null {
  return adminTotpError;
}

export function setAdminTotpToken(token: string) {
  adminTotpToken = token.trim();
  adminTotpError = null;
  // P2-27: auto-expire token after 5 minutes
  if (adminTotpExpiryTimer) clearTimeout(adminTotpExpiryTimer);
  adminTotpExpiryTimer = setTimeout(() => {
    clearAdminTotpToken("TOTP сессия истекла — введите код повторно");
  }, ADMIN_TOTP_TTL_MS);
  emitAdminTotpState();
}

export function clearAdminTotpToken(error: string | null = null) {
  adminTotpToken = null;
  adminTotpError = error;
  if (adminTotpExpiryTimer) {
    clearTimeout(adminTotpExpiryTimer);
    adminTotpExpiryTimer = null;
  }
  emitAdminTotpState();
}

export function clearAdminTotpError() {
  if (adminTotpError === null) {
    return;
  }

  adminTotpError = null;
  emitAdminTotpState();
}

export function isAdminTotpErrorMessage(detail: string | null | undefined): boolean {
  if (!detail) {
    return false;
  }

  const normalizedDetail = detail.toLowerCase();
  return ADMIN_TOTP_ERROR_MARKERS.some((marker) => normalizedDetail.includes(marker));
}

export function subscribeAdminTotpState(listener: AdminTotpListener): () => void {
  listeners.add(listener);
  listener(getAdminTotpState());

  return () => {
    listeners.delete(listener);
  };
}