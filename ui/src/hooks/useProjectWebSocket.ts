import { useEffect, useRef, useCallback } from "react";

// WS-FE R12-И1: WebSocket хук для реального времени статуса проекта.
// Заменяет polling setInterval(3000) в Dashboard.

const isViteDevServer = ['5173', '5174'].includes(window.location.port);
const WS_BASE = isViteDevServer
    ? "ws://localhost:8002/api/v1"
    : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1`;

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
    onDone?: () => void; // вызывается когда WS закрылся (перевод завершён)
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

    // Обновляем refs чтобы не пересоздавать WS при изменении колбэков
    useEffect(() => { onUpdateRef.current = onUpdate; });
    useEffect(() => { onDoneRef.current = onDone; });

    const connect = useCallback(() => {
        if (!projectId || !enabled) return;

        // Закрываем предыдущее соединение если есть
        if (wsRef.current) {
            wsRef.current.onclose = null;
            wsRef.current.close();
        }

        // R13-И3: передаём api_key через query param (WS не поддерживает заголовки в браузере)
        const apiKey = localStorage.getItem('tv_api_key') || '';
        const url = apiKey
            ? `${WS_BASE}/projects/${projectId}/ws?api_key=${encodeURIComponent(apiKey)}`
            : `${WS_BASE}/projects/${projectId}/ws`;
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onmessage = (event) => {
            try {
                const data: WSProjectStatus = JSON.parse(event.data);
                onUpdateRef.current(data);
            } catch {
                // ignore parse errors
            }
        };

        ws.onclose = () => {
            wsRef.current = null;
            onDoneRef.current?.();
        };

        ws.onerror = () => {
            // При ошибке WS — не крашим, просто закрываем (Dashboard может fallback на polling)
            ws.close();
        };
    }, [projectId, enabled]);

    useEffect(() => {
        if (enabled && projectId) {
            connect();
        } else {
            // Если не enabled — закрываем WS
            if (wsRef.current) {
                wsRef.current.onclose = null;
                wsRef.current.close();
                wsRef.current = null;
            }
        }

        return () => {
            if (wsRef.current) {
                wsRef.current.onclose = null;
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [enabled, projectId, connect]);
}
