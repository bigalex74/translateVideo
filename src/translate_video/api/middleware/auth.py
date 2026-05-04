"""Опциональный API-ключ middleware для защиты всех эндпоинтов.

Активируется только если переменная окружения ``API_KEY`` задана и непуста.
При активации все запросы должны содержать заголовок:

    X-API-Key: <значение API_KEY>

Публичные пути (не требуют ключа):
- /api/health
- /docs, /redoc, /openapi.json  (Swagger UI)
- /      (статика фронтенда)

Если ``API_KEY`` не задан — middleware пропускает все запросы без проверки.
Это позволяет использовать сервер локально без конфигурации.
"""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


# Пути, которые доступны без ключа даже при включённой защите
_PUBLIC_PREFIXES = (
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/runs/",   # статические файлы артефактов (защищены именем проекта)
)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Проверяет заголовок X-API-Key если переменная API_KEY задана."""

    def __init__(self, app, *, api_key: str | None = None) -> None:
        super().__init__(app)
        self._api_key = api_key or os.getenv("API_KEY") or ""

    async def dispatch(self, request: Request, call_next):
        # Если ключ не настроен — всё открыто
        if not self._api_key:
            return await call_next(request)

        path = request.url.path

        # Статика фронтенда (/, /index.html, /assets/...)
        if path == "/" or not path.startswith("/api"):
            return await call_next(request)

        # Публичные API-пути
        if any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)

        # Проверяем ключ
        provided = request.headers.get("X-API-Key", "")
        if provided != self._api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Invalid or missing API key. "
                    "Provide X-API-Key header.",
                    "hint": "Set API_KEY environment variable to disable auth.",
                },
            )

        return await call_next(request)
