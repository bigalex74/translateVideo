/**
 * R8-И1: useProjectStatus — умный хук статуса проекта.
 *
 * Стратегия:
 *  - Если проект running → подключается к WebSocket /{project_id}/ws
 *  - Если WS недоступен или проект не running → fallback на адаптивный HTTP поллинг
 *  - При завершении (completed/failed) → закрывает WS и останавливает поллинг
 *
 * Глеб Г7: замена дёргающего setInterval на push-обновления
 */

import { useEffect, useRef, useCallback } from 'react';
import { getProjectStatus } from '../api/client';
import type { VideoProject } from '../types/schemas';

const WS_BASE = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1/projects`;

interface UseProjectStatusOptions {
  projectId: string;
  isRunning: boolean;
  cancelling: boolean;
  onUpdate: (data: VideoProject) => void;
  onError?: (e: unknown) => void;
}

/**
 * Хук управления статусом проекта через WebSocket + HTTP fallback.
 * Используется в Workspace вместо inline useEffect с setTimeout.
 */
export function useProjectStatus({
  projectId,
  isRunning,
  cancelling,
  onUpdate,
  onError,
}: UseProjectStatusOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollStartRef = useRef<number>(Date.now());
  const wsFailedRef = useRef<boolean>(false);

  // ── Адаптивный интервал поллинга (fallback) ──────────────────────────────
  const getInterval = useCallback(() => {
    if (cancelling) return 500;
    const elapsed = (Date.now() - pollStartRef.current) / 60_000; // мин
    if (elapsed > 5) return 5000;
    if (elapsed > 2) return 3000;
    return 2000;
  }, [cancelling]);

  // ── HTTP поллинг ──────────────────────────────────────────────────────────
  const startPolling = useCallback(() => {
    const tick = async () => {
      try {
        const data = await getProjectStatus(projectId);
        onUpdate(data);
        if (data.status === 'running') {
          pollTimerRef.current = setTimeout(tick, getInterval());
        }
      } catch (e) {
        onError?.(e);
        pollTimerRef.current = setTimeout(tick, getInterval());
      }
    };
    pollTimerRef.current = setTimeout(tick, getInterval());
  }, [projectId, getInterval, onUpdate, onError]);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  // ── WebSocket подключение ─────────────────────────────────────────────────
  const startWS = useCallback(() => {
    // Не создавать второй WS если уже есть открытый
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return;

    const ws = new WebSocket(`${WS_BASE}/${encodeURIComponent(projectId)}/ws`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as {
          status: string;
          progress_percent?: number | null;
          eta_seconds?: number | null;
          error?: string;
        };
        if (payload.error) { ws.close(); return; }
        // WS шлёт только частичные данные — мержим через getProjectStatus
        // при финальном статусе, чтобы получить сегменты/артефакты
        if (payload.status !== 'running') {
          void getProjectStatus(projectId).then(onUpdate).catch(onError);
          ws.close();
        } else {
          // Оптимистичное обновление прогресса без полного запроса
          onUpdate({
            project_id: projectId,
            status: payload.status as VideoProject['status'],
            progress_percent: payload.progress_percent ?? undefined,
            eta_seconds: payload.eta_seconds ?? undefined,
          } as VideoProject);
        }
      } catch {/* ignore malformed JSON */}
    };

    ws.onerror = () => {
      wsFailedRef.current = true;
      ws.close();
    };

    ws.onclose = () => {
      wsRef.current = null;
      // WS закрылся, но проект ещё running → fallback на поллинг
      if (wsFailedRef.current) {
        startPolling();
      }
    };
  }, [projectId, onUpdate, onError, startPolling]);

  const stopWS = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onclose = null; // не триггерить fallback при намеренном закрытии
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  // ── Основной эффект ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!isRunning) {
      stopWS();
      stopPolling();
      return;
    }

    pollStartRef.current = Date.now();
    wsFailedRef.current = false;

    // Пробуем WS сначала
    try {
      startWS();
    } catch {
      // WS не поддерживается (старый браузер) → сразу поллинг
      wsFailedRef.current = true;
      startPolling();
    }

    return () => {
      stopWS();
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRunning, projectId, cancelling]);

  return { stopWS, stopPolling };
}
