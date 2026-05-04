"""Admin API endpoints для управления API-ключами (per-user auth).

Защищён отдельным ADMIN_API_KEY из переменной окружения.
Если ADMIN_API_KEY не задан — эндпоинты возвращают 403.
"""

from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from translate_video.api.middleware.auth import get_key_store, APIKeyStore

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(x_admin_key: str = Header(..., alias="X-Admin-Key")) -> None:
    """Dependency: проверяет X-Admin-Key против ADMIN_API_KEY."""
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
