"""Регрессионные тесты — покрывают конкретные баги, которые были зафиксированы.

Каждый тест привязан к номеру ветки TVIDEO-XXX и описывает поведение до/после фикса.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from translate_video.api.main import app
from translate_video.api.routes.pipeline import _running_projects
from translate_video.api.routes.projects import get_store
from translate_video.core.schemas import ArtifactKind, Stage
from translate_video.core.store import ProjectStore

# Путь к скрипту bump_version.py (относительно корня проекта)
BUMP_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "bump_version.py"


# ─── TVIDEO-021: абсолютный WORK_ROOT ────────────────────────────────────────

class TestAbsoluteWorkRoot(unittest.TestCase):
    """TVIDEO-021: get_store() должен возвращать store с абсолютным root.

    Баг: WORK_ROOT="runs" (относительный) → store.root = Path("runs") →
    artifact.path сохранялся как относительный → при следующем этапе:
    work_dir / artifact.path = "runs/project-id/runs/project-id/file" → FileNotFoundError.
    """

    def test_get_store_returns_absolute_root(self):
        """get_store() должен возвращать store с абсолютным root."""
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                os.makedirs("runs", exist_ok=True)
                with patch.dict(os.environ, {"WORK_ROOT": "runs"}):
                    store = get_store()
                    self.assertTrue(
                        store.root.is_absolute(),
                        f"store.root должен быть абсолютным, получили: {store.root}"
                    )
            finally:
                os.chdir(old_cwd)

    def test_artifact_path_is_relative_and_resolvable(self):
        """Артефакт сохраняется как относительный путь и восстанавливается через work_dir.

        Регрессия: при относительном store.root путь к артефакту дублировал work_dir.
        Корректно: artifact.path = 'source_audio.wav', work_dir / path = существующий файл.
        """
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "runs")
            project = store.create_project("video.mp4", project_id="test-artifact-path")

            audio_file = project.work_dir / "source_audio.wav"
            audio_file.write_bytes(b"fake-wav-data")

            record = store.add_artifact(
                project, ArtifactKind.SOURCE_AUDIO, audio_file,
                stage=Stage.EXTRACT_AUDIO, content_type="audio/wav",
            )
            store.save_project(project)

            # Путь должен быть относительным (без абсолютного prefix)
            self.assertFalse(
                record.path.startswith("/"),
                f"artifact.path должен быть относительным: {record.path}"
            )
            # Не должен содержать дублирования work_dir
            self.assertNotIn(
                "runs",
                record.path,
                f"artifact.path не должен включать 'runs/': {record.path}"
            )
            # Восстановленный путь должен существовать
            restored = project.work_dir / record.path
            self.assertTrue(
                restored.exists(),
                f"Восстановленный путь не существует: {restored}"
            )

    def test_transcribe_stage_finds_audio_after_extract(self):
        """TranscribeStage находит source_audio.wav созданный ExtractAudioStage.

        Симулирует полный цикл: сохранение артефакта → load_project → поиск пути.
        Регрессия: при relative root путь восстанавливался неверно.
        """
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "runs")
            project = store.create_project("input.mp4", project_id="test-stage-path")

            # Симулируем ExtractAudioStage: создаём файл и артефакт
            audio_file = project.work_dir / "source_audio.wav"
            audio_file.write_bytes(b"fake-wav")
            store.add_artifact(
                project, ArtifactKind.SOURCE_AUDIO, audio_file,
                stage=Stage.EXTRACT_AUDIO, content_type="audio/wav",
            )
            store.save_project(project)

            # Перезагружаем (как PipelineRunner)
            reloaded = store.load_project(project.work_dir)

            # TranscribeStage: ищем SOURCE_AUDIO и строим путь
            source_audio = next(
                (r for r in reloaded.artifact_records if r.kind == ArtifactKind.SOURCE_AUDIO),
                None,
            )
            self.assertIsNotNone(source_audio, "Артефакт SOURCE_AUDIO должен быть найден")

            audio_path = reloaded.work_dir / source_audio.path
            self.assertTrue(
                audio_path.exists(),
                f"TranscribeStage не найдёт файл: {audio_path}"
            )


# ─── TVIDEO-019/020: провайдер по умолчанию ─────────────────────────────────

class TestDefaultProviderIsLegacy(unittest.TestCase):
    """TVIDEO-019/020: провайдер по умолчанию — 'legacy', не 'fake'.

    Баг: RunPipelineRequest.provider = "fake" → пустой перевод «Пример речи».
    """

    def test_run_pipeline_request_default_provider_is_legacy(self):
        """RunPipelineRequest без явного provider должен использовать 'legacy'."""
        from translate_video.api.routes.pipeline import RunPipelineRequest
        req = RunPipelineRequest()
        self.assertEqual(
            req.provider, "legacy",
            f"Дефолтный провайдер должен быть 'legacy', получили '{req.provider}'"
        )

    def test_run_without_provider_field_uses_legacy(self):
        """POST /run без поля provider в JSON-теле использует 'legacy'."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "runs")
            app.dependency_overrides[get_store] = lambda: store
            _running_projects.clear()
            store.create_project("dummy.mp4", project_id="legacy_test")
            try:
                with patch(
                    "translate_video.api.routes.pipeline.asyncio.to_thread",
                    new_callable=AsyncMock,
                ):
                    client = TestClient(app)
                    resp = client.post(
                        "/api/v1/projects/legacy_test/run",
                        json={},  # provider не указан
                    )
                self.assertEqual(resp.status_code, 200)
            finally:
                app.dependency_overrides.clear()
                _running_projects.clear()


# ─── TVIDEO-021: bump_version.py защита от битого VERSION ────────────────────

class TestBumpVersionGuards(unittest.TestCase):
    """TVIDEO-021: bump_version.py должен падать с понятной ошибкой при битом VERSION."""

    def _run_bump(self, version_content: str, bump_arg: str) -> tuple[bool, str]:
        """Запускает bump_version с заданным VERSION-файлом в изолированном tmpdir."""
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text(version_content, encoding="utf-8")
            (root / "pyproject.toml").write_text('[project]\nversion = "0.0.0"\n', encoding="utf-8")
            src = root / "src" / "translate_video"
            src.mkdir(parents=True)
            (src / "__init__.py").write_text('__version__ = "0.0.0"\n', encoding="utf-8")
            (root / "change.log").write_text("# Журнал Изменений\n", encoding="utf-8")
            # Копируем скрипт в ожидаемую структуру (ROOT = script.parent.parent)
            scripts_dir = root / "scripts"
            scripts_dir.mkdir()
            import shutil
            shutil.copy(BUMP_SCRIPT, scripts_dir / "bump_version.py")

            result = subprocess.run(
                ["python3", str(scripts_dir / "bump_version.py"), bump_arg],
                capture_output=True, text=True, cwd=tmp,
            )
            return result.returncode == 0, result.stdout + result.stderr

    def test_keyword_as_version_raises_error(self):
        """VERSION='patch' вместо X.Y.Z → понятная ошибка с подсказкой."""
        ok, output = self._run_bump("patch\n", "patch")
        self.assertFalse(ok, "Должна быть ошибка при VERSION='patch'")
        self.assertIn("X.Y.Z", output, f"Вывод: {output}")

    def test_conflict_markers_raise_error(self):
        """VERSION с git-конфликт-маркерами → понятная ошибка."""
        ok, output = self._run_bump("<<<<<<< HEAD\n1.0.0\n=======\n1.1.0\n>>>>>>>\n", "patch")
        self.assertFalse(ok, "Должна быть ошибка при конфликт-маркерах")
        self.assertTrue(
            "конфликт" in output.lower() or "conflict" in output.lower(),
            f"Ошибка должна упомянуть конфликт: {output}"
        )

    def test_major_bump_resets_minor_and_patch(self):
        """1.2.3 → major → 2.0.0."""
        ok, output = self._run_bump("1.2.3\n", "major")
        self.assertTrue(ok, f"Bump major: {output}")
        self.assertIn("2.0.0", output)

    def test_minor_bump_resets_patch(self):
        """1.2.3 → minor → 1.3.0."""
        ok, output = self._run_bump("1.2.3\n", "minor")
        self.assertTrue(ok, f"Bump minor: {output}")
        self.assertIn("1.3.0", output)

    def test_patch_bump(self):
        """1.2.3 → patch → 1.2.4."""
        ok, output = self._run_bump("1.2.3\n", "patch")
        self.assertTrue(ok, f"Bump patch: {output}")
        self.assertIn("1.2.4", output)

    def test_explicit_version(self):
        """Явная версия 2.0.0 записывается напрямую."""
        ok, output = self._run_bump("1.2.3\n", "2.0.0")
        self.assertTrue(ok, f"Явная версия: {output}")
        self.assertIn("2.0.0", output)

    def test_invalid_explicit_version_raises_error(self):
        """Некорректная версия 'not-a-version' → ошибка."""
        ok, _ = self._run_bump("1.2.3\n", "not-a-version")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
