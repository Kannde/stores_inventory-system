// Service Worker — Inventory Stores PWA
const CACHE_VERSION = '{{ cache_version }}';
const CACHE_NAME = 'stores-' + CACHE_VERSION;
const OFFLINE_URL = '/offline/';

const PRE_CACHE_URLS = [
  OFFLINE_URL,
  '/static/manifest.json',
];

// ── Install ───────────────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRE_CACHE_URLS).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

// ── Activate — purge old caches ───────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch ─────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;
  if (!url.protocol.startsWith('http')) return;
  // Skip admin and ping — these must always hit the real server
  if (url.pathname.startsWith('/admin/')) return;
  if (url.pathname === '/ping/') return;
  // Skip cross-origin requests
  if (url.origin !== self.location.origin) return;

  // Static & media assets — Cache First
  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // HTML navigation — Network First with offline fallback
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirstHTML(request));
    return;
  }

  // JSON / API reads — Network First, stale-if-error
  event.respondWith(networkFirst(request));
});

// ── Background Sync ───────────────────────────────────────
self.addEventListener('sync', event => {
  if (event.tag === 'sync-pending-sales') {
    event.waitUntil(syncPendingSales());
  }
  if (event.tag === 'sync-pending-preorders') {
    event.waitUntil(syncPendingPreorders());
  }
});

// ── Push (future use) ─────────────────────────────────────
self.addEventListener('push', event => {
  const data = event.data?.json() || {};
  event.waitUntil(
    self.registration.showNotification(data.title || 'Stores', {
      body: data.body || '',
      icon: '/static/icons/icon-192.png',
      badge: '/static/icons/icon-192.png',
    })
  );
});

// ─────────────────────────────────────────────────────────
// Cache strategies
// ─────────────────────────────────────────────────────────
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Asset unavailable offline', { status: 503 });
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    return cached || new Response('Offline', { status: 503 });
  }
}

async function networkFirstHTML(request) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(request, { signal: controller.signal });
    clearTimeout(timer);
    // Only cache same-origin, non-redirected responses (avoids caching login page under dashboard URL)
    if (response.ok && response.url.startsWith(self.location.origin) &&
        new URL(response.url).pathname === new URL(request.url).pathname) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    clearTimeout(timer);
    const cached = await caches.match(request);
    if (cached) return cached;
    return caches.match(OFFLINE_URL);
  }
}

// ─────────────────────────────────────────────────────────
// IndexedDB helpers
// ─────────────────────────────────────────────────────────
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('stores-pwa', 1);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('pending_sales'))
        db.createObjectStore('pending_sales', { keyPath: 'id', autoIncrement: true });
      if (!db.objectStoreNames.contains('pending_preorders'))
        db.createObjectStore('pending_preorders', { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = e => reject(e.target.error);
  });
}

function getAllFromStore(db, storeName) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).getAll();
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = e => reject(e.target.error);
  });
}

function deleteFromStore(db, storeName, id) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const req = tx.objectStore(storeName).delete(id);
    req.onsuccess = () => resolve();
    req.onerror = e => reject(e.target.error);
  });
}

function notifyClients(type, payload) {
  self.clients.matchAll({ includeUncontrolled: true }).then(clients => {
    clients.forEach(c => c.postMessage({ type, ...payload }));
  });
}

// ─────────────────────────────────────────────────────────
// Sync handlers
// ─────────────────────────────────────────────────────────
async function syncPendingSales() {
  const db = await openDB();
  const pending = await getAllFromStore(db, 'pending_sales');
  for (const sale of pending) {
    try {
      const res = await fetch(sale.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': sale.csrfToken,
        },
        body: JSON.stringify(sale.data),
        credentials: 'same-origin',
      });
      const json = await res.json();
      if (json.success) {
        await deleteFromStore(db, 'pending_sales', sale.id);
        notifyClients('SALE_SYNCED', { receiptNumber: json.receipt_number });
      }
    } catch (e) {
      // Will retry on next sync event
    }
  }
}

async function syncPendingPreorders() {
  const db = await openDB();
  const pending = await getAllFromStore(db, 'pending_preorders');
  for (const order of pending) {
    try {
      const formData = new URLSearchParams(order.data);
      const res = await fetch(order.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': order.csrfToken,
        },
        body: formData.toString(),
        credentials: 'same-origin',
        redirect: 'manual',
      });
      // Django redirects on success (302) or manual redirect
      if (res.ok || res.type === 'opaqueredirect' || res.status === 302) {
        await deleteFromStore(db, 'pending_preorders', order.id);
        notifyClients('PREORDER_SYNCED', {});
      }
    } catch (e) {
      // Will retry
    }
  }
}
