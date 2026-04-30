"""E2E-тест полного пайплайна с fake-провайдерами и реальным видеофайлом.

Тест проверяет, что CLI-команды `preflight`, `init`, `run`, `status`, `artifacts`,
`config`, `export-srt`, `export-vtt`, `timing-report` и `review` работают корректно
от начала до конца с синтетическим видеофайлом.

Тестовое видео создаётся скриптом tests/e2e/fixtures/create_test_video.py.
Запуск одного теста занимает <1 сек (fake-провайдеры, нет тяжёлых моделей).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

# Добавляем src в путь для импорта пакета
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from translate_video.cli import main as cli_main
from translate_video.core.preflight import run_preflight

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_VIDEO = FIXTURES_DIR / "sample_en.mp4"


def _run_cli(*args: str) -> dict:
    """Запустить CLI-команду и вернуть распарсенный JSON-вывод."""

    buf = StringIO()
    exit_code = cli_main(list(args), stdout=buf)
    assert exit_code == 0, f"CLI завершился с кодом {exit_code}"
    output = buf.getvalue().strip()
    return json.loads(output) if output else {}


class E2EVideoFixtureTest(unittest.TestCase):
    """Проверяет наличие и корректность тестового видеофайла."""

    def test_sample_video_exists(self):
        """Тестовый видеофайл должен существовать перед запуском e2e."""

        if not SAMPLE_VIDEO.exists():
            self.skipTest(
                f"Тестовое видео не найдено: {SAMPLE_VIDEO}\n"
                "Создайте его командой:\n"
                "  python3 tests/e2e/fixtures/create_test_video.py"
            )
        self.assertTrue(SAMPLE_VIDEO.is_file())
        self.assertGreater(SAMPLE_VIDEO.stat().st_size, 0)

    def test_sample_video_size_is_reasonable(self):
        """Тестовое видео должно быть не меньше 1 КБ и не больше 50 МБ."""

        if not SAMPLE_VIDEO.exists():
            self.skipTest("Тестовое видео отсутствует")
        size = SAMPLE_VIDEO.stat().st_size
        self.assertGreater(size, 1024, "Файл слишком мал — вероятно повреждён")
        self.assertLess(size, 50 * 1024 * 1024, "Файл слишком большой для тестового")


class E2EPreflightTest(unittest.TestCase):
    """Проверяет preflight-анализ реального видеофайла."""

    def setUp(self):
        if not SAMPLE_VIDEO.exists():
            self.skipTest("Тестовое видео отсутствует")

    def test_preflight_fake_provider_passes(self):
        """Preflight для fake-провайдера должен пройти при наличии файла."""

        report = run_preflight(SAMPLE_VIDEO, provider="fake")
        self.assertTrue(
            report.ok,
            f"Preflight упал: {[c.message for c in report.checks if not c.ok]}",
        )
        self.assertEqual(report.provider, "fake")

    def test_preflight_cli_returns_json(self):
        """CLI preflight должен вернуть корректный JSON с полем ok."""

        result = _run_cli("preflight", str(SAMPLE_VIDEO), "--provider", "fake")
        self.assertIn("ok", result)
        self.assertIn("checks", result)
        self.assertTrue(result["ok"])
        self.assertIsInstance(result["checks"], list)
        self.assertGreater(len(result["checks"]), 0)


class E2EFullPipelineTest(unittest.TestCase):
    """Проверяет полный цикл: init → run → status → artifacts → config."""

    def setUp(self):
        if not SAMPLE_VIDEO.exists():
            self.skipTest("Тестовое видео отсутствует")
        self._tmpdir = tempfile.TemporaryDirectory()
        self.work_root = Path(self._tmpdir.name) / "runs"

    def tearDown(self):
        self._tmpdir.cleanup()

    def _cli(self, *args: str) -> dict:
        return _run_cli(*args)

    def test_init_creates_project(self):
        """Команда init должна создать проект и вернуть его метаданные."""

        result = self._cli(
            "init", str(SAMPLE_VIDEO),
            "--work-root", str(self.work_root),
            "--project-id", "e2e-init-test",
            "--source-language", "en",
            "--target-language", "ru",
        )
        self.assertEqual(result["project_id"], "e2e-init-test")
        self.assertEqual(result["status"], "created")
        self.assertIn("work_dir", result)

        work_dir = Path(result["work_dir"])
        self.assertTrue(work_dir.exists(), "Рабочая папка проекта должна быть создана")
        self.assertTrue((work_dir / "project.json").exists())
        self.assertTrue((work_dir / "settings.json").exists())

    def test_run_with_fake_provider_completes(self):
        """Команда run с fake-провайдером должна завершиться со статусом completed."""

        result = self._cli(
            "run", str(SAMPLE_VIDEO),
            "--work-root", str(self.work_root),
            "--project-id", "e2e-run-test",
            "--provider", "fake",
        )
        self.assertEqual(result["status"], "completed")
        self.assertIn("runs", result)
        stage_runs = result["runs"]
        self.assertGreater(len(stage_runs), 0)

        failed = [r for r in stage_runs if r["status"] != "completed"]
        self.assertEqual(failed, [], f"Есть упавшие этапы: {failed}")

    def test_run_creates_output_artifact(self):
        """После run в папке проекта должен появиться output/translated.mp4."""

        result = self._cli(
            "run", str(SAMPLE_VIDEO),
            "--work-root", str(self.work_root),
            "--project-id", "e2e-artifact-test",
            "--provider", "fake",
        )
        work_dir = Path(result["work_dir"])
        output_video = work_dir / "output" / "translated.mp4"
        self.assertTrue(output_video.exists(), f"Выходное видео не найдено: {output_video}")

    def test_status_after_run(self):
        """Команда status должна вернуть completed после run."""

        run_result = self._cli(
            "run", str(SAMPLE_VIDEO),
            "--work-root", str(self.work_root),
            "--project-id", "e2e-status-test",
            "--provider", "fake",
        )
        status_result = self._cli("status", run_result["work_dir"])
        self.assertEqual(status_result["status"], "completed")
        self.assertIn("stage_runs", status_result)

    def test_artifacts_command(self):
        """Команда artifacts должна вернуть список артефактов проекта."""

        run_result = self._cli(
            "run", str(SAMPLE_VIDEO),
            "--work-root", str(self.work_root),
            "--project-id", "e2e-artifacts-test",
            "--provider", "fake",
        )
        art_result = self._cli("artifacts", run_result["work_dir"])
        self.assertIn("artifacts", art_result)
        self.assertIsInstance(art_result["artifacts"], list)
        self.assertGreater(len(art_result["artifacts"]), 0)

        kinds = [a["kind"] for a in art_result["artifacts"]]
        self.assertIn("output_video", kinds)

    def test_config_command_shows_pipeline_settings(self):
        """Команда config должна вернуть настройки пайплайна проекта."""

        run_result = self._cli(
            "run", str(SAMPLE_VIDEO),
            "--work-root", str(self.work_root),
            "--project-id", "e2e-config-test",
            "--source-language", "en",
            "--target-language", "ru",
            "--provider", "fake",
        )
        config_result = self._cli("config", run_result["work_dir"])
        self.assertEqual(config_result["source_language"], "en")
        self.assertEqual(config_result["target_language"], "ru")
        self.assertIn("translation_mode", config_result)
        self.assertIn("quality_gate", config_result)

    def test_run_without_video_raises_error(self):
        """run без input_video и без --work-dir должен завершиться с ошибкой."""

        with self.assertRaises(SystemExit):
            cli_main(["run", "--work-root", str(self.work_root)])

    def test_preflight_nonexistent_file_fails(self):
        """preflight на несуществующий файл должен вернуть ok=False."""

        report = run_preflight("/nonexistent/video.mp4", provider="fake")
        self.assertFalse(report.ok)
        failed_checks = [c for c in report.checks if not c.ok]
        self.assertGreater(len(failed_checks), 0)



class E2EExportCommandsTest(unittest.TestCase):
    """Проверяет команды экспорта артефактов после полного run."""

    def setUp(self):
        if not SAMPLE_VIDEO.exists():
            self.skipTest("Тестовое видео отсутствует")
        self._tmpdir = tempfile.TemporaryDirectory()
        self.work_root = Path(self._tmpdir.name) / "runs"
        # Запускаем пайплайн один раз, переиспользуем work_dir во всех тестах
        buf = StringIO()
        cli_main(
            [
                "run", str(SAMPLE_VIDEO),
                "--work-root", str(self.work_root),
                "--project-id", "e2e-export",
                "--provider", "fake",
            ],
            stdout=buf,
        )
        self.run_result = json.loads(buf.getvalue())
        self.work_dir = self.run_result["work_dir"]

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_export_srt_returns_path(self):
        """export-srt должен вернуть путь к SRT-файлу."""
        result = _run_cli("export-srt", self.work_dir)
        self.assertEqual(result["format"], "srt")
        self.assertIn(".srt", result["path"])

    def test_export_srt_creates_file(self):
        """export-srt должен создать файл на диске."""
        result = _run_cli("export-srt", self.work_dir)
        srt_path = Path(result["path"])
        self.assertTrue(srt_path.exists(), f"SRT-файл не найден: {srt_path}")

    def test_export_srt_file_has_webvtt_check(self):
        """SRT-файл не должен начинаться с WEBVTT (это формат VTT)."""
        result = _run_cli("export-srt", self.work_dir)
        content = Path(result["path"]).read_text(encoding="utf-8")
        self.assertFalse(content.startswith("WEBVTT"))

    def test_export_vtt_returns_path(self):
        """export-vtt должен вернуть путь к VTT-файлу."""
        result = _run_cli("export-vtt", self.work_dir)
        self.assertEqual(result["format"], "vtt")
        self.assertIn(".vtt", result["path"])

    def test_export_vtt_creates_file(self):
        """export-vtt должен создать файл на диске."""
        result = _run_cli("export-vtt", self.work_dir)
        vtt_path = Path(result["path"])
        self.assertTrue(vtt_path.exists(), f"VTT-файл не найден: {vtt_path}")

    def test_export_vtt_starts_with_webvtt(self):
        """VTT-файл должен начинаться с заголовка WEBVTT."""
        result = _run_cli("export-vtt", self.work_dir)
        content = Path(result["path"]).read_text(encoding="utf-8")
        self.assertTrue(content.startswith("WEBVTT"))

    def test_timing_report_structure(self):
        """timing-report должен вернуть JSON с полями счётчиков."""
        result = _run_cli("timing-report", self.work_dir)
        for field in ("total_segments", "translated_count", "empty_count",
                      "total_duration", "segments"):
            self.assertIn(field, result)

    def test_timing_report_segment_count_matches(self):
        """Число записей в segments должно совпадать с total_segments."""
        result = _run_cli("timing-report", self.work_dir)
        self.assertEqual(len(result["segments"]), result["total_segments"])

    def test_review_structure(self):
        """review должен вернуть JSON с полями ревью."""
        result = _run_cli("review", self.work_dir)
        for field in ("reviewed_at", "total_segments", "needs_review_count", "segments"):
            self.assertIn(field, result)

    def test_review_has_config(self):
        """review должен содержать поле config с настройками пайплайна."""
        result = _run_cli("review", self.work_dir)
        self.assertIn("config", result)
        self.assertIn("target_language", result["config"])

    def test_subtitles_registered_as_artifact(self):
        """После export-srt артефакт subtitles должен быть зарегистрирован."""
        _run_cli("export-srt", self.work_dir)
        art_result = _run_cli("artifacts", self.work_dir)
        kinds = [a["kind"] for a in art_result["artifacts"]]
        self.assertIn("subtitles", kinds)


if __name__ == "__main__":
    unittest.main()
