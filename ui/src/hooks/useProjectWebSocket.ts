import { useEffect, useRef, useCallback } from "react";

// WS-FE R12-И1: WebSocket хук для реального времени статуса проекта.
// R14-И1: Авто-реконнект с exponential backoff (Никита — мобильный потеря WS).

const isViteDevServer = ['5173', '5174'].includes(window.location.port);
const WS_BASE = isViteDevServer
    ? "ws://localhost:8002/api/v1"
    : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1`;

/** Максимальные задержки реконнекта (ms): 1s, 2s, 4s, 8s, 15s, 30s */
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 15000, 30000];
const MAX_RECONNECT_ATTEMPTS = 10; // после 10 попыток — прекращаем

export interface WSProjectStatus {
    status: string;
    progress_percent: number | null;
    eta_seconds: number | null;
    error?: string;
}

interface UseProjectWebSocketOptions {
    projectId: string | null | undefined;
    enabled: boolean; // только когда status === 'running'
    onUpdate: (data: WSProjectStatus) => void;
    onDone?: () => void; // вызывается когда сервер закрыл WS (перевод завершён нормально)
}

export function useProjectWebSocket({
    projectId,
    enabled,
    onUpdate,
    onDone,
}: UseProjectWebSocketOptions): void {
    const wsRef = useRef<WebSocket | null>(null);
    const onUpdateRef = useRef(onUpdate);
    const onDoneRef = useRef(onDone);
    const reconnectAttemptsRef = useRef(0);
    const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const intentionalCloseRef = useRef(false); // true когда мы сами закрываем (не ошибка)

    // Обновляем refs чтобы не пересоздавать WS при изменении колбэков
    useEffect(() => { onUpdateRef.current = onUpdate; });
    useEffect(() => { onDoneRef.current = onDone; });

    const clearReconnectTimer = useCallback(() => {
        if (reconnectTimerRef.current !== null) {
            clearTimeout(reconnectTimerRef.current);
            reconnectTimerRef.current = null;
        }
    }, []);

    const connect = useCallback(() => {
        if (!projectId || !enabled) return;

        // Закрываем предыдущее соединение
        if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
            wsRef.current.onclose = null; // предотвращаем рекурсивный реконнект
            wsRef.current.close();
        }

        // R13-И3: передаём api_key через query param
        const apiKey = localStorage.getItem('tv_api_key') || '';
        const url = apiKey
            ? `${WS_BASE}/projects/${projectId}/ws?api_key=${encodeURIComponent(apiKey)}`
            : `${WS_BASE}/projects/${projectId}/ws`;
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
            // Успешное соединение — сбрасываем счётчик реконнектов
            reconnectAttemptsRef.current = 0;
        };

        ws.onmessage = (event) => {
            try {
                const data: WSProjectStatus = JSON.parse(event.data);
                // Если сервер вернул unauthorized — не реконнектимся
                if (data.error === 'unauthorized') {
                    intentionalCloseRef.current = true;
                }
                onUpdateRef.current(data);
            } catch {
                // ignore parse errors
            }
        };

        ws.onclose = (event) => {
            wsRef.current = null;

            // Намеренное закрытие (мы сами вызвали close или проект завершён)
            if (intentionalCloseRef.current) {
                intentionalCloseRef.current = false;
                onDoneRef.current?.();
                return;
            }

            // Код 1000 = нормальное закрытие сервером (перевод завершён)
            if (event.code === 1000 || event.code === 4401) {
                onDoneRef.current?.();
                return;
            }

            // R14-И1: Аномальное закрытие (потеря сети, мобильный фон) → реконнект
            if (!enabled) return; // если хук уже disabled — не реконнектимся
            const attempt = reconnectAttemptsRef.current;
            if (attempt >= MAX_RECONNECT_ATTEMPTS) {
                console.warn(`[WS] Превышен лимит реконнектов (${MAX_RECONNECT_ATTEMPTS}), прекращаем`);
                onDoneRef.current?.();
                return;
            }
            const delay = RECONNECT_DELAYS[Math.min(attempt, RECONNECT_DELAYS.length - 1)];
            console.info(`[WS] Реконнект через ${delay}ms (попытка ${attempt + 1})`);
            reconnectAttemptsRef.current = attempt + 1;
            reconnectTimerRef.current = setTimeout(() => {
                if (enabled) connect();
            }, delay);
        };

        ws.onerror = () => {
            // onerror всегда предшествует onclose — не нужно отдельно обрабатывать
            ws.close();
        };
    }, [projectId, enabled, clearReconnectTimer]);

    // R14-И1: При возвращении вкладки на передний план — реконнектимся сразу
    useEffect(() => {
        const handleVisibilityChange = () => {
            if (document.visibilityState === 'visible' && enabled && projectId) {
                const ws = wsRef.current;
                if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
                    clearReconnectTimer(); // отменяем отложенный реконнект — делаем сразу
                    reconnectAttemptsRef.current = 0; // сбрасываем счётчик при ручном реконнекте
                    connect();
                }
            }
        };
        document.addEventListener('visibilitychange', handleVisibilityChange);
        return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
    }, [enabled, projectId, connect, clearReconnectTimer]);

    useEffect(() => {
        if (enabled && projectId) {
            intentionalCloseRef.current = false;
            reconnectAttemptsRef.current = 0;
            connect();
        } else {
            // Если не enabled — закрываем WS намеренно
            clearReconnectTimer();
            if (wsRef.current) {
                intentionalCloseRef.current = true;
                wsRef.current.onclose = null;
                wsRef.current.close();
                wsRef.current = null;
            }
        }

        return () => {
            clearReconnectTimer();
            if (wsRef.current) {
                wsRef.current.onclose = null;
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [enabled, projectId, connect, clearReconnectTimer]);
}
