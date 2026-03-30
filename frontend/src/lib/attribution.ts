export interface AttributionSnapshot {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_term?: string;
  utm_content?: string;
  ref?: string;
  landing_path?: string;
}

const STORAGE_KEY = "questionwork_attribution";

function normalizeValue(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed || undefined;
}

function hasWindow(): boolean {
  return typeof window !== "undefined";
}

export function getStoredAttribution(): AttributionSnapshot {
  if (!hasWindow()) {
    return {};
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as AttributionSnapshot;
    return parsed ?? {};
  } catch {
    return {};
  }
}

export function persistAttributionFromLocation(): AttributionSnapshot {
  if (!hasWindow()) {
    return {};
  }

  const params = new URLSearchParams(window.location.search);
  const existing = getStoredAttribution();
  const externalReferrer = (() => {
    if (!document.referrer) {
      return undefined;
    }
    try {
      const refUrl = new URL(document.referrer);
      if (refUrl.host === window.location.host) {
        return undefined;
      }
      return refUrl.toString();
    } catch {
      return undefined;
    }
  })();

  const merged: AttributionSnapshot = {
    utm_source: normalizeValue(params.get("utm_source")) ?? existing.utm_source,
    utm_medium: normalizeValue(params.get("utm_medium")) ?? existing.utm_medium,
    utm_campaign: normalizeValue(params.get("utm_campaign")) ?? existing.utm_campaign,
    utm_term: normalizeValue(params.get("utm_term")) ?? existing.utm_term,
    utm_content: normalizeValue(params.get("utm_content")) ?? existing.utm_content,
    ref: normalizeValue(params.get("ref")) ?? existing.ref ?? externalReferrer,
    landing_path:
      existing.landing_path ?? `${window.location.pathname}${window.location.search}`,
  };

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
  return merged;
}

export function getAttributionPayload(): AttributionSnapshot {
  return getStoredAttribution();
}