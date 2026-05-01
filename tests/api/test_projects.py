import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from translate_video.api.main import app
from translate_video.core.store import ProjectStore
from translate_video.api.routes.projects import get_store

class APIProjectsTest(TestCase):
    """Тесты API маршрутов управления проектами."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_root = Path(self.temp_dir.name) / "runs"
        self.store = ProjectStore(self.work_root)
        
        app.dependency_overrides[get_store] = lambda: self.store
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()

    def test_get_store(self):
        """Проверка дефолтной зависимости get_store."""
        store = get_store()
        self.assertIsNotNone(store)

    def test_create_project(self):
        """Проверка создания проекта через API."""
        response = self.client.post("/api/v1/projects", json={
            "input_video": "dummy.mp4",
            "project_id": "api_test",
            "config": {"source_language": "en"}
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["project_id"], "api_test")
        self.assertEqual(data["status"], "created")

    @patch.object(ProjectStore, "create_project")
    def test_create_project_exception(self, mock_create):
        """Проверка 400 при ошибке создания."""
        mock_create.side_effect = Exception("Test Error")
        response = self.client.post("/api/v1/projects", json={"input_video": "dummy.mp4"})
        self.assertEqual(response.status_code, 400)

    @patch.object(ProjectStore, "create_project")
    def test_upload_project_exception(self, mock_create):
        """Проверка 400 при ошибке загрузки файла."""
        mock_create.side_effect = Exception("Upload Error")
        files = {"file": ("test.mp4", b"data", "video/mp4")}
        response = self.client.post("/api/v1/projects/upload", files=files)
        self.assertEqual(response.status_code, 400)

    def test_get_project_status(self):
        """Проверка получения статуса."""
        self.store.create_project("dummy.mp4", project_id="status_test")
        response = self.client.get("/api/v1/projects/status_test")
        self.assertEqual(response.status_code, 200)

    def test_get_project_not_found(self):
        """Проверка 404 для несуществующего проекта."""
        response = self.client.get("/api/v1/projects/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_get_project_rejects_path_traversal_id(self):
        """Получение проекта не должно принимать небезопасный ID."""

        response = self.client.get("/api/v1/projects/%2E%2E")

        self.assertEqual(response.status_code, 400)

    def test_get_artifacts(self):
        """Проверка получения артефактов."""
        self.store.create_project("dummy.mp4", project_id="artifacts_test")
        response = self.client.get("/api/v1/projects/artifacts_test/artifacts")
        self.assertEqual(response.status_code, 200)

    def test_get_artifacts_rejects_path_traversal_id(self):
        """Получение артефактов не должно принимать небезопасный ID."""

        response = self.client.get("/api/v1/projects/%2E%2E/artifacts")

        self.assertEqual(response.status_code, 400)

    def test_upload_project(self):
        """Проверка загрузки файла через multipart/form-data."""
        files = {"file": ("test_vid.mp4", b"fake", "video/mp4")}
        data = {"project_id": "upload_test"}
        response = self.client.post("/api/v1/projects/upload", files=files, data=data)
        self.assertEqual(response.status_code, 200)
        project_dir = self.work_root / "upload_test"
        self.assertTrue((project_dir / "input.mp4").exists())
        self.assertEqual((project_dir / "input.mp4").read_bytes(), b"fake")
        self.assertFalse((self.work_root.parent / "test_vid.mp4").exists())

    def test_upload_rejects_path_traversal_project_id(self):
        """Загрузка должна запрещать project_id с выходом из корня."""

        files = {"file": ("test.mp4", b"fake", "video/mp4")}
        response = self.client.post(
            "/api/v1/projects/upload",
            files=files,
            data={"project_id": "../evil"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse((self.work_root.parent / "evil").exists())

    def test_upload_sanitizes_filename(self):
        """Имя загруженного файла не должно создавать вложенные пути."""

        files = {"file": ("../nested/test.mp4", b"fake", "video/mp4")}
        response = self.client.post("/api/v1/projects/upload", files=files)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["project_id"], "test")
        self.assertTrue((self.work_root / "test" / "input.mp4").exists())
