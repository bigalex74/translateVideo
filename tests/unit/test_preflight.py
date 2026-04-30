"""Модульные тесты предварительных проверок запуска."""

from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from translate_video.cli import main
from translate_video.core.preflight import run_preflight


class PreflightTest(unittest.TestCase):
    """Проверяет диагностику файла и окружения до запуска пайплайна."""

    def test_fake_provider_requires_only_existing_input_file(self):
        """Имитационный провайдер должен требовать только входной файл."""

        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "lesson.mp4"
            video.write_bytes(b"video")

            report = run_preflight(video, "fake")

            self.assertTrue(report.ok)
            self.assertEqual(report.provider, "fake")
            self.assertEqual([check.name for check in report.checks], ["input_video", "provider"])

    def test_missing_input_file_fails_report(self):
        """Отсутствующий входной файл должен делать отчет неуспешным."""

        report = run_preflight("/tmp/missing-video.mp4", "fake")

        self.assertFalse(report.ok)
        self.assertEqual(report.checks[0].name, "input_video")
        self.assertEqual(report.checks[0].message, "входной файл не найден")

    def test_legacy_provider_reports_missing_dependencies(self):
        """Провайдер устаревшего скрипта должен показать отсутствующие зависимости."""

        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "lesson.mp4"
            video.write_bytes(b"video")

            report = run_preflight(
                video,
                "legacy",
                module_finder=lambda _module: None,
                executable_finder=lambda _executable: None,
            )

            self.assertFalse(report.ok)
            names = [check.name for check in report.checks]
            self.assertIn("python_module:moviepy", names)
            self.assertIn("python_module:faster_whisper", names)
            self.assertIn("executable:ffmpeg", names)
            self.assertIn("executable:ffprobe", names)

    def test_legacy_provider_passes_when_dependencies_are_available(self):
        """Провайдер устаревшего скрипта должен пройти при доступных зависимостях."""

        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "lesson.mp4"
            video.write_bytes(b"video")

            report = run_preflight(
                video,
                "legacy",
                module_finder=lambda module: object(),
                executable_finder=lambda executable: f"/usr/bin/{executable}",
            )

            self.assertTrue(report.ok)

    def test_cli_preflight_outputs_json_report(self):
        """CLI-команда preflight должна вернуть JSON-отчет."""

        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "lesson.mp4"
            video.write_bytes(b"video")
            output = StringIO()

            code = main(["preflight", str(video), "--provider", "fake"], stdout=output)

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["provider"], "fake")


if __name__ == "__main__":
    unittest.main()
