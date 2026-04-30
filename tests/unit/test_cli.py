"""Модульные тесты CLI-обертки."""

from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from translate_video.cli import main


class CliTest(unittest.TestCase):
    """Проверяет команды CLI без внешних провайдеров."""

    def test_init_creates_project_with_config(self):
        """Команда init должна создать проект и сохранить настройки."""

        with tempfile.TemporaryDirectory() as temp_dir:
            output = StringIO()
            code = main(
                [
                    "init",
                    "lesson.mp4",
                    "--work-root",
                    temp_dir,
                    "--project-id",
                    "lesson",
                    "--source-language",
                    "en",
                    "--target-language",
                    "ru",
                    "--translation-mode",
                    "subtitles",
                    "--translation-style",
                    "business",
                    "--do-not-translate",
                    "OpenAI",
                ],
                stdout=output,
            )

            payload = json.loads(output.getvalue())

            self.assertEqual(code, 0)
            self.assertEqual(payload["project_id"], "lesson")
            self.assertEqual(payload["status"], "created")
            self.assertEqual(payload["work_dir"], str(Path(temp_dir) / "lesson"))
            settings = json.loads((Path(temp_dir) / "lesson" / "settings.json").read_text())
            self.assertEqual(settings["translation_mode"], "subtitles")
            self.assertEqual(settings["translation_style"], "business")
            self.assertEqual(settings["do_not_translate"], ["OpenAI"])

    def test_config_prints_saved_settings(self):
        """Команда config должна вернуть сохраненную конфигурацию проекта."""

        with tempfile.TemporaryDirectory() as temp_dir:
            main(
                [
                    "init",
                    "lesson.mp4",
                    "--work-root",
                    temp_dir,
                    "--project-id",
                    "lesson",
                    "--target-language",
                    "de",
                ],
                stdout=StringIO(),
            )
            output = StringIO()

            code = main(["config", str(Path(temp_dir) / "lesson")], stdout=output)

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["target_language"], "de")


if __name__ == "__main__":
    unittest.main()
