/**
 * useVisibilityRefresh — хук принудительного обновления при возврате на вкладку (TVIDEO-223)
 *
 * Решает проблему устаревшего статуса: когда пользователь переключается на другую
 * вкладку и возвращается, polling мог пропустить обновления.
 *
 * При document.visibilityState === 'visible' → вызывает onVisible() немедленно.
 * Позволяет Workspace принудительно запросить актуальный статус проекта.
 */

import { useEffect } from 'react';

interface UseVisibilityRefreshOptions {
  /** Вызывается при каждом возврате на вкладку (видимость → visible) */
  onVisible: () => void;
  /** Включён ли хук (только когда проект запущен) */
  enabled?: boolean;
}

export function useVisibilityRefresh({
  onVisible,
  enabled = true,
}: UseVisibilityRefreshOptions): void {
  useEffect(() => {
    if (!enabled) return;

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        onVisible();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [onVisible, enabled]);
}


/**
 * requestCompletionNotification — запросить разрешение на Browser Notifications
 * и отправить уведомление если статус completedNot.
 *
 * Вызывается при первом запуске пайплайна (contextual permission request).
 * Если разрешение уже есть/нет — мгновенно без UI-диалога.
 *
 * @param projectId  Идентификатор проекта для отображения в уведомлении
 * @param status     Статус проекта: 'completed' | 'failed'
 */
export async function requestCompletionNotification(
  projectId: string,
  status: 'completed' | 'failed'
): Promise<void> {
  if (!('Notification' in window)) return;

  // Запрашиваем разрешение если ещё не решено
  if (Notification.permission === 'default') {
    try {
      await Notification.requestPermission();
    } catch {
      return; // Браузер заблокировал запрос разрешения
    }
  }

  if (Notification.permission !== 'granted') return;

  const title =
    status === 'completed'
      ? `✅ Перевод завершён`
      : `❌ Ошибка перевода`;

  const body =
    status === 'completed'
      ? `Проект ${projectId} готов к скачиванию`
      : `Проект ${projectId} завершился с ошибкой`;

  // Не показываем если вкладка активна
  if (document.visibilityState === 'visible') return;

  try {
    const n = new Notification(title, {
      body,
      icon: '/favicon.ico',
      tag: `tv-project-${projectId}`, // заменяет предыдущее уведомление для того же проекта
    });
    // Клик по уведомлению фокусирует вкладку
    n.onclick = () => {
      window.focus();
      n.close();
    };
  } catch {
    // Safari и некоторые браузеры не поддерживают Notification constructor в iframe
  }
}
