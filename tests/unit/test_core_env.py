"""Тесты загрузки локального `.env` без внешних зависимостей."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from translate_video.core import env


class EnvLoaderTest(unittest.TestCase):
    """Проверяет безопасное чтение `.env`."""

    def setUp(self):
        """Сбросить одноразовый флаг загрузчика перед тестом."""

        env._LOADED = False

    def tearDown(self):
        """Сбросить одноразовый флаг загрузчика между тестами."""

        env._LOADED = False

    def test_load_env_file_sets_missing_values(self):
        """Загрузчик добавляет переменные из файла."""

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".env"
            path.write_text("GEMINI_API_KEY=test\n", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                env.load_env_file(path)

                import os
                self.assertEqual(os.environ["GEMINI_API_KEY"], "test")

    def test_load_env_file_does_not_override_existing_values(self):
        """Загрузчик не перезаписывает окружение процесса."""

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".env"
            path.write_text("GEMINI_API_KEY=file\n", encoding="utf-8")

            with patch.dict("os.environ", {"GEMINI_API_KEY": "process"}, clear=True):
                env.load_env_file(path)

                import os
                self.assertEqual(os.environ["GEMINI_API_KEY"], "process")


if __name__ == "__main__":
    unittest.main()
