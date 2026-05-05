/**
 * Service Worker для AI Video Translator (PWA)
 *
 * СТРАТЕГИЯ v2 (фикс бага с кэшированием):
 * - HTML → Network First (всегда свежий, обновляется при деплое)
 * - API запросы → Network Only
 * - Статические ассеты с хэшем (/assets/*.js) → Cache First (безопасно, т.к. хэш меняется)
 * - Прочее → Network First
 *
 * ВАЖНО: APP_VERSION обновляется при каждом деплое через make deploy
 */

// Версия кэша — ОБНОВЛЯЕТСЯ при каждом make deploy (sed-заменой)
const APP_VERSION = '1.78.0';
const CACHE_NAME = `av-static-${APP_VERSION}`;

// НЕ кэшируем index.html — всегда с сети (Network First для HTML)
// Кэшируем ТОЛЬКО хэшированные ассеты (они неизменны по хэшу)

// Установка SW — минимальный precache
self.addEventListener('install', (event) => {
  // Немедленно активируем новый SW, не ждём закрытия вкладок
  event.waitUntil(self.skipWaiting());
});

// Активация — УДАЛЯЕМ все старые кэши
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME)
          .map((k) => {
            console.info('[SW] Deleting old cache:', k);
            return caches.delete(k);
          })
      )
    ).then(() => self.clients.claim())
  );
});

// Fetch стратегии
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 1. API запросы — ВСЕГДА сеть (свежие данные)
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

  // 2. HTML (навигация) — Network First, без кэша
  // ВАЖНО: index.html НЕ кэшируется, чтобы деплой всегда давал новый бандл
  if (request.mode === 'navigate' || request.headers.get('Accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response('<h1>Нет соединения</h1><p>Проверьте подключение и перезагрузите страницу.</p>',
          { headers: { 'Content-Type': 'text/html' } })
      )
    );
    return;
  }

  // 3. Хэшированные ассеты /assets/*.js, /assets/*.css — Cache First (безопасно)
  // Vite генерирует уникальные имена файлов с хэшем при каждой сборке
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) =>
        cache.match(request).then((cached) => {
          if (cached) return cached;
          return fetch(request).then((res) => {
            if (res.ok) cache.put(request, res.clone());
            return res;
          });
        })
      )
    );
    return;
  }

  // 4. Всё остальное (favicon, manifest, icons) — Network First
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});

// Push notifications
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
