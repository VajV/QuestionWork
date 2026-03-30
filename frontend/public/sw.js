/**
 * QuestionWork Service Worker
 *
 * Strategy:
 *  - Public assets (/icons/, /favicon.svg): cache-first
 *  - Next.js runtime assets (/_next/): network-only
 *  - API calls (/api/): network-first, no caching (auth-sensitive)
 *  - Navigation (HTML pages): network-first with offline fallback to /offline.html
 *    (if the network is unavailable and no cache entry exists)
 *
 * Install: precaches the offline fallback page.
 */

// Bump SW_VERSION on each deploy to invalidate old caches.
const SW_VERSION = '2';
const CACHE_NAME = `qwork-v${SW_VERSION}`;
const STATIC_CACHE = `qwork-static-v${SW_VERSION}`;

/** Resources to precache on install */
const PRECACHE_URLS = [
  '/offline.html',
];

// ── Install ─────────────────────────────────────────────────────────────────

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // Best-effort precache — individual failures don't abort install
      return Promise.allSettled(
        PRECACHE_URLS.map((url) => cache.add(url).catch(() => null))
      );
    })
  );
  self.skipWaiting();
});

// ── Activate ─────────────────────────────────────────────────────────────────

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // Delete caches from older SW versions
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME && key !== STATIC_CACHE)
          .map((key) => caches.delete(key))
      );
      await self.clients.claim();
    })()
  );
});

// ── Fetch ─────────────────────────────────────────────────────────────────────

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') return;

  // Skip cross-origin requests
  if (url.origin !== self.location.origin) return;

  // API requests → network-first, never cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(request));
    return;
  }

  // Next.js runtime assets should never be cached by this SW.
  // In local/dev they change constantly and stale chunks cause runtime crashes.
  if (url.pathname.startsWith('/_next/')) {
    event.respondWith(fetch(request));
    return;
  }

  // Public static assets → cache-first
  if (
    url.pathname.startsWith('/icons/') ||
    url.pathname === '/favicon.svg' ||
    url.pathname === '/manifest.json'
  ) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // HTML navigation → network-only (never cache authenticated pages).
  // Offline: fall back to /offline.html from the precache.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(async () => {
        const offline = await caches.match('/offline.html');
        return offline || new Response('Offline', { status: 503 });
      })
    );
    return;
  }

  // Everything else: network-only
  event.respondWith(fetch(request));
});

// ── Strategies ───────────────────────────────────────────────────────────────

async function cacheFirst(request, cacheName = CACHE_NAME) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Offline', { status: 503 });
  }
}
