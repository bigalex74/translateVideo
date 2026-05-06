import { useState, useEffect } from 'react';

/**
 * useOnlineStatus — хук для отслеживания состояния сети (R9-И1)
 *
 * Возвращает:
 * - `isOnline`: boolean — текущий статус сети
 * - `wasOffline`: boolean — был ли пользователь офлайн в этой сессии (для badge «Синхронизировано»)
 *
 * Реагирует на события `online` / `offline` из браузера.
 */
export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(() => navigator.onLine);
  const [wasOffline, setWasOffline] = useState(false);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      // Сигнализируем SW о восстановлении сети (Background Sync)
      if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
        navigator.serviceWorker.ready
          .then((reg) => {
            if ('sync' in reg) {
              return (reg as ServiceWorkerRegistration & { sync: { register(tag: string): Promise<void> } })
                .sync.register('sync-save-segments');
            }
          })
          .catch(() => {}); // Background Sync может быть недоступен
      }
    };

    const handleOffline = () => {
      setIsOnline(false);
      setWasOffline(true);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Начальная проверка
    if (!navigator.onLine) setWasOffline(true);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return { isOnline, wasOffline };
}
