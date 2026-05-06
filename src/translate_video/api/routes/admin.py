"""Admin API endpoints для управления API-ключами (per-user auth).

Защищён отдельным ADMIN_API_KEY из переменной окружения.
Если ADMIN_API_KEY не задан — эндпоинты возвращают 403.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from translate_video.api.middleware.auth import get_key_store, APIKeyStore

router = APIRouter(prefix="/api/admin", tags=["admin"])


class _RateLimiter:
    """Simple in-memory rate limiter (NC2-04): max N requests per window per IP."""

    def __init__(self, max_requests: int = 10, window_s: float = 60.0) -> None:
        self._max = max_requests
        self._window = window_s
        self._requests: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._requests[client_ip]
            # Удаляем устаревшие записи
            while q and now - q[0] > self._window:
                q.popleft()
            if len(q) >= self._max:
                return False
            q.append(now)
            return True


_ADMIN_RATE_LIMITER = _RateLimiter(
    max_requests=int(os.getenv("ADMIN_RATE_LIMIT", "10")),
    window_s=float(os.getenv("ADMIN_RATE_WINDOW", "60")),
)


def _require_admin(
    request: Request,
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
) -> None:
    """Dependency: проверяет X-Admin-Key + rate limit по IP (NC2-04)."""
    client_ip = request.client.host if request.client else "unknown"

    # Rate limit проверка
    if not _ADMIN_RATE_LIMITER.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Слишком много запросов к Admin API. Попробуйте через 60 сек.",
            headers={"Retry-After": "60"},
        )

    admin_key = os.getenv("ADMIN_API_KEY", "")
    if not admin_key:
        raise HTTPException(
            status_code=403,
            detail="Admin API не активирован. Задайте ADMIN_API_KEY.",
        )
    if x_admin_key != admin_key:
        raise HTTPException(status_code=401, detail="Неверный Admin API Key.")


class CreateKeyRequest(BaseModel):
    user: str = Field(..., min_length=1, max_length=64, description="Имя пользователя")
    key: str | None = Field(
        None,
        min_length=16,
        description="API-ключ. Если не задан — генерируется автоматически.",
    )


class CreateKeyResponse(BaseModel):
    user: str
    key: str
    message: str


class UserListResponse(BaseModel):
    users: list[str]
    total: int
    auth_enabled: bool


@router.get(
    "/keys",
    response_model=UserListResponse,
    summary="Список API-пользователей",
    description="Возвращает список пользователей (без ключей). Требует X-Admin-Key.",
)
def list_keys(
    _: None = Depends(_require_admin),
    store: APIKeyStore = Depends(get_key_store),
) -> UserListResponse:
    users = store.list_users()
    return UserListResponse(
        users=users,
        total=len(users),
        auth_enabled=store.is_enabled(),
    )


@router.post(
    "/keys",
    response_model=CreateKeyResponse,
    status_code=201,
    summary="Создать API-ключ для пользователя",
    description="Создаёт нового пользователя. Если key не указан — генерируется случайный.",
)
def create_key(
    req: CreateKeyRequest,
    _: None = Depends(_require_admin),
    store: APIKeyStore = Depends(get_key_store),
) -> CreateKeyResponse:
    if req.user in store.list_users():
        raise HTTPException(status_code=409, detail=f"Пользователь '{req.user}' уже существует.")
    new_key = store.add_user(req.user, req.key)
    return CreateKeyResponse(
        user=req.user,
        key=new_key,
        message=f"Пользователь '{req.user}' создан. Сохраните ключ — он показывается только один раз.",
    )


@router.delete(
    "/keys/{user}",
    status_code=200,
    summary="Удалить API-ключ пользователя",
)
def delete_key(
    user: str,
    _: None = Depends(_require_admin),
    store: APIKeyStore = Depends(get_key_store),
) -> dict:
    if not store.remove_user(user):
        raise HTTPException(status_code=404, detail=f"Пользователь '{user}' не найден.")
    return {"deleted": user}
