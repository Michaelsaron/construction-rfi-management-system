// Construction RFI service worker
// - Page navigations: network-first (so new versions always load), cached shell as offline fallback.
// - Built static assets / icons / fonts: stale-while-revalidate.
// - API data is NEVER cached here (offline writes are handled by the IndexedDB queue in the app).
const VERSION = 'v5';
const STATIC = `rfi-static-${VERSION}`;
const RUNTIME = `rfi-runtime-${VERSION}`;
const SHELL = ['/', '/manifest.json', '/icon-192.png', '/icon-512.png', '/icon-maskable-512.png', '/apple-touch-icon.png'];
const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(STATIC).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== STATIC && k !== RUNTIME).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function staleWhileRevalidate(req) {
  return caches.open(RUNTIME).then(cache =>
    cache.match(req).then(cached => {
      const net = fetch(req).then(resp => {
        if (resp && (resp.ok || resp.type === 'opaque')) cache.put(req, resp.clone());
        return resp;
      }).catch(() => cached);
      return cached || net;
    })
  );
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Google Fonts (cross-origin) — cache so the UI keeps its fonts offline.
  if (FONT_HOSTS.includes(url.hostname)) { e.respondWith(staleWhileRevalidate(req)); return; }

  // Anything else cross-origin (e.g. the API on another port/host) is left to the network.
  if (url.origin !== self.location.origin) return;

  // Same-origin API (production: /api/...) and Vite dev-server internals are never cached.
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/@') ||
      url.pathname.startsWith('/src/') || url.pathname.startsWith('/node_modules/')) return;

  // App navigations: network first, fall back to the cached shell when offline.
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req).then(resp => {
        if (resp.ok) { const copy = resp.clone(); caches.open(STATIC).then(c => c.put('/', copy)); }
        return resp;
      }).catch(() => caches.match('/').then(r => r || Response.error()))
    );
    return;
  }

  // Static files (hashed build assets, icons, manifest).
  e.respondWith(staleWhileRevalidate(req));
});
