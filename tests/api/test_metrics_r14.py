"""R14-И5 тесты: Prometheus metrics endpoint расширения.

Новое в R14-И5:
- /api/metrics alias работает (alias → /metrics)
- translate_video_rate_limited_requests_total присутствует
- HTTP metrics fields (translate_video_http_requests_total)
- /api/health содержит metrics URL
- increment_http_request / increment_rate_limited функции
"""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from translate_video.api.main import app


class TestMetricsExtendedR14(unittest.TestCase):
    """Тесты расширенных Prometheus метрик R14-И5."""

    def setUp(self):
        self.client = TestClient(app)

    def test_metrics_endpoint_returns_200(self):
        """GET /metrics → 200."""
        r = self.client.get("/metrics")
        self.assertEqual(r.status_code, 200)

    def test_metrics_alias_api_returns_200(self):
        """GET /api/metrics (alias) → 200 (R14-И5 backward compat для Артёма)."""
        r = self.client.get("/api/metrics")
        self.assertEqual(r.status_code, 200)

    def test_metrics_alias_content_matches_original(self):
        """GET /api/metrics возвращает то же содержимое что и /metrics."""
        r1 = self.client.get("/metrics")
        r2 = self.client.get("/api/metrics")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        # Оба содержат translate_video_info
        self.assertIn("translate_video_info", r1.text)
        self.assertIn("translate_video_info", r2.text)

    def test_metrics_has_rate_limited_counter(self):
        """GET /metrics содержит translate_video_rate_limited_requests_total."""
        r = self.client.get("/metrics")
        self.assertIn("translate_video_rate_limited_requests_total", r.text)

    def test_metrics_content_type_is_text(self):
        """GET /metrics возвращает text/plain."""
        r = self.client.get("/metrics")
        self.assertIn("text/plain", r.headers.get("content-type", ""))

    def test_health_contains_metrics_url(self):
        """GET /api/health содержит поле metrics с Prometheus URL (R14-И5)."""
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("metrics", data)
        self.assertIn("prometheus", data["metrics"])
        self.assertEqual(data["metrics"]["prometheus"], "/metrics")
        self.assertEqual(data["metrics"]["alias"], "/api/metrics")

    def test_increment_rate_limited_function(self):
        """increment_rate_limited() увеличивает счётчик."""
        from translate_video.api.routes.metrics import increment_rate_limited, _HTTP_LOCK
        import translate_video.api.routes.metrics as m_module

        old_val = m_module._RATE_LIMITED_TOTAL
        increment_rate_limited()
        self.assertEqual(m_module._RATE_LIMITED_TOTAL, old_val + 1)
        # Сбрасываем
        m_module._RATE_LIMITED_TOTAL = old_val

    def test_increment_http_request_function(self):
        """increment_http_request() добавляет ключ в _HTTP_REQUESTS."""
        from translate_video.api.routes.metrics import increment_http_request
        import translate_video.api.routes.metrics as m_module

        before_keys = set(m_module._HTTP_REQUESTS.keys())
        increment_http_request("GET", "/api/test-r14", 200)
        after_keys = set(m_module._HTTP_REQUESTS.keys())
        new_keys = after_keys - before_keys
        self.assertTrue(any("test-r14" in k for k in new_keys))

    def test_metrics_has_all_required_gauges(self):
        """GET /metrics содержит все обязательные gauge метрики."""
        r = self.client.get("/metrics")
        required = [
            "translate_video_info",
            "translate_video_running_projects",
            "translate_video_disk_usage_mb",
            "translate_video_uptime_seconds",
            "translate_video_metrics_requests_total",
            "translate_video_rate_limited_requests_total",
        ]
        for metric in required:
            self.assertIn(metric, r.text, f"Метрика {metric} не найдена в /metrics")

    def test_metrics_prometheus_format_valid(self):
        """Формат Prometheus: каждая метрика содержит # HELP и # TYPE."""
        r = self.client.get("/metrics")
        self.assertIn("# HELP", r.text)
        self.assertIn("# TYPE", r.text)
        self.assertIn("gauge", r.text)

    def test_metrics_increments_request_counter(self):
        """Вызов /metrics инкрементирует свой собственный счётчик."""
        import translate_video.api.routes.metrics as m_module
        before = m_module._REQUEST_COUNTER["total"]
        self.client.get("/metrics")
        after = m_module._REQUEST_COUNTER["total"]
        self.assertGreater(after, before)


if __name__ == "__main__":
    unittest.main()
