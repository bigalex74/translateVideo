"""Тесты CLI-адаптера."""

import unittest
from pathlib import Path
from unittest.mock import patch
import json

from translate_video.cli import main


class CLITest(unittest.TestCase):
    """Проверка обработки ошибок и аргументов CLI."""

    @patch("sys.stderr.write")
    def test_missing_work_dir(self, mock_stderr):
        """Несуществующая папка проекта вызывает ошибку без трейсбека."""

        exit_code = main(["status", "runs/non_existent_dir"])
        self.assertEqual(exit_code, 1)
        mock_stderr.assert_called()
        # Проверяем, что в stderr пишется сообщение об ошибке
        output = "".join(call.args[0] for call in mock_stderr.call_args_list)
        self.assertIn("Ошибка:", output)

    @patch("sys.stderr.write")
    @patch("translate_video.core.store.ProjectStore.load_project")
    def test_corrupted_project_json(self, mock_load, mock_stderr):
        """Поврежденный project.json вызывает ошибку без трейсбека."""

        mock_load.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        exit_code = main(["status", "runs/some_dir"])
        self.assertEqual(exit_code, 1)
        mock_stderr.assert_called()
        output = "".join(call.args[0] for call in mock_stderr.call_args_list)
        self.assertIn("Ошибка:", output)


if __name__ == "__main__":
    unittest.main()
