"""Интеграционные тесты CLI и пайплайна."""

from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from translate_video.cli import main


class CliPipelineIntegrationTest(unittest.TestCase):
    """Проверяет CLI-запуск пайплайна через ядро."""

    def test_run_executes_fake_pipeline_and_status_commands(self):
        """Команда run должна создать артефакты, а status/artifacts должны их читать."""

        with tempfile.TemporaryDirectory() as temp_dir:
            run_output = StringIO()
            code = main(
                [
                    "run",
                    "lesson.mp4",
                    "--work-root",
                    temp_dir,
                    "--project-id",
                    "lesson",
                    "--target-language",
                    "es",
                ],
                stdout=run_output,
            )
            run_payload = json.loads(run_output.getvalue())

            self.assertEqual(code, 0)
            self.assertEqual(run_payload["status"], "completed")
            self.assertEqual(run_payload["segments"], 1)
            self.assertEqual(len(run_payload["runs"]), 7)  # +RegroupStage + TimingFitStage
            self.assertEqual(run_payload["artifacts"]["output_video"], "output/translated.mp4")
            self.assertTrue((Path(temp_dir) / "lesson" / "output" / "translated.mp4").exists())

            status_output = StringIO()
            main(["status", str(Path(temp_dir) / "lesson")], stdout=status_output)
            status_payload = json.loads(status_output.getvalue())

            self.assertEqual(status_payload["status"], "completed")
            self.assertEqual(len(status_payload["stage_runs"]), 7)  # +RegroupStage + TimingFitStage

            artifacts_output = StringIO()
            main(["artifacts", str(Path(temp_dir) / "lesson")], stdout=artifacts_output)
            artifacts_payload = json.loads(artifacts_output.getvalue())

            self.assertEqual(artifacts_payload["project_id"], "lesson")
            self.assertIn("output_video", [item["kind"] for item in artifacts_payload["artifacts"]])


if __name__ == "__main__":
    unittest.main()
