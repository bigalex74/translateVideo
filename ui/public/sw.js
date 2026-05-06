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
const APP_VERSION = '1.86.0';
const CACHE_NAME = `av-static-${APP_VERSION}`;

// НЕ кэшируем index.html — всегда с сети (Network First для HTML)
// Кэшируем ТОЛЬКО хэшированные ассеты (они неизменны по хэшу)

// Установка SW — минимальный precache
self.addEventListener('install', (event) => {
  // Немедленно активируем новый SW, не ждём закрытия вкладок
  event.waitUntil(self.skipWaiting());
});

// Активация — УДАЛЯЕМ все старые кэши + сообщаем клиентам об обновлении
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== CACHE_NAME)
            .map((k) => {
              console.info('[SW] Deleting old cache:', k);
              return caches.delete(k);
            })
        )
      )
      .then(() => self.clients.claim())
      .then(() => {
        // Сообщаем всем открытым вкладкам: новая версия активирована → перезагрузить
        return self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      })
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

  // 2. Остальные API запросы — Network Only (свежие данные, но с fallback)
  if (url.pathname.startsWith('/api/')) {
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
