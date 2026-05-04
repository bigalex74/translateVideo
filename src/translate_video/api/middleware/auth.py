"""Расширенный API-ключ middleware с поддержкой per-user ключей (backlog).

## Режимы работы

### 1. Один глобальный ключ (старый режим)
Задайте переменную ``API_KEY``.
Все запросы проверяются против этого ключа.

### 2. Per-user ключи (новый режим)
Задайте ``API_KEYS`` — JSON-словарь или список ключей:
- JSON-словарь: ``API_KEYS={"user1": "key-abc", "admin": "key-xyz"}``
  В этом случае к каждому запросу добавляется заголовок ``X-API-User``.
- JSON-список: ``API_KEYS=["key-abc", "key-xyz"]``
  Любой ключ из списка принимается.

### 3. Без аутентификации (локальный режим)
Если ни ``API_KEY``, ни ``API_KEYS`` не заданы — всё открыто.

## Управление ключами через API (admin endpoint)

При задании ``ADMIN_API_KEY`` активируется endpoint:
- ``GET /api/admin/keys`` — список пользователей (без ключей)
- ``POST /api/admin/keys`` — создать нового пользователя
- ``DELETE /api/admin/keys/{user}`` — удалить пользователя
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    pass

# Пути, которые доступны без ключа даже при включённой защите
_PUBLIC_PREFIXES = (
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/runs/",
)


def _load_api_keys() -> dict[str, str]:
    """Загрузить ключи из переменных окружения.

    Возвращает словарь {user: key}. Пустой словарь = auth выключен.
    """
    # Приоритет 1: API_KEYS (per-user)
    raw = os.getenv("API_KEYS", "")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
            if isinstance(parsed, list):
                # Список ключей — user = ключ
                return {k: k for k in parsed if isinstance(k, str)}
        except json.JSONDecodeError:
            # Одна строка — трактуем как единственный ключ
            return {"default": raw.strip()}

    # Приоритет 2: API_KEY (один глобальный)
    single = os.getenv("API_KEY", "").strip()
    if single:
        return {"default": single}

    return {}


class APIKeyStore:
    """Thread-safe хранилище API-ключей с поддержкой горячего обновления."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._keys: dict[str, str] = _load_api_keys()  # {user: key}
        self._reverse: dict[str, str] = {v: k for k, v in self._keys.items()}

    def is_enabled(self) -> bool:
        with self._lock:
            return bool(self._keys)

    def authenticate(self, api_key: str) -> str | None:
        """Проверить ключ. Вернуть имя пользователя или None."""
        with self._lock:
            return self._reverse.get(api_key)

    def list_users(self) -> list[str]:
        with self._lock:
            return list(self._keys.keys())

    def add_user(self, user: str, key: str | None = None) -> str:
        """Добавить пользователя. Если key=None — генерируем."""
        new_key = key or secrets.token_urlsafe(32)
        with self._lock:
            self._keys[user] = new_key
            self._reverse[new_key] = user
            self._persist()
        return new_key

    def remove_user(self, user: str) -> bool:
        with self._lock:
            key = self._keys.pop(user, None)
            if key:
                self._reverse.pop(key, None)
                self._persist()
                return True
        return False

    def _persist(self) -> None:
        """Сохранить ключи в API_KEYS_FILE если задан."""
        keys_file = os.getenv("API_KEYS_FILE", "")
        if not keys_file:
            return
        try:
            Path(keys_file).write_text(
                json.dumps(self._keys, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass


# Глобальный singleton
_KEY_STORE = APIKeyStore()


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Проверяет заголовок X-API-Key с поддержкой per-user ключей."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._store = _KEY_STORE
        # Обратная совместимость: один глобальный ключ
        self._single_key = os.getenv("API_KEY", "").strip()

    async def dispatch(self, request: Request, call_next):
        # Если auth не настроен — всё открыто
        if not self._store.is_enabled():
            return await call_next(request)

        path = request.url.path

        # Статика фронтенда
        if path == "/" or not path.startswith("/api"):
            return await call_next(request)

        # Публичные API-пути
        if any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)

        # Проверяем ключ
        provided = request.headers.get("X-API-Key", "")
        user = self._store.authenticate(provided)

        if user is None:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Invalid or missing API key. Provide X-API-Key header.",
                    "hint": "Set API_KEY or API_KEYS environment variable.",
                },
                headers={"WWW-Authenticate": "ApiKey"},
            )

        # Добавляем user в state для downstream handlers
        request.state.api_user = user
        return await call_next(request)


def get_key_store() -> APIKeyStore:
    """Получить глобальный APIKeyStore (для admin endpoints)."""
    return _KEY_STORE
