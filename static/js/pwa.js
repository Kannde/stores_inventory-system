// PWA client-side logic — offline detection, IndexedDB queue, sync

// ── Service Worker Registration ───────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then(reg => {
        navigator.serviceWorker.addEventListener('message', handleSWMessage);
      })
      .catch(err => console.warn('SW registration failed:', err));
  });
}

// ── Offline / Online Indicator ────────────────────────────
function updateOnlineStatus() {
  const bar = document.getElementById('offlineBar');
  if (!bar) return;
  if (!navigator.onLine) {
    bar.style.display = 'flex';
  } else {
    bar.style.display = 'none';
    triggerBackgroundSync();
  }
}

function triggerBackgroundSync() {
  if (!('serviceWorker' in navigator) || !('SyncManager' in window)) return;
  navigator.serviceWorker.ready.then(reg => {
    reg.sync.register('sync-pending-sales').catch(() => {});
    reg.sync.register('sync-pending-preorders').catch(() => {});
  });
}

window.addEventListener('online', updateOnlineStatus);
window.addEventListener('offline', updateOnlineStatus);
document.addEventListener('DOMContentLoaded', updateOnlineStatus);

// ── SW Message Handler ────────────────────────────────────
function handleSWMessage(event) {
  const { type, receiptNumber } = event.data || {};
  if (type === 'SALE_SYNCED') {
    showPwaToast(`Sale synced: ${receiptNumber || ''}`, 'success');
    updatePendingBadge();
  }
  if (type === 'PREORDER_SYNCED') {
    showPwaToast('Pre-order synced to server', 'success');
    updatePendingBadge();
  }
}

// ── IndexedDB ─────────────────────────────────────────────
function openPWADB() {
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

function addToStore(db, storeName, record) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const req = tx.objectStore(storeName).add(record);
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = e => reject(e.target.error);
  });
}

function countStore(db, storeName) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).count();
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = e => reject(e.target.error);
  });
}

// ── Queue a sale when offline ─────────────────────────────
window.queueSale = async function(url, data, csrfToken) {
  const db = await openPWADB();
  const id = await addToStore(db, 'pending_sales', {
    url, data, csrfToken, queuedAt: Date.now()
  });
  if ('serviceWorker' in navigator && 'SyncManager' in window) {
    const reg = await navigator.serviceWorker.ready;
    reg.sync.register('sync-pending-sales').catch(() => {});
  }
  updatePendingBadge();
  return id;
};

// ── Queue a preorder when offline ─────────────────────────
window.queuePreorder = async function(url, formData, csrfToken) {
  const db = await openPWADB();
  const id = await addToStore(db, 'pending_preorders', {
    url, data: formData, csrfToken, queuedAt: Date.now()
  });
  if ('serviceWorker' in navigator && 'SyncManager' in window) {
    const reg = await navigator.serviceWorker.ready;
    reg.sync.register('sync-pending-preorders').catch(() => {});
  }
  updatePendingBadge();
  return id;
};

// ── Pending badge ─────────────────────────────────────────
async function updatePendingBadge() {
  const badge = document.getElementById('pendingSyncBadge');
  if (!badge) return;
  try {
    const db = await openPWADB();
    const sales = await countStore(db, 'pending_sales');
    const orders = await countStore(db, 'pending_preorders');
    const total = sales + orders;
    badge.textContent = total;
    badge.style.display = total > 0 ? 'inline-flex' : 'none';
  } catch {}
}

document.addEventListener('DOMContentLoaded', updatePendingBadge);

// ── Toast helper ──────────────────────────────────────────
window.showPwaToast = function(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = 'toast';
  t.style.cssText = `background:${type === 'success' ? 'var(--accent)' : type === 'error' ? 'var(--danger)' : 'var(--text)'};`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
};

// ── Install prompt ────────────────────────────────────────
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  deferredPrompt = e;
  const btn = document.getElementById('installAppBtn');
  if (btn) btn.style.display = 'flex';
});

window.installPWA = function() {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  deferredPrompt.userChoice.then(() => {
    deferredPrompt = null;
    const btn = document.getElementById('installAppBtn');
    if (btn) btn.style.display = 'none';
  });
};
