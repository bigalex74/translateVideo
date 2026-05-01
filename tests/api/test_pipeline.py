import tempfile
import socket
from pathlib import Path
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from translate_video.api.main import app
from translate_video.api.routes.pipeline import _running_projects
from translate_video.core.store import ProjectStore
from translate_video.api.routes.projects import get_store


class APIPipelineTest(TestCase):
    """Тесты API маршрутов запуска пайплайна."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_root = Path(self.temp_dir.name) / "runs"
        self.store = ProjectStore(self.work_root)
        app.dependency_overrides[get_store] = lambda: self.store
        self.client = TestClient(app)
        # Очищаем реестр запущенных проектов между тестами
        _running_projects.clear()

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()
        _running_projects.clear()

    @patch("translate_video.api.routes.pipeline.asyncio.to_thread", new_callable=AsyncMock)
    def test_run_pipeline_background(self, mock_thread):
        """Запуск пайплайна должен возвращать 200 сразу (background task)."""
        self.store.create_project("dummy.mp4", project_id="run_test")
        # TestClient выполняет background tasks синхронно
        response = self.client.post("/api/v1/projects/run_test/run", json={"provider": "fake"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "accepted")
        self.assertEqual(data["project_id"], "run_test")

    def test_run_pipeline_not_found(self):
        """Запуск несуществующего проекта возвращает 404."""
        response = self.client.post("/api/v1/projects/missing/run", json={"provider": "fake"})
        self.assertEqual(response.status_code, 404)

    def test_run_pipeline_rejects_path_traversal_id(self):
        """Запуск пайплайна не должен принимать небезопасный ID."""
        response = self.client.post("/api/v1/projects/%2E%2E/run", json={"provider": "fake"})
        self.assertEqual(response.status_code, 400)

    @patch("translate_video.api.routes.pipeline.asyncio.to_thread", new_callable=AsyncMock)
    def test_run_pipeline_with_webhook(self, mock_thread):
        """Запуск с webhook-заголовком должен вызвать notify_webhook после завершения."""
        self.store.create_project("dummy.mp4", project_id="webhook_test")
        public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        with (
            patch("translate_video.api.routes.pipeline.socket.getaddrinfo", return_value=public_dns),
            patch("translate_video.api.routes.pipeline.notify_webhook", new_callable=AsyncMock) as mock_notify,
        ):
            self.client.post(
                "/api/v1/projects/webhook_test/run",
                json={"provider": "fake"},
                headers={"X-Webhook-Url": "http://example.com/webhook"},
            )
            mock_notify.assert_called_once()

    @patch("translate_video.api.routes.pipeline.asyncio.to_thread", new_callable=AsyncMock)
    def test_run_pipeline_webhook_on_error(self, mock_thread):
        """Webhook должен вызываться при ошибке пайплайна."""
        mock_thread.side_effect = Exception("Pipeline failed")
        self.store.create_project("dummy.mp4", project_id="webhook_err_test")
        public_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        with (
            patch("translate_video.api.routes.pipeline.socket.getaddrinfo", return_value=public_dns),
            patch("translate_video.api.routes.pipeline.notify_webhook", new_callable=AsyncMock) as mock_notify,
        ):
            self.client.post(
                "/api/v1/projects/webhook_err_test/run",
                json={"provider": "fake"},
                headers={"X-Webhook-Url": "http://example.com/webhook"},
            )
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args[0][1]
            self.assertEqual(call_args["status"], "failed")

    @patch("translate_video.api.routes.pipeline.asyncio.to_thread", new_callable=AsyncMock)
    def test_run_pipeline_returns_409_if_already_running(self, mock_thread):
        """Повторный запуск уже работающего проекта возвращает 409."""
        self.store.create_project("dummy.mp4", project_id="busy_test")
        # Имитируем уже запущенный проект
        _running_projects.add("busy_test")
        response = self.client.post("/api/v1/projects/busy_test/run", json={"provider": "fake"})
        self.assertEqual(response.status_code, 409)

    def test_run_rejects_ssrf_private_ip_webhook(self):
        """Webhook на приватный IP должен возвращать 400."""
        self.store.create_project("dummy.mp4", project_id="ssrf_test")
        response = self.client.post(
            "/api/v1/projects/ssrf_test/run",
            json={"provider": "fake"},
            headers={"X-Webhook-Url": "http://127.0.0.1/steal"},
        )
        self.assertEqual(response.status_code, 400)

    def test_run_rejects_ssrf_localhost_webhook(self):
        """Webhook на localhost должен возвращать 400 даже без IP-литерала."""
        self.store.create_project("dummy.mp4", project_id="localhost_test")
        response = self.client.post(
            "/api/v1/projects/localhost_test/run",
            json={"provider": "fake"},
            headers={"X-Webhook-Url": "http://localhost/webhook"},
        )
        self.assertEqual(response.status_code, 400)

    def test_run_rejects_hostname_resolving_to_private_ip(self):
        """Webhook hostname не должен проходить, если DNS ведёт во внутреннюю сеть."""
        self.store.create_project("dummy.mp4", project_id="dns_private_test")
        private_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
        with patch("translate_video.api.routes.pipeline.socket.getaddrinfo", return_value=private_dns):
            response = self.client.post(
                "/api/v1/projects/dns_private_test/run",
                json={"provider": "fake"},
                headers={"X-Webhook-Url": "http://hooks.example.test/webhook"},
            )
        self.assertEqual(response.status_code, 400)

    def test_run_rejects_unresolved_webhook_hostname(self):
        """Webhook hostname должен быть проверяемым до запуска фоновой задачи."""
        self.store.create_project("dummy.mp4", project_id="dns_fail_test")
        with patch(
            "translate_video.api.routes.pipeline.socket.getaddrinfo",
            side_effect=socket.gaierror("not found"),
        ):
            response = self.client.post(
                "/api/v1/projects/dns_fail_test/run",
                json={"provider": "fake"},
                headers={"X-Webhook-Url": "https://missing.example.test/webhook"},
            )
        self.assertEqual(response.status_code, 400)

    def test_run_rejects_non_http_webhook(self):
        """Webhook с file:// схемой должен возвращать 400."""
        self.store.create_project("dummy.mp4", project_id="scheme_test")
        response = self.client.post(
            "/api/v1/projects/scheme_test/run",
            json={"provider": "fake"},
            headers={"X-Webhook-Url": "file:///etc/passwd"},
        )
        self.assertEqual(response.status_code, 400)

    @patch("translate_video.api.routes.pipeline.asyncio.to_thread", new_callable=AsyncMock)
    def test_running_project_removed_from_registry_after_completion(self, mock_thread):
        """После завершения задачи проект удаляется из реестра запущенных."""
        self.store.create_project("dummy.mp4", project_id="cleanup_test")
        self.client.post("/api/v1/projects/cleanup_test/run", json={"provider": "fake"})
        # TestClient выполняет background tasks синхронно
        self.assertNotIn("cleanup_test", _running_projects)
