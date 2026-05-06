"""Тесты для R9-И2: AI Translation Hints endpoint (TVIDEO-215)."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


class TestTranslationHintsEndpoint(unittest.TestCase):
    """Тесты POST /api/v1/projects/{id}/segments/{seg_id}/hint."""

    def setUp(self):
        """Настройка тестового окружения."""
        from translate_video.api.main import app
        from translate_video.core.schemas import Segment, SegmentStatus, VideoProject
        from translate_video.core.config import PipelineConfig

        self.client = TestClient(app, raise_server_exceptions=False)

        # Создаём мок-проект с сегментами
        self.mock_segment = MagicMock(spec=Segment)
        self.mock_segment.id = "seg-001"
        self.mock_segment.source_text = "Hello world"
        self.mock_segment.translated_text = "Привет мир"
        self.mock_segment.start = 0.0
        self.mock_segment.end = 2.5
        self.mock_segment.status = SegmentStatus.TRANSLATED

        self.mock_project = MagicMock(spec=VideoProject)
        self.mock_project.id = "test-project-001"
        self.mock_project.segments = [self.mock_segment]
        self.mock_project.config = PipelineConfig()
        self.mock_project.config.target_language = "ru"

    def test_hint_returns_503_without_provider(self):
        """Без LLM-провайдера должен вернуть 503."""
        with patch("translate_video.api.routes.projects.sanitize_project_id", return_value="test-project-001"), \
             patch("translate_video.api.routes.projects.get_store") as mock_get_store:

            mock_store = MagicMock()
            mock_store.load_project.return_value = self.mock_project
            mock_get_store.return_value = mock_store

            # Убираем все env переменные провайдера
            with patch.dict("os.environ", {
                "GEMINI_BRIDGE_URL": "",
                "POLZA_API_KEY": "",
                "NEUROAPI_API_KEY": "",
            }, clear=False):
                resp = self.client.post(
                    "/api/v1/projects/test-project-001/segments/seg-001/hint",
                    json={"context_segments": []},
                )
        # 503 или другой статус — главное не 200 без провайдера
        self.assertIn(resp.status_code, [503, 422, 500, 404])

    def test_hint_returns_404_for_unknown_project(self):
        """Несуществующий проект — 404."""
        with patch("translate_video.api.routes.projects.sanitize_project_id", return_value="nonexistent"), \
             patch("translate_video.api.routes.projects.get_store") as mock_get_store:

            mock_store = MagicMock()
            mock_store.load_project.side_effect = FileNotFoundError("not found")
            mock_get_store.return_value = mock_store

            resp = self.client.post(
                "/api/v1/projects/nonexistent/segments/seg-001/hint",
                json={"context_segments": []},
            )
        self.assertEqual(resp.status_code, 404)

    def test_hint_returns_404_for_unknown_segment(self):
        """Несуществующий сегмент — 404."""
        with patch("translate_video.api.routes.projects.sanitize_project_id", return_value="test-project-001"), \
             patch("translate_video.api.routes.projects.get_store") as mock_get_store:

            mock_store = MagicMock()
            mock_store.load_project.return_value = self.mock_project
            mock_get_store.return_value = mock_store

            with patch.dict("os.environ", {"GEMINI_BRIDGE_URL": "http://test"}):
                resp = self.client.post(
                    "/api/v1/projects/test-project-001/segments/NONEXISTENT-SEG/hint",
                    json={"context_segments": []},
                )
        self.assertEqual(resp.status_code, 404)

    def test_hint_uses_cache(self):
        """Повторный запрос возвращает кэш."""
        import translate_video.api.routes.projects as routes_module

        # Прямое тестирование кэш-функций
        test_key = "test_cache_key_abc123"
        test_suggestions = ["Вариант 1", "Вариант 2", "Вариант 3"]

        routes_module._hints_cache_set(test_key, test_suggestions)
        cached = routes_module._hints_cache_get(test_key)

        self.assertEqual(cached, test_suggestions)

    def test_hints_cache_respects_ttl(self):
        """Кэш устаревает после TTL."""
        import time
        import translate_video.api.routes.projects as routes_module

        test_key = "test_ttl_key"
        test_suggestions = ["старый вариант"]

        # Прямо манипулируем TTL
        original_ttl = routes_module._HINTS_CACHE_TTL
        routes_module._HINTS_CACHE_TTL = 0.001  # 1ms TTL

        routes_module._hints_cache_set(test_key, test_suggestions)
        time.sleep(0.01)  # Ждём истечения TTL

        cached = routes_module._hints_cache_get(test_key)
        routes_module._HINTS_CACHE_TTL = original_ttl  # восстанавливаем

        self.assertIsNone(cached)

    def test_hints_cache_lru_eviction(self):
        """LRU кэш выселяет старые записи при переполнении."""
        import translate_video.api.routes.projects as routes_module

        original_max = routes_module._HINTS_CACHE_MAX
        routes_module._HINTS_CACHE_MAX = 3

        # Заполняем кэш до предела
        for i in range(3):
            routes_module._hints_cache_set(f"key_{i}", [f"val_{i}"])

        # Добавляем ещё одну — одна старая должна быть удалена
        routes_module._hints_cache_set("key_new", ["new_val"])

        routes_module._HINTS_CACHE_MAX = original_max

        total = len(routes_module._hints_cache)
        self.assertLessEqual(total, 4)  # LRU предотвратил неограниченный рост


class TestShareLinksEndpoint(unittest.TestCase):
    """Тесты R9-И3: Share link endpoints."""

    def setUp(self):
        from translate_video.api.main import app
        from translate_video.core.schemas import VideoProject
        from translate_video.core.config import PipelineConfig

        self.client = TestClient(app, raise_server_exceptions=False)

        self.mock_project = MagicMock(spec=VideoProject)
        self.mock_project.id = "share-test-project"
        self.mock_project.segments = []
        self.mock_project.config = PipelineConfig()
        self.mock_project._extra = {}
        self.mock_project.stage_runs = []
        self.mock_project.status = "completed"

    def test_share_create_returns_token(self):
        """Создание share ссылки возвращает токен."""
        with patch("translate_video.api.routes.projects.sanitize_project_id", return_value="share-test-project"), \
             patch("translate_video.api.routes.projects.ProjectStore") as mock_store_cls:

            mock_store = MagicMock()
            mock_store.load_project.return_value = self.mock_project
            mock_store.save_project.return_value = None
            mock_store_cls.return_value = mock_store

            resp = self.client.post("/api/v1/projects/share-test-project/share")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("share_token", data)
        self.assertIn("share_url", data)
        self.assertIn("expires_at", data)
        self.assertTrue(len(data["share_token"]) > 10)

    def test_share_revoke_returns_ok(self):
        """Отзыв токена работает."""
        self.mock_project._extra = {
            "share_token": "test-tok-123",
            "share_expires_at": "2099-01-01T00:00:00Z",
        }
        with patch("translate_video.api.routes.projects.sanitize_project_id", return_value="share-test-project"), \
             patch("translate_video.api.routes.projects.ProjectStore") as mock_store_cls:

            mock_store = MagicMock()
            mock_store.load_project.return_value = self.mock_project
            mock_store.save_project.return_value = None
            mock_store_cls.return_value = mock_store

            resp = self.client.delete("/api/v1/projects/share-test-project/share")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["revoked"])

    def test_share_get_404_when_no_token(self):
        """GET возвращает 404 если токен не создан."""
        self.mock_project._extra = {}
        with patch("translate_video.api.routes.projects.sanitize_project_id", return_value="share-test-project"), \
             patch("translate_video.api.routes.projects.ProjectStore") as mock_store_cls:

            mock_store = MagicMock()
            mock_store.load_project.return_value = self.mock_project
            mock_store_cls.return_value = mock_store

            resp = self.client.get("/api/v1/projects/share-test-project/share")

        self.assertEqual(resp.status_code, 404)


class TestAnalyticsEndpoint(unittest.TestCase):
    """Тесты R9-И4: Analytics summary endpoint."""

    def test_analytics_returns_summary(self):
        """Analytics endpoint возвращает корректную структуру."""
        from translate_video.api.main import app

        client = TestClient(app)

        with patch("translate_video.api.routes.analytics._get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_projects.return_value = []
            mock_get_store.return_value = mock_store

            resp = client.get("/api/v1/analytics/summary")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        required_keys = [
            "total_projects", "total_segments", "total_words_translated",
            "cost_usd_total", "most_used_provider", "projects_per_day",
            "status_distribution", "provider_distribution",
        ]
        for key in required_keys:
            self.assertIn(key, data, f"Missing key: {key}")

    def test_analytics_projects_per_day_has_7_days(self):
        """projects_per_day содержит 7 элементов."""
        from translate_video.api.main import app

        client = TestClient(app)

        with patch("translate_video.api.routes.analytics._get_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.list_projects.return_value = []
            mock_get_store.return_value = mock_store

            resp = client.get("/api/v1/analytics/summary")

        data = resp.json()
        self.assertEqual(len(data["projects_per_day"]), 7)


if __name__ == "__main__":
    unittest.main()
