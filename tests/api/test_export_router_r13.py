"""R13-И5 тесты: Export Router (ADR-001 Фаза 1).

Используем FastAPI dependency_overrides для мокирования get_store,
как это принято в остальных тестах проекта (test_projects_r3.py).
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from translate_video.api.routes.export import export_router
from translate_video.api.routes.projects import get_store


class TestExportRouterStructure(unittest.TestCase):
    """Структурные тесты export router."""

    def test_router_has_4_routes(self):
        """export_router содержит ровно 4 endpoint."""
        self.assertEqual(len(export_router.routes), 4)

    def test_router_paths(self):
        """Все 4 пути зарегистрированы."""
        paths = {r.path for r in export_router.routes}
        self.assertIn("/{project_id}/export/zip", paths)
        self.assertIn("/{project_id}/export/subtitles-all", paths)
        self.assertIn("/{project_id}/export/script", paths)
        self.assertIn("/{project_id}/export-audio", paths)

    def test_router_tags(self):
        """Router имеет tag 'Export'."""
        self.assertEqual(export_router.tags, ["Export"])


class TestExportRouterEndpoints(unittest.TestCase):
    """Интеграционные тесты через TestClient + dependency_overrides."""

    def _make_app_with_store(self, mock_store) -> TestClient:
        """Создаём FastAPI app с моком store."""
        app = FastAPI()
        app.include_router(export_router, prefix="/api/v1/projects")
        app.dependency_overrides[get_store] = lambda: mock_store
        return TestClient(app, raise_server_exceptions=False)

    def test_export_zip_404_nonexistent(self):
        """GET /export/zip → 404 для несуществующего проекта."""
        mock_store = MagicMock()
        mock_store.load_project.side_effect = FileNotFoundError()
        client = self._make_app_with_store(mock_store)
        r = client.get("/api/v1/projects/nonexistent/export/zip")
        self.assertEqual(r.status_code, 404)

    def test_export_subtitles_404_nonexistent(self):
        """GET /export/subtitles-all → 404 для несуществующего проекта."""
        mock_store = MagicMock()
        mock_store.load_project.side_effect = FileNotFoundError()
        client = self._make_app_with_store(mock_store)
        r = client.get("/api/v1/projects/nonexistent/export/subtitles-all")
        self.assertEqual(r.status_code, 404)

    def test_export_subtitles_404_no_segments(self):
        """GET /export/subtitles-all → 404 если нет сегментов."""
        mock_project = MagicMock()
        mock_project.segments = []
        mock_store = MagicMock()
        mock_store.load_project.return_value = mock_project
        client = self._make_app_with_store(mock_store)
        r = client.get("/api/v1/projects/test-project/export/subtitles-all")
        self.assertEqual(r.status_code, 404)
        self.assertIn("Субтитры", r.json()["detail"])

    def test_export_script_404_no_segments(self):
        """GET /export/script → 404 если нет сегментов."""
        mock_project = MagicMock()
        mock_project.segments = []
        mock_store = MagicMock()
        mock_store.load_project.return_value = mock_project
        client = self._make_app_with_store(mock_store)
        r = client.get("/api/v1/projects/test-project/export/script")
        self.assertEqual(r.status_code, 404)

    def test_export_audio_404_no_tts(self):
        """GET /export-audio → 404 если нет TTS директории."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_project = MagicMock()
            mock_project.work_dir = Path(tmpdir)
            mock_store = MagicMock()
            mock_store.load_project.return_value = mock_project
            client = self._make_app_with_store(mock_store)
            r = client.get("/api/v1/projects/test-project/export-audio")
            self.assertEqual(r.status_code, 404)
            self.assertIn("TTS", r.json()["detail"])

    def test_export_zip_returns_zip_content_type(self):
        """GET /export/zip → 200 и application/zip content-type."""
        mock_project = MagicMock()
        mock_project.segments = []
        mock_project.to_dict.return_value = {"id": "test-project"}
        mock_store = MagicMock()
        mock_store.load_project.return_value = mock_project
        client = self._make_app_with_store(mock_store)
        r = client.get("/api/v1/projects/test-project/export/zip")
        self.assertEqual(r.status_code, 200)
        self.assertIn("zip", r.headers.get("content-type", ""))

    def test_export_zip_has_v2_header(self):
        """GET /export/zip содержит X-Export-Router: v2 header."""
        mock_project = MagicMock()
        mock_project.segments = []
        mock_project.to_dict.return_value = {"id": "test-project"}
        mock_store = MagicMock()
        mock_store.load_project.return_value = mock_project
        client = self._make_app_with_store(mock_store)
        r = client.get("/api/v1/projects/test-project/export/zip")
        self.assertEqual(r.headers.get("x-export-router"), "v2")

    def test_export_script_txt_format(self):
        """GET /export/script?format=txt → 200 text/plain с переводом."""
        seg = MagicMock()
        seg.start = 0.0
        seg.end = 5.0
        seg.source_text = "Hello world"
        seg.translated_text = "Привет мир"
        mock_project = MagicMock()
        mock_project.segments = [seg]
        mock_project.id = "test-project"
        mock_store = MagicMock()
        mock_store.load_project.return_value = mock_project
        client = self._make_app_with_store(mock_store)
        r = client.get("/api/v1/projects/test-project/export/script?format=txt")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/plain", r.headers.get("content-type", ""))
        self.assertIn("Привет мир", r.text)

    def test_export_script_tsv_format(self):
        """GET /export/script?format=tsv → 200 TSV с табами."""
        seg = MagicMock()
        seg.start = 0.0
        seg.end = 5.0
        seg.source_text = "Hello"
        seg.translated_text = "Привет"
        mock_project = MagicMock()
        mock_project.segments = [seg]
        mock_store = MagicMock()
        mock_store.load_project.return_value = mock_project
        client = self._make_app_with_store(mock_store)
        r = client.get("/api/v1/projects/test-project/export/script?format=tsv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Привет", r.text)
        self.assertIn("\t", r.text)

    def test_export_script_unknown_format_defaults_to_txt(self):
        """GET /export/script?format=unknown → 200 (fallback to txt)."""
        seg = MagicMock()
        seg.start = 0.0
        seg.end = 5.0
        seg.source_text = "Hi"
        seg.translated_text = "Привет"
        mock_project = MagicMock()
        mock_project.segments = [seg]
        mock_project.id = "test"
        mock_store = MagicMock()
        mock_store.load_project.return_value = mock_project
        client = self._make_app_with_store(mock_store)
        r = client.get("/api/v1/projects/test/export/script?format=unknown")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
