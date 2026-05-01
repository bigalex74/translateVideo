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
        self.stage = run.stage
        self.called = False

    def run(self, context):
        """Отметить вызов и вернуть заранее заданную запись запуска этапа."""

        self.called = True
        return self.run_result


class PipelineRunnerTest(unittest.TestCase):
    """Проверяет управление последовательностью этапов."""

    def setUp(self):
        """Настройка окружения для тестов."""

        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")
        self.project = self.store.create_project("lesson.mp4", project_id="lesson")
        self.context = StageContext(project=self.project, store=self.store)

    def tearDown(self):
        """Очистка окружения после тестов."""

        self.temp_dir.cleanup()

    def test_runner_stops_on_failed_stage(self):
        """Раннер должен остановиться после первого упавшего этапа."""

        failed = StaticStage(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.FAILED))
        skipped = StaticStage(StageRun(stage=Stage.TRANSLATE, status=JobStatus.COMPLETED))
        runner = PipelineRunner([failed, skipped])

        runs = runner.run(context=self.context)
        restored = self.store.load_project(self.project.work_dir)

        self.assertEqual(len(runs), 1)
        self.assertTrue(failed.called)
        self.assertFalse(skipped.called)
        self.assertEqual(restored.status, ProjectStatus.FAILED)

    def test_empty_stages_list(self):
        """Пустой список этапов завершается успешно."""

        runner = PipelineRunner([])
        runs = runner.run(context=self.context)
        restored = self.store.load_project(self.project.work_dir)

        self.assertEqual(len(runs), 0)
        self.assertEqual(restored.status, ProjectStatus.COMPLETED)

    def test_successful_run(self):
        """Успешное завершение всех этапов."""

        stage1 = StaticStage(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED))
        stage2 = StaticStage(StageRun(stage=Stage.TRANSLATE, status=JobStatus.COMPLETED))
        runner = PipelineRunner([stage1, stage2])

        runs = runner.run(context=self.context)
        restored = self.store.load_project(self.project.work_dir)

        self.assertEqual(len(runs), 2)
        self.assertTrue(stage1.called)
        self.assertTrue(stage2.called)
        self.assertEqual(restored.status, ProjectStatus.COMPLETED)

    def test_skip_already_completed_stage(self):
        """Завершенные этапы должны пропускаться, если не указан force."""

        # Добавляем в проект уже завершенный этап
        self.project.stage_runs.append(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED))
        self.store.save_project(self.project)

        stage1 = StaticStage(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED))
        stage2 = StaticStage(StageRun(stage=Stage.TRANSLATE, status=JobStatus.COMPLETED))
        runner = PipelineRunner([stage1, stage2])

        runs = runner.run(context=self.context)

        self.assertEqual(len(runs), 2)
        self.assertFalse(stage1.called)
        self.assertEqual(runs[0].status, JobStatus.SKIPPED)
        self.assertTrue(stage2.called)

    def test_force_restarts_completed_stage(self):
        """Если указан force, завершенные этапы перезапускаются."""

        # Добавляем в проект уже завершенный этап
        self.project.stage_runs.append(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED))
        self.store.save_project(self.project)

        stage1 = StaticStage(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED))
        runner = PipelineRunner([stage1], force=True)

        runs = runner.run(context=self.context)

        self.assertEqual(len(runs), 1)
        self.assertTrue(stage1.called)
        self.assertEqual(runs[0].status, JobStatus.COMPLETED)


class ResumeRegressionTest(PipelineRunnerTest):
    """TVIDEO-030a: регрессия бага resume (_already_completed last-record).

    При повторном запуске force=False должна проверяться ПОСЛЕДНЯЯ запись
    этапа, а не любая из всех записей (включая старые COMPLETED).
    """

    def test_resume_reruns_failed_stage(self):
        """После упавшего запуска resume (force=False) перезапускает упавший этап."""
        # Симулируем: первый запуск — transcribe OK, translate FAILED
        self.project.stage_runs.append(
            StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED)
        )
        self.project.stage_runs.append(
            StageRun(stage=Stage.TRANSLATE, status=JobStatus.FAILED)
        )
        self.store.save_project(self.project)

        transcribe_stage = StaticStage(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED))
        translate_stage = StaticStage(StageRun(stage=Stage.TRANSLATE, status=JobStatus.COMPLETED))
        runner = PipelineRunner([transcribe_stage, translate_stage], force=False)

        runs = runner.run(context=self.context)

        # transcribe пропущен (последняя запись = COMPLETED)
        self.assertFalse(transcribe_stage.called, "transcribe не должен повторяться")
        self.assertEqual(runs[0].status, JobStatus.SKIPPED)
        # translate должен быть выполнен (последняя запись = FAILED)
        self.assertTrue(translate_stage.called, "translate должен быть перезапущен")
        self.assertEqual(runs[1].status, JobStatus.COMPLETED)

    def test_resume_after_completed_reruns_all(self):
        """После полного completed второй запуск force=False должен всё перезапустить.

        Когда все этапы уже COMPLETED (из последнего запуска), resume
        должен... на самом деле тоже пропустить их — это ПРАВИЛЬНОЕ поведение.
        Пользователь должен использовать force=True для полного перезапуска.
        """
        self.project.stage_runs.append(
            StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED)
        )
        self.project.stage_runs.append(
            StageRun(stage=Stage.TRANSLATE, status=JobStatus.COMPLETED)
        )
        self.store.save_project(self.project)

        transcribe_stage = StaticStage(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED))
        translate_stage = StaticStage(StageRun(stage=Stage.TRANSLATE, status=JobStatus.COMPLETED))
        runner = PipelineRunner([transcribe_stage, translate_stage], force=False)

        runs = runner.run(context=self.context)

        # Все пропущены — последние записи оба COMPLETED
        self.assertFalse(transcribe_stage.called)
        self.assertFalse(translate_stage.called)
        self.assertEqual(runs[0].status, JobStatus.SKIPPED)
        self.assertEqual(runs[1].status, JobStatus.SKIPPED)

    def test_second_failed_run_after_first_failed_reruns(self):
        """Два подряд FAILED запуска — каждый раз этап должен выполняться."""
        # После двух FAILED записей для одного этапа — resume должен перезапустить
        self.project.stage_runs.append(
            StageRun(stage=Stage.TRANSLATE, status=JobStatus.FAILED)
        )
        self.project.stage_runs.append(
            StageRun(stage=Stage.TRANSLATE, status=JobStatus.FAILED)
        )
        self.store.save_project(self.project)

        translate_stage = StaticStage(StageRun(stage=Stage.TRANSLATE, status=JobStatus.COMPLETED))
        runner = PipelineRunner([translate_stage], force=False)
        runner.run(context=self.context)

        self.assertTrue(translate_stage.called, "повторно упавший этап должен перезапуститься")

    def test_old_completed_does_not_block_resume_of_later_failed(self):
        """Старый COMPLETED не блокирует resume если потом был FAILED для того же этапа.

        Это регрессия основного бага: старый COMPLETED из предыдущего
        прогона пайплайна не должен скрывать последующий FAILED.
        """
        # Прогон 1: transcribe COMPLETED
        # Прогон 2: transcribe снова запущен и получил FAILED (force=True был)
        self.project.stage_runs.append(
            StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED)
        )
        self.project.stage_runs.append(
            StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.FAILED)
        )
        self.store.save_project(self.project)

        transcribe_stage = StaticStage(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED))
        runner = PipelineRunner([transcribe_stage], force=False)
        runner.run(context=self.context)

        # Последняя запись FAILED → должен перезапуститься
        self.assertTrue(transcribe_stage.called, "FAILED после COMPLETED должен перезапуститься")


if __name__ == "__main__":
    unittest.main()
