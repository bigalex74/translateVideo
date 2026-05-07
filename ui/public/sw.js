/**
 * Service Worker для AI Video Translator (PWA)
 *
 * СТРАТЕГИЯ v3 (Offline-first R9-И1):
 * - HTML → Network First + offline.html fallback при отсутствии сети
 * - /api/v1/projects → Stale-While-Revalidate (60s TTL) — список проектов доступен офлайн
 * - Остальные API → Network Only с JSON 503 fallback
 * - /assets/*.js, /assets/*.css → Cache First (Vite хэши — безопасно)
 * - Range-запросы (видео/аудио) → всегда напрямую, SW не перехватывает
 * - Background Sync: saveSegments при офлайн → синхронизация при восстановлении сети
 *
 * ВАЖНО: APP_VERSION обновляется при каждом деплое через make deploy
 */

// Версия кэша — ОБНОВЛЯЕТСЯ при каждом make deploy (sed-заменой)
const APP_VERSION = '1.95.3';
const CACHE_NAME = `av-static-${APP_VERSION}`;
const OFFLINE_CACHE = `av-offline-${APP_VERSION}`;
const API_CACHE = `av-api-${APP_VERSION}`;
const OFFLINE_URL = '/offline.html';
const API_CACHE_TTL_MS = 60_000; // 60 сек stale-while-revalidate для /api/v1/projects
const SYNC_TAG = 'sync-save-segments';

// НЕ кэшируем index.html — всегда с сети (Network First для HTML)
// Кэшируем ТОЛЬКО хэшированные ассеты (они неизменны по хэшу)

// Установка SW — precache offline.html
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(OFFLINE_CACHE)
      .then((cache) => cache.add(OFFLINE_URL))
      .then(() => self.skipWaiting())
  );
});

// Активация — УДАЛЯЕМ все старые кэши + сообщаем клиентам об обновлении
self.addEventListener('activate', (event) => {
  const KEEP = [CACHE_NAME, OFFLINE_CACHE, API_CACHE];
  event.waitUntil(
    caches.keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => !KEEP.includes(k))
            .map((k) => {
              console.info('[SW] Deleting old cache:', k);
              return caches.delete(k);
            })
        )
      )
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: 'window', includeUncontrolled: true }))
      .then((clients) => {
        console.info(`[SW] Activated v${APP_VERSION}, notifying ${clients.length} client(s) to reload`);
        clients.forEach((client) => {
          client.postMessage({ type: 'SW_UPDATED', version: APP_VERSION });
        });
      })
  );
});

// Fetch стратегии
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 0. Range-запросы (видео/аудио стриминг) — НЕ перехватывать совсем
  // SW не может корректно обработать Range requests — браузер делает это сам
  if (request.headers.get('Range')) {
    return; // не вызываем event.respondWith → браузер идёт напрямую на сервер
  }

  // 1. Видео-файлы /api/v1/video/ и /runs/ — всегда напрямую, без SW
  // Видео стримится через Range requests и несовместимо с SW-кэшированием
  if (
    url.pathname.startsWith('/api/v1/video/') ||
    url.pathname.startsWith('/runs/') ||
    url.pathname.match(/\.(mp4|mp3|wav|webm|ogg|m4a|mkv)(\?|$)/)
  ) {
    return; // без event.respondWith → браузер сам
  }

  // 2a. /api/v1/projects (список) — Stale-While-Revalidate (60s TTL)
  // Пользователь офлайн видит закэшированный список проектов
  if (url.pathname === '/api/v1/projects' && request.method === 'GET') {
    event.respondWith(
      caches.open(API_CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        const fetchPromise = fetch(request).then((res) => {
          if (res.ok) {
            const cloned = res.clone();
            // Добавляем заголовок времени кэширования
            cloned.headers && cache.put(request, res.clone());
            cache.put(request, res.clone());
          }
          return res;
        }).catch(() => null);

        if (cached) {
          // Есть кэш — возвращаем сразу, обновляем в фоне
          const age = Date.now() - Number(cached.headers.get('sw-cached-at') || 0);
          if (age < API_CACHE_TTL_MS) return cached; // свежий кэш
          fetchPromise; // запускаем обновление в фоне
          return cached;
        }
        // Нет кэша — ждём сеть или возвращаем пустой список
        return fetchPromise || new Response(
          JSON.stringify([]),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      })
    );
    return;
  }

  // 2b. Остальные API запросы — Network Only с JSON 503 fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(
          JSON.stringify({ error: 'Нет подключения к серверу', offline: true }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        )
      )
    );
    return;
  }

  // 2c. HTML (навигация) — Network First + offline.html fallback
  // ВАЖНО: index.html НЕ кэшируется, чтобы деплой всегда давал новый бандл
  if (request.mode === 'navigate' || request.headers.get('Accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request).catch(() =>
        caches.open(OFFLINE_CACHE).then((cache) => cache.match(OFFLINE_URL))
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

// Background Sync — повторная отправка saveSegments при восстановлении сети
self.addEventListener('sync', (event) => {
  if (event.tag === SYNC_TAG) {
    event.waitUntil(
      // Читаем очередь из IndexedDB (заполняется в useOnlineStatus при офлайн-сохранении)
      self.clients.matchAll({ type: 'window' }).then((clients) => {
        clients.forEach((client) =>
          client.postMessage({ type: 'SW_SYNC_SEGMENTS' })
        );
      })
    );
  }
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
