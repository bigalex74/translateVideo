"""Модульные тесты последовательного раннера пайплайна."""

import unittest
import tempfile
from pathlib import Path

from translate_video.core.schemas import JobStatus, ProjectStatus, Stage, StageRun
from translate_video.core.store import ProjectStore
from translate_video.pipeline.context import StageContext
from translate_video.pipeline.runner import PipelineRunner


class StaticStage:
    """Тестовый этап, который возвращает заранее заданный результат."""

    def __init__(self, run: StageRun):
        """Сохранить результат, который этап вернет при запуске."""

        self.run_result = run
        self.called = False

    def run(self, context):
        """Отметить вызов и вернуть заранее заданную запись запуска этапа."""

        self.called = True
        return self.run_result


class PipelineRunnerTest(unittest.TestCase):
    """Проверяет управление последовательностью этапов."""

    def test_runner_stops_on_failed_stage(self):
        """Раннер должен остановиться после первого упавшего этапа."""

        failed = StaticStage(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.FAILED))
        skipped = StaticStage(StageRun(stage=Stage.TRANSLATE, status=JobStatus.COMPLETED))
        runner = PipelineRunner([failed, skipped])

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project("lesson.mp4", project_id="lesson")
            context = StageContext(project=project, store=store)

            runs = runner.run(context=context)
            restored = store.load_project(project.work_dir)

            self.assertEqual(len(runs), 1)
            self.assertTrue(failed.called)
            self.assertFalse(skipped.called)
            self.assertEqual(restored.status, ProjectStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
