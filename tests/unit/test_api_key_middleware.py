"""Модульные тесты APIKeyMiddleware."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.requests import Request
from starlette.responses import JSONResponse

from translate_video.api.middleware.auth import APIKeyMiddleware


def _make_request(path: str, api_key: str | None = None) -> Request:
    """Создать минимальный объект Request для тестов."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
    }
    if api_key is not None:
        scope["headers"] = [(b"x-api-key", api_key.encode())]
    return Request(scope)


class APIKeyMiddlewareTest(unittest.IsolatedAsyncioTestCase):
    """TVIDEO-136: APIKeyMiddleware пропускает/блокирует запросы по X-API-Key."""

    async def _dispatch(
        self,
        middleware: APIKeyMiddleware,
        request: Request,
        next_response=None,
    ):
        """Вызвать dispatch, подставив мок-callback."""
        if next_response is None:
            next_response = JSONResponse({"ok": True}, status_code=200)
        call_next = AsyncMock(return_value=next_response)
        return await middleware.dispatch(request, call_next)

    async def test_no_api_key_env_allows_all(self):
        """Без API_KEY все запросы проходят без проверки."""
        mw = APIKeyMiddleware(MagicMock(), api_key="")
        req = _make_request("/api/v1/projects")
        resp = await self._dispatch(mw, req)
        self.assertEqual(resp.status_code, 200)

    async def test_valid_key_allows_request(self):
        """Правильный X-API-Key пропускает запрос."""
        mw = APIKeyMiddleware(MagicMock(), api_key="secret123")
        req = _make_request("/api/v1/projects", api_key="secret123")
        resp = await self._dispatch(mw, req)
        self.assertEqual(resp.status_code, 200)

    async def test_wrong_key_returns_401(self):
        """Неправильный ключ возвращает 401."""
        mw = APIKeyMiddleware(MagicMock(), api_key="secret123")
        req = _make_request("/api/v1/projects", api_key="wrongkey")
        resp = await self._dispatch(mw, req)
        self.assertEqual(resp.status_code, 401)

    async def test_missing_key_returns_401(self):
        """Отсутствующий ключ возвращает 401."""
        mw = APIKeyMiddleware(MagicMock(), api_key="secret123")
        req = _make_request("/api/v1/projects")
        resp = await self._dispatch(mw, req)
        self.assertEqual(resp.status_code, 401)

    async def test_health_check_bypasses_auth(self):
        """Эндпоинт /api/health не требует ключа."""
        mw = APIKeyMiddleware(MagicMock(), api_key="secret123")
        req = _make_request("/api/health")
        resp = await self._dispatch(mw, req)
        self.assertEqual(resp.status_code, 200)

    async def test_docs_bypasses_auth(self):
        """Swagger /docs не требует ключа."""
        mw = APIKeyMiddleware(MagicMock(), api_key="secret123")
        req = _make_request("/docs")
        resp = await self._dispatch(mw, req)
        self.assertEqual(resp.status_code, 200)

    async def test_static_frontend_bypasses_auth(self):
        """Фронтенд (/) не требует ключа."""
        mw = APIKeyMiddleware(MagicMock(), api_key="secret123")
        req = _make_request("/")
        resp = await self._dispatch(mw, req)
        self.assertEqual(resp.status_code, 200)

    async def test_api_key_from_env(self):
        """APIKeyMiddleware читает ключ из переменной окружения API_KEY."""
        with patch.dict("os.environ", {"API_KEY": "envkey"}, clear=False):
            mw = APIKeyMiddleware(MagicMock())
            req = _make_request("/api/v1/projects", api_key="envkey")
            resp = await self._dispatch(mw, req)
            self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
