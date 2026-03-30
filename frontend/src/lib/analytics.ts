/**
 * First-party analytics helper.
 *
 * Events are fire-and-forget. They will never throw or block the caller.
 *
 * Env knobs:
 *   NEXT_PUBLIC_ANALYTICS_DISABLED=true  — disable all tracking (e.g. for e2e tests)
 *   NEXT_PUBLIC_API_URL                  — controls which backend receives events
 *                                          (same base URL as the rest of the API)
 */

type AnalyticsPayload = Record<string, unknown>;

interface AnalyticsEvent {
  event_name: string;
  path: string;
  timestamp: string;
  properties: AnalyticsPayload;
}

function isDisabled(): boolean {
  return process.env.NEXT_PUBLIC_ANALYTICS_DISABLED === "true";
}

function getApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (typeof window === "undefined") {
    return configured || "http://127.0.0.1:8001/api/v1";
  }
  if (!configured) {
    const { protocol, hostname } = window.location;
    const resolvedHost = hostname === "localhost" || hostname === "127.0.0.1" ? "127.0.0.1" : hostname;
    return `${protocol}//${resolvedHost}:8001/api/v1`;
  }
  return configured.replace(/\/+$/, "");
}

function buildEvent(eventName: string, payload: AnalyticsPayload): AnalyticsEvent | null {
  if (typeof window === "undefined") {
    return null;
  }
  return {
    event_name: eventName,
    path: window.location.pathname,
    timestamp: new Date().toISOString(),
    properties: payload,
  };
}

function sendToBackend(analyticsEvent: AnalyticsEvent): void {
  const endpoint = `${getApiBase()}/analytics/events`;
  const body = JSON.stringify({ events: [analyticsEvent] });
  try {
    if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
      const blob = new Blob([body], { type: "application/json" });
      // sendBeacon doesn't support custom headers; fall through to fetch for auth
      if (!navigator.sendBeacon(endpoint, blob)) {
        throw new Error("sendBeacon returned false");
      }
      return;
    }
    void fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    });
  } catch {
    // Fall back to fetch if sendBeacon failed
    void fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {
      // Analytics must never break product flow.
    });
  }
}

export function trackAnalyticsEvent(event: string, payload: AnalyticsPayload = {}): void {
  if (isDisabled()) {
    return;
  }

  const analyticsEvent = buildEvent(event, payload);
  if (!analyticsEvent) {
    return;
  }

  // Emit DOM event so other listeners (e.g. tag managers) can react
  window.dispatchEvent(new CustomEvent("questionwork:analytics", { detail: analyticsEvent }));

  sendToBackend(analyticsEvent);
}