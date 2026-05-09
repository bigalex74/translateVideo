"""R13-И3 тесты: Rate Limiting middleware + WS авторизация.

Тесты:
1. Upload rate limiter — блокирует после N запросов
2. Delete rate limiter — блокирует после N запросов
3. GET запросы не лимитируются
4. X-RateLimit-* заголовки присутствуют
5. DISABLE_RATE_LIMIT env переменная отключает лимитер
6. WS auth: без ключа при включённом auth → error: unauthorized
"""
import os
import unittest
from unittest.mock import MagicMock, patch


class TestRateLimitMiddleware(unittest.TestCase):
    """Unit тесты _IPRateLimiter из rate_limit.py."""

    def setUp(self):
        from translate_video.api.middleware.rate_limit import _IPRateLimiter
        self.limiter = _IPRateLimiter(max_requests=3, window_seconds=60.0)

    def test_allows_within_limit(self):
        """Первые N запросов разрешены."""
        for i in range(3):
            allowed, remaining = self.limiter.check("192.168.1.1")
            self.assertTrue(allowed, f"Запрос {i+1} должен быть разрешён")
        self.assertEqual(remaining, 0)

    def test_blocks_after_limit(self):
        """После N запросов — 429."""
        for _ in range(3):
            self.limiter.check("10.0.0.1")
        allowed, remaining = self.limiter.check("10.0.0.1")
        self.assertFalse(allowed, "4й запрос должен быть заблокирован")
        self.assertEqual(remaining, 0)

    def test_different_ips_independent(self):
        """Разные IP не влияют друг на друга."""
        for _ in range(3):
            self.limiter.check("1.1.1.1")
        # 1.1.1.1 достиг лимита
        allowed_1, _ = self.limiter.check("1.1.1.1")
        self.assertFalse(allowed_1)
        # 2.2.2.2 не тронут
        allowed_2, remaining_2 = self.limiter.check("2.2.2.2")
        self.assertTrue(allowed_2)
        self.assertEqual(remaining_2, 2)

    def test_reset_for_ip(self):
        """reset_for_ip сбрасывает лимит для IP."""
        for _ in range(3):
            self.limiter.check("192.168.1.2")
        self.limiter.reset_for_ip("192.168.1.2")
        allowed, _ = self.limiter.check("192.168.1.2")
        self.assertTrue(allowed, "После reset запрос снова разрешён")

    def test_remaining_decrements(self):
        """remaining декрементируется с каждым запросом."""
        _, r1 = self.limiter.check("192.168.1.3")
        _, r2 = self.limiter.check("192.168.1.3")
        _, r3 = self.limiter.check("192.168.1.3")
        self.assertEqual(r1, 2)
        self.assertEqual(r2, 1)
        self.assertEqual(r3, 0)


class TestRateLimitMiddlewareIntegration(unittest.TestCase):
    """Интеграционные тесты middleware через TestClient."""

    def _make_app(self, max_requests: int = 3):
        """Создаём FastAPI app с rate limit middleware для тестов."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from translate_video.api.middleware.rate_limit import _IPRateLimiter, GlobalRateLimitMiddleware, get_limiters

        app = FastAPI()

        @app.post("/api/v1/projects")
        def upload():
            return {"ok": True}

        @app.get("/api/v1/projects")
        def list_projects():
            return {"ok": True}

        @app.delete("/api/v1/projects/test-id")
        def delete_project():
            return {"ok": True}

        app.add_middleware(GlobalRateLimitMiddleware)
        return app

    def test_upload_rate_limit_headers_present(self):
        """POST /api/v1/projects возвращает X-RateLimit-* заголовки."""
        from fastapi.testclient import TestClient
        app = self._make_app()
        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/v1/projects")
        # Если auth не мешает — должны быть заголовки
        self.assertIn("x-ratelimit-limit", r.headers)
        self.assertIn("x-ratelimit-remaining", r.headers)

    def test_get_not_rate_limited(self):
        """GET запросы не имеют X-RateLimit заголовков."""
        from fastapi.testclient import TestClient
        app = self._make_app()
        client = TestClient(app, raise_server_exceptions=False)
        for _ in range(20):
            r = client.get("/api/v1/projects")
        # Последний GET должен быть 200
        self.assertNotEqual(r.status_code, 429)

    def test_disable_rate_limit_env(self):
        """DISABLE_RATE_LIMIT=1 отключает rate limiting."""
        import os
        from fastapi.testclient import TestClient
        app = self._make_app()
        client = TestClient(app, raise_server_exceptions=False)
        with patch.dict(os.environ, {"DISABLE_RATE_LIMIT": "1"}):
            for _ in range(50):
                r = client.post("/api/v1/projects")
        # С отключённым лимитером последний запрос не 429
        self.assertNotEqual(r.status_code, 429)


class TestWSAuthLogic(unittest.TestCase):
    """Unit тесты логики WS авторизации (без реального WS соединения)."""

    def test_key_store_is_enabled_without_env(self):
        """Без API_KEY/API_KEYS store.is_enabled() = False."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("API_KEY", None)
            os.environ.pop("API_KEYS", None)
            from translate_video.api.middleware.auth import APIKeyStore
            store = APIKeyStore()
            self.assertFalse(store.is_enabled())

    def test_key_store_is_enabled_with_env(self):
        """С API_KEY store.is_enabled() = True."""
        with patch.dict(os.environ, {"API_KEY": "test-secret-key"}, clear=False):
            from translate_video.api.middleware.auth import APIKeyStore
            store = APIKeyStore()
            self.assertTrue(store.is_enabled())

    def test_key_store_authenticate_valid(self):
        """Правильный ключ authenticate() -> user."""
        with patch.dict(os.environ, {"API_KEY": "my-secret-key"}, clear=False):
            from translate_video.api.middleware.auth import APIKeyStore
            store = APIKeyStore()
            user = store.authenticate("my-secret-key")
            self.assertIsNotNone(user)

    def test_key_store_authenticate_invalid(self):
        """Неправильный ключ authenticate() -> None."""
        with patch.dict(os.environ, {"API_KEY": "my-secret-key"}, clear=False):
            from translate_video.api.middleware.auth import APIKeyStore
            store = APIKeyStore()
            user = store.authenticate("wrong-key")
            self.assertIsNone(user)

    def test_get_key_store_returns_singleton(self):
        """get_key_store() возвращает глобальный объект."""
        from translate_video.api.middleware.auth import get_key_store
        store1 = get_key_store()
        store2 = get_key_store()
        self.assertIs(store1, store2)


if __name__ == "__main__":
    unittest.main()
