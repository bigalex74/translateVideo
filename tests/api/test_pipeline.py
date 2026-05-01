import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from translate_video.api.main import app
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

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()

    def test_run_pipeline_background(self):
        """Запуск пайплайна должен возвращать 200 сразу (background task)."""
        project = self.store.create_project("dummy.mp4", project_id="run_test")
        response = self.client.post("/api/v1/projects/run_test/run", json={"provider": "fake"})
        self.assertEqual(response.status_code, 200)
        time.sleep(0.5)

    def test_run_pipeline_not_found(self):
        """Запуск несуществующего проекта возвращает 404."""
        response = self.client.post("/api/v1/projects/missing/run", json={"provider": "fake"})
        self.assertEqual(response.status_code, 404)

    def test_run_pipeline_rejects_path_traversal_id(self):
        """Запуск пайплайна не должен принимать небезопасный ID."""

        response = self.client.post("/api/v1/projects/%2E%2E/run", json={"provider": "fake"})

        self.assertEqual(response.status_code, 400)

    @patch("translate_video.api.routes.pipeline.notify_webhook")
    def test_run_pipeline_with_webhook(self, mock_notify):
        project = self.store.create_project("dummy.mp4", project_id="webhook_test")
        self.client.post(
            "/api/v1/projects/webhook_test/run", 
            json={"provider": "fake"},
            headers={"X-Webhook-Url": "http://example.com/webhook"}
        )
        time.sleep(0.5)
        mock_notify.assert_called_once()

    @patch("translate_video.api.routes.pipeline.PipelineRunner.run")
    @patch("translate_video.api.routes.pipeline.notify_webhook")
    def test_run_pipeline_webhook_on_error(self, mock_notify, mock_run):
        mock_run.side_effect = Exception("Pipeline failed")
        project = self.store.create_project("dummy.mp4", project_id="webhook_err_test")
        self.client.post(
            "/api/v1/projects/webhook_err_test/run", 
            json={"provider": "fake"},
            headers={"X-Webhook-Url": "http://example.com/webhook"}
        )
        time.sleep(0.5)
        mock_notify.assert_called_once()
