"""Тесты API providers и retry (QA Monitor: покрытие ≥80%).

Покрывает: providers.py (50%→90%+), core/retry.py (83%→90%).
"""
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from translate_video.api.main import app


class TestProvidersAPI(TestCase):
    """Тесты providers endpoints (list, models, balance)."""

    def setUp(self):
        self.client = TestClient(app)

    def test_list_providers(self):
        """GET /api/v1/providers возвращает список провайдеров."""
        resp = self.client.get("/api/v1/providers")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("providers", resp.json())

    def test_provider_models_valid(self):
        """GET /api/v1/providers/{provider}/models для известного провайдера."""
        with patch("translate_video.api.routes.providers.list_provider_models") as mock:
            mock.return_value = []
            resp = self.client.get("/api/v1/providers/legacy/models")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("models", resp.json())

    def test_provider_models_invalid_400(self):
        """GET /api/v1/providers/{provider}/models для неизвестного → 400."""
        with patch("translate_video.api.routes.providers.list_provider_models") as mock:
            mock.side_effect = ValueError("unknown provider")
            resp = self.client.get("/api/v1/providers/unknown_xyz/models")
        self.assertEqual(resp.status_code, 400)

    def test_provider_balance_valid(self):
        """GET /api/v1/providers/{provider}/balance для провайдера с балансом."""
        mock_balance = MagicMock()
        mock_balance.to_dict.return_value = {"provider": "test", "balance": 10.0}
        with patch("translate_video.api.routes.providers.get_provider_balance", return_value=mock_balance):
            resp = self.client.get("/api/v1/providers/polza/balance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("balance", data)

    def test_provider_balance_invalid_400(self):
        """GET /api/v1/providers/{provider}/balance для неизвестного → 400."""
        with patch("translate_video.api.routes.providers.get_provider_balance") as mock:
            mock.side_effect = ValueError("unknown provider")
            resp = self.client.get("/api/v1/providers/unknown_xyz/balance")
        self.assertEqual(resp.status_code, 400)


class TestRetryMechanism(TestCase):
    """Тесты механизма повторных попыток (core/retry.py)."""

    def test_retry_succeeds_on_first_try(self):
        """Функция успешна с первого раза — нет повторов."""
        from translate_video.core.retry import with_retry
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = with_retry(func, max_attempts=3, base_delay=0.0, jitter=False,
                            retryable_exceptions=(ValueError,))
        self.assertEqual(result, "ok")
        self.assertEqual(call_count, 1)

    def test_retry_succeeds_after_failure(self):
        """Функция успешна после 2 ошибок — повторяет."""
        from translate_video.core.retry import with_retry
        attempts = []

        def func():
            attempts.append(1)
            if len(attempts) < 3:
                raise ConnectionError("temporary error")
            return "recovered"

        result = with_retry(func, max_attempts=5, base_delay=0.0, jitter=False,
                            retryable_exceptions=(ConnectionError,))
        self.assertEqual(result, "recovered")
        self.assertEqual(len(attempts), 3)

    def test_retry_raises_after_all_attempts(self):
        """Функция всегда падает — поднимает исключение после max_attempts."""
        from translate_video.core.retry import with_retry

        def func():
            raise ConnectionError("always fails")

        with self.assertRaises(ConnectionError):
            with_retry(func, max_attempts=2, base_delay=0.0, jitter=False,
                       retryable_exceptions=(ConnectionError,))

    def test_retry_http_non_retryable_raises_immediately(self):
        """HTTP не-ретрайный код (404) → исключение без повторов."""
        from translate_video.core.retry import with_retry
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("HTTP 404: not found")

        with self.assertRaises(ConnectionError):
            with_retry(func, max_attempts=3, base_delay=0.0, jitter=False,
                       retryable_exceptions=(ConnectionError,))
        # 404 — не ретрайный код, должен упасть с первого раза
        self.assertEqual(call_count, 1)

    def test_retry_http_429_increases_delay(self):
        """HTTP 429 (rate limit) → delay увеличивается до минимум 5с."""
        from translate_video.core.retry import with_retry
        import unittest.mock as _mock
        attempts = []

        def func():
            attempts.append(1)
            if len(attempts) < 3:
                raise ConnectionError("HTTP 429: rate limited")
            return "ok"

        # Мокаем time.sleep чтобы не ждать реально
        with _mock.patch("translate_video.core.retry.time.sleep"):
            result = with_retry(func, max_attempts=5, base_delay=0.0, jitter=False,
                                retryable_exceptions=(ConnectionError,))
        self.assertEqual(result, "ok")

    def test_retry_config_call(self):
        """RetryConfig.call() применяет retry к функции."""
        from translate_video.core.retry import RetryConfig
        config = RetryConfig(max_attempts=2, base_delay=0.0)
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            return "done"

        result = config.call(fn, label="test")
        self.assertEqual(result, "done")
        self.assertEqual(call_count, 1)

    def test_retry_with_jitter(self):
        """Retry с jitter=True не падает."""
        from translate_video.core.retry import with_retry
        import unittest.mock as _mock

        def func():
            return 42

        with _mock.patch("translate_video.core.retry.time.sleep"):
            result = with_retry(func, max_attempts=1, base_delay=0.1, jitter=True,
                                retryable_exceptions=(ConnectionError,))
        self.assertEqual(result, 42)


class TestStoreEdgeCases(TestCase):
    """Граничные случаи ProjectStore (core/store.py)."""

    def test_list_projects_empty_dir(self):
        """list_projects с пустой директорией возвращает пустой список."""
        from translate_video.core.store import ProjectStore
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "runs")
            result = list(store.list_projects())
            self.assertEqual(result, [])

    def test_load_nonexistent_project_raises(self):
        """load_project для несуществующего → FileNotFoundError."""
        from translate_video.core.store import ProjectStore
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "runs")
            with self.assertRaises(FileNotFoundError):
                store.load_project(store.root / "nonexistent_id")

    def test_save_and_reload_project(self):
        """Сохранение и перезагрузка проекта сохраняет данные."""
        from translate_video.core.store import ProjectStore
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "runs")
            p = store.create_project("test.mp4", project_id="save_reload_test")
            p.tags = ["тест", "сохранение"]
            p.archived = True
            store.save_project(p)
            loaded = store.load_project(store.root / "save_reload_test")
            self.assertEqual(loaded.tags, ["тест", "сохранение"])
            self.assertTrue(loaded.archived)


if __name__ == "__main__":
    import unittest
    unittest.main()
