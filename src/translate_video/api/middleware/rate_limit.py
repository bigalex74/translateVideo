"""R13-И3: Rate limiting middleware для защиты API от злоупотреблений.

## Политика:
- POST /api/v1/projects (upload): 10 запросов / 60с на IP
- DELETE /api/v1/projects/*: 20 / 60с на IP
- PATCH /api/v1/projects/*/rename: 30 / 60с на IP
- GET endpoints: не лимитируются (readonly, нет смысла)
- /api/v1/projects/*/run (POST): уже лимитирован в pipeline.py (5/60с)

## Почему не slowapi/redis:
- Инстанс один, shared memory достаточно
- Zero dependencies
- Легко тестировать без инфраструктуры
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    pass


class _IPRateLimiter:
    """Thread-safe sliding window rate limiter per IP.

    Хранит временные метки запросов в deque. O(1) амортизированно.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._lock = threading.Lock()
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def check(self, ip: str) -> tuple[bool, int]:
        """Вернуть (allowed, remaining).

        allowed=False означает 429. remaining — сколько запросов ещё можно.
        """
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            dq = self._windows[ip]
            # Удаляем старые записи
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self.max_requests:
                return False, 0
            dq.append(now)
            remaining = self.max_requests - len(dq)
        return True, remaining

    def reset_for_ip(self, ip: str) -> None:
        """Сброс (для тестов)."""
        with self._lock:
            self._windows.pop(ip, None)


# Лимитеры по типу операции
_UPLOAD_LIMITER = _IPRateLimiter(max_requests=10, window_seconds=60.0)
_DELETE_LIMITER = _IPRateLimiter(max_requests=20, window_seconds=60.0)
_PATCH_LIMITER  = _IPRateLimiter(max_requests=30, window_seconds=60.0)


def _get_client_ip(request: Request) -> str:
    """Возвращает IP клиента с учётом reverse proxy."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Пути исключённые из rate limiting (даже если метод подходит)
_EXCLUDED_PATHS = {
    "/api/v1/projects/run",  # уже лимитируется в pipeline.py
}


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware: rate limiting для мутирующих endpoints.

    GET запросы пропускаются без ограничений.
    Лимитируются только POST (upload), DELETE, PATCH.
    """

    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path

        # WebSocket — пропускаем
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        # GET / HEAD / OPTIONS — не лимитируем
        if method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Не наши пути
        if not path.startswith("/api/v1/projects"):
            return await call_next(request)

        # Исключения
        if any(path.startswith(ex) for ex in _EXCLUDED_PATHS):
            return await call_next(request)

        # Если rate limiting отключён через env
        if os.getenv("DISABLE_RATE_LIMIT", "").lower() in ("1", "true", "yes"):
            return await call_next(request)

        ip = _get_client_ip(request)
        limiter: _IPRateLimiter | None = None

        if method == "POST" and path == "/api/v1/projects":
            # Upload создание проекта
            limiter = _UPLOAD_LIMITER
        elif method == "DELETE":
            limiter = _DELETE_LIMITER
        elif method == "PATCH":
            limiter = _PATCH_LIMITER

        if limiter is None:
            return await call_next(request)

        allowed, remaining = limiter.check(ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Слишком много запросов. Повторите через минуту.",
                    "hint": f"Лимит: {limiter.max_requests} запросов за {int(limiter.window)}с.",
                },
                headers={
                    "Retry-After": str(int(limiter.window)),
                    "X-RateLimit-Limit": str(limiter.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


def get_limiters() -> dict[str, _IPRateLimiter]:
    """Вернуть все лимитеры (для тестирования и мониторинга)."""
    return {
        "upload": _UPLOAD_LIMITER,
        "delete": _DELETE_LIMITER,
        "patch": _PATCH_LIMITER,
    }
