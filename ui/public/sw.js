/**
 * Service Worker для AI Video Translator (PWA — backlog)
 *
 * Стратегия:
 * - Shell (HTML/CSS/JS) → Cache First (офлайн)
 * - API запросы (/api/*) → Network Only (всегда свежие данные)
 * - Статические ассеты → Stale While Revalidate
 */

const CACHE_NAME = 'ai-video-translator-v1';
const SHELL_CACHE = 'shell-v1';

// Ресурсы для precaching (app shell)
const SHELL_ASSETS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.svg',
];

// Установка SW — precache shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Активация — удаляем старые кэши
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME && k !== SHELL_CACHE)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// Fetch стратегии
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // API запросы — всегда сеть (актуальные данные)
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/runs/')) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(
          JSON.stringify({ error: 'Нет подключения к серверу' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        )
      )
    );
    return;
  }

  // HTML — Shell (app) — Cache First с fallback на сеть
  if (request.mode === 'navigate' || request.headers.get('Accept')?.includes('text/html')) {
    event.respondWith(
      caches.match('/index.html').then((cached) =>
        cached || fetch(request).then((res) => {
          const clone = res.clone();
          caches.open(SHELL_CACHE).then((c) => c.put('/index.html', clone));
          return res;
        })
      )
    );
    return;
  }

  // Статические ассеты — Stale While Revalidate
  if (url.pathname.startsWith('/assets/') || url.pathname.endsWith('.svg')) {
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) =>
        cache.match(request).then((cached) => {
          const fetchPromise = fetch(request).then((res) => {
            cache.put(request, res.clone());
            return res;
          });
          return cached || fetchPromise;
        })
      )
    );
    return;
  }

  // Всё остальное — Network First
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});

// Push notifications (если браузер поддерживает и разрешены)
self.addEventListener('push', (event) => {
  if (!event.data) return;
  const data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title || 'AI Video Translator', {
      body: data.body || 'Перевод завершён',
      icon: '/favicon.svg',
      badge: '/favicon.svg',
      tag: data.tag || 'translation',
      data: { url: data.url || '/' },
    })
  );
});

// Клик по уведомлению — открываем приложение
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow(event.notification.data?.url || '/');
    })
  );
});
