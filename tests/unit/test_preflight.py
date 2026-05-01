"""Модульные тесты предварительных проверок запуска."""

from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from translate_video.cli import main
from translate_video.core.preflight import _probe_duration, run_preflight


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
        self.assertIn("не найден", report.checks[0].message)

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
            self.assertIn("timing_rewriter:gemini", names)
            self.assertIn("timing_rewriter:polza", names)

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

    def test_legacy_preflight_reports_optional_rewriter_keys(self):
        """Preflight показывает ключи rewriter-провайдеров, но не валит запуск без них."""

        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "lesson.mp4"
            video.write_bytes(b"video")

            with patch("translate_video.core.preflight.load_env_file", lambda: None), \
                    patch.dict("os.environ", {"GEMINI_API_KEY": "secret"}, clear=True):
                report = run_preflight(
                    video,
                    "legacy",
                    module_finder=lambda module: object(),
                    executable_finder=lambda executable: f"/usr/bin/{executable}",
                )

            gemini = next(c for c in report.checks if c.name == "timing_rewriter:gemini")
            polza = next(c for c in report.checks if c.name == "timing_rewriter:polza")
            self.assertTrue(report.ok)
            self.assertEqual(gemini.message, "ключ найден")
            self.assertIn("будет пропущен", polza.message)

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

    def test_report_includes_duration_seconds_field(self):
        """Отчет должен содержать поле duration_seconds в to_dict()."""

        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "lesson.mp4"
            video.write_bytes(b"video")

            report = run_preflight(video, "fake")
            payload = report.to_dict()

            self.assertIn("duration_seconds", payload)

    def test_duration_none_when_ffprobe_unavailable(self):
        """duration_seconds должен быть None когда ffprobe недоступен."""

        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "lesson.mp4"
            video.write_bytes(b"video")

            report = run_preflight(
                video,
                "fake",
                executable_finder=lambda _: None,
            )

            self.assertIsNone(report.duration_seconds)

    def test_duration_returned_when_ffprobe_available(self):
        """duration_seconds должен быть float когда ffprobe доступен и файл — медиа."""

        import subprocess
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "lesson.mp4"
            video.write_bytes(b"video")

            mock_result = mock.MagicMock()
            mock_result.stdout = "123.45\n"

            with mock.patch("subprocess.run", return_value=mock_result):
                duration = _probe_duration(
                    video,
                    executable_finder=lambda x: f"/usr/bin/{x}",
                )

            self.assertAlmostEqual(duration, 123.45)

    def test_unknown_provider_fails_report(self):
        """Неизвестный провайдер должен давать ошибку проверки провайдера."""

        with tempfile.TemporaryDirectory() as temp_dir:
            video = Path(temp_dir) / "lesson.mp4"
            video.write_bytes(b"video")

            report = run_preflight(video, "unknown_provider")

            self.assertFalse(report.ok)
            provider_check = next(c for c in report.checks if c.name == "provider")
            self.assertFalse(provider_check.ok)


if __name__ == "__main__":
    unittest.main()
