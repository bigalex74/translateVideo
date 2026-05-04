"""Тесты batch run endpoint (TVIDEO-137)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _make_app():
    """Создать FastAPI app без реального файлового хранилища."""
    from translate_video.api.main import app
    return app


class BatchRunEndpointTest(unittest.TestCase):
    """POST /api/v1/projects/batch/run."""

    def setUp(self):
        """Создаём тест-клиент с моком хранилища."""
        from translate_video.api.main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_batch_run_returns_queued_items(self):
        """Endpoint ставит проекты в очередь и возвращает BatchRunResponse."""
        import tempfile
        from pathlib import Path
        from translate_video.core.store import ProjectStore
        from translate_video.core.schemas import VideoProject
        from translate_video.core.config import PipelineConfig
        from translate_video.api.routes.projects import get_store

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProjectStore(Path(tmpdir))
            # Создаём фиктивный проект
            p = VideoProject(
                input_video=Path("video.mp4"),
                work_dir=Path(tmpdir) / "proj-batch-1",
                config=PipelineConfig(source_language="en", target_language="ru"),
            )
            (Path(tmpdir) / "proj-batch-1").mkdir()
            store.save_project(p)

            from translate_video.api.main import app
            app.dependency_overrides[get_store] = lambda: store

            with patch("translate_video.api.routes.pipeline.run_pipeline_task"):
                resp = self.client.post(
                    "/api/v1/projects/batch/run",
                    json={"project_ids": ["proj-batch-1"], "provider": "fake"},
                )

            app.dependency_overrides.clear()

        # Endpoint должен вернуть 200 с queued=1
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("queued", data)
        self.assertIn("items", data)

    def test_batch_run_rejects_more_than_50(self):
        """Endpoint отклоняет запрос с >50 проектами (новый лимит)."""
        from translate_video.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
        ids = [f"proj-{i}" for i in range(51)]
        resp = client.post(
            "/api/v1/projects/batch/run",
            json={"project_ids": ids, "provider": "fake"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("50", resp.json()["detail"])

    def test_batch_run_skips_invalid_ids(self):
        """Endpoint пропускает некорректные ID с reason=invalid_project_id."""
        import tempfile
        from pathlib import Path
        from translate_video.core.store import ProjectStore
        from translate_video.api.routes.projects import get_store
        from translate_video.api.main import app

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProjectStore(Path(tmpdir))
            app.dependency_overrides[get_store] = lambda: store

            resp = TestClient(app, raise_server_exceptions=False).post(
                "/api/v1/projects/batch/run",
                json={"project_ids": ["../../../etc/passwd"], "provider": "fake"},
            )
            app.dependency_overrides.clear()

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["skipped"], 1)
        self.assertEqual(data["items"][0]["reason"], "invalid_project_id")

    def test_batch_run_skips_already_running(self):
        """Endpoint пропускает проекты, которые уже запущены."""
        import tempfile
        from pathlib import Path
        from translate_video.core.store import ProjectStore
        from translate_video.api.routes.projects import get_store
        from translate_video.api import routes as _routes
        from translate_video.api.routes import pipeline as _pl
        from translate_video.api.main import app

        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProjectStore(Path(tmpdir))
            app.dependency_overrides[get_store] = lambda: store

            # Симулируем запущенный проект
            _pl._running_projects.add("running-proj")
            try:
                resp = TestClient(app, raise_server_exceptions=False).post(
                    "/api/v1/projects/batch/run",
                    json={"project_ids": ["running-proj"], "provider": "fake"},
                )
            finally:
                _pl._running_projects.discard("running-proj")
                app.dependency_overrides.clear()

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["skipped"], 1)
        self.assertEqual(data["items"][0]["reason"], "already_running")


if __name__ == "__main__":
    unittest.main()
