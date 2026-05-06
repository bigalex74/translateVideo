import { useEffect, useState } from 'react';
import { useOnlineStatus } from '../hooks/useOnlineStatus';

/**
 * OfflineBanner — баннер-уведомление об офлайн-режиме (R9-И1)
 *
 * - Показывается как sticky top при потере соединения
 * - Исчезает с анимацией при восстановлении (через 3 сек показывает «Синхронизировано»)
 */
export function OfflineBanner() {
  const { isOnline, wasOffline } = useOnlineStatus();
  const [showRestored, setShowRestored] = useState(false);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    if (isOnline && wasOffline) {
      setShowRestored(true);
      const t1 = setTimeout(() => setHidden(true), 3000);
      return () => clearTimeout(t1);
    }
    if (!isOnline) {
      setHidden(false);
      setShowRestored(false);
    }
  }, [isOnline, wasOffline]);

  if (!wasOffline && isOnline) return null;
  if (hidden) return null;

  if (showRestored) {
    return (
      <div
        className="offline-banner offline-banner--restored"
        role="status"
        aria-live="polite"
      >
        <span className="offline-banner__icon">✅</span>
        <span>Соединение восстановлено — данные синхронизированы</span>
      </div>
    );
  }

  if (!isOnline) {
    return (
      <div
        className="offline-banner offline-banner--offline"
        role="alert"
        aria-live="assertive"
      >
        <span className="offline-banner__icon">⚡</span>
        <span>Офлайн — данные могут быть устаревшими. Изменения сохранятся локально.</span>
        <a
          href="/offline.html"
          className="offline-banner__link"
          onClick={(e) => e.preventDefault()}
        >
          Подробнее
        </a>
      </div>
    );
  }

  return null;
}
