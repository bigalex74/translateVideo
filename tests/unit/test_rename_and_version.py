"""Тесты для /api/version и PATCH /projects/{id}/rename (В10, О1).

QA Monitor: coverage hotfix — покрываем новые endpoints iter 1 Round 5.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class ApiVersionEndpointTest(unittest.TestCase):
    """В10: GET /api/version — лёгкий endpoint версии."""

    def setUp(self):
        from translate_video.api.main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_version_returns_ok(self):
        """GET /api/version → 200 с version+status+app."""
        resp = self.client.get("/api/version")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("version", data)
        self.assertEqual(data["status"], "ok")
        self.assertIn("app", data)

    def test_version_matches_package(self):
        """Версия из /api/version совпадает с __version__ пакета."""
        import translate_video
        resp = self.client.get("/api/version")
        self.assertEqual(resp.json()["version"], translate_video.__version__)


class RenameProjectEndpointTest(unittest.TestCase):
    """О1: PATCH /api/v1/projects/{id}/rename — переименование проекта."""

    def _make_project(self, work_root: Path, project_id: str):
        """Создаём минимальный project.json в work_root/project_id/."""
        from translate_video.core.schemas import VideoProject, PipelineConfig
        proj_dir = work_root / project_id
        proj_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("subtitles", "tts", "output"):
            (proj_dir / sub).mkdir(exist_ok=True)
        proj = VideoProject(
            input_video=proj_dir / "video.mp4",
            work_dir=proj_dir,
            config=PipelineConfig(),
            id=project_id,
        )
        (proj_dir / "project.json").write_text(
            json.dumps(proj.to_dict(), default=str), encoding="utf-8"
        )
        (proj_dir / "settings.json").write_text(
            json.dumps(proj.config.to_dict(), default=str), encoding="utf-8"
        )
        return proj_dir

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self._work_root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_rename_sets_display_name(self):
        """PATCH /rename → display_name сохраняется в project.json."""
        from translate_video.api.main import app
        from translate_video.api.routes.projects import get_store
        from translate_video.core.store import ProjectStore

        proj_id = "test_proj_rename01"
        self._make_project(self._work_root, proj_id)
        store = ProjectStore(self._work_root)

        with TestClient(app, raise_server_exceptions=False) as client:
            app.dependency_overrides[get_store] = lambda: store
            resp = client.patch(
                f"/api/v1/projects/{proj_id}/rename",
                json={"display_name": "Мой проект"},
            )
            app.dependency_overrides.clear()

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["display_name"], "Мой проект")
        self.assertEqual(data["status"], "renamed")

        # Проверяем что сохранилось в JSON
        saved = json.loads((self._work_root / proj_id / "project.json").read_text())
        self.assertEqual(saved["display_name"], "Мой проект")

    def test_rename_empty_name_rejected(self):
        """PATCH /rename с пустым именем → 422."""
        from translate_video.api.main import app
        from translate_video.api.routes.projects import get_store
        from translate_video.core.store import ProjectStore

        proj_id = "test_proj_rename02"
        self._make_project(self._work_root, proj_id)
        store = ProjectStore(self._work_root)

        with TestClient(app, raise_server_exceptions=False) as client:
            app.dependency_overrides[get_store] = lambda: store
            resp = client.patch(
                f"/api/v1/projects/{proj_id}/rename",
                json={"display_name": ""},
            )
            app.dependency_overrides.clear()

        self.assertIn(resp.status_code, [400, 422])

    def test_rename_unknown_project_404(self):
        """PATCH /rename на несуществующий проект → 404."""
        from translate_video.api.main import app
        from translate_video.api.routes.projects import get_store
        from translate_video.core.store import ProjectStore

        store = ProjectStore(self._work_root)

        with TestClient(app, raise_server_exceptions=False) as client:
            app.dependency_overrides[get_store] = lambda: store
            resp = client.patch(
                "/api/v1/projects/nonexistent_xyz/rename",
                json={"display_name": "Test"},
            )
            app.dependency_overrides.clear()

        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
