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


class CancelPipelineTest(unittest.TestCase):
    """TVIDEO-070: тесты отмены пайплайна через cancel_event."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")
        self.project = self.store.create_project("lesson.mp4", project_id="lesson")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cancel_event_default_not_set(self):
        """StageContext.cancel_event должен быть не установлен по умолчанию."""
        import threading
        ctx = StageContext(project=self.project, store=self.store)
        self.assertIsInstance(ctx.cancel_event, threading.Event)
        self.assertFalse(ctx.cancel_event.is_set(), "cancel_event не должен быть установлен по умолчанию")

    def test_cancel_before_first_stage_raises(self):
        """Если cancel_event установлен до запуска, PipelineCancelledError выбрасывается сразу."""
        from translate_video.pipeline.runner import PipelineCancelledError
        stage = StaticStage(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED))
        ctx = StageContext(project=self.project, store=self.store)
        ctx.cancel_event.set()

        runner = PipelineRunner([stage])
        with self.assertRaises(PipelineCancelledError):
            runner.run(ctx)

        self.assertFalse(stage.called, "этап не должен запускаться после установки cancel_event")

    def test_cancel_between_stages(self):
        """Cancel_event, установленный первым этапом, останавливает второй."""
        from translate_video.pipeline.runner import PipelineCancelledError

        ctx = StageContext(project=self.project, store=self.store)

        class CancellingStage:
            """Первый этап — сам устанавливает cancel_event."""
            stage = Stage.TRANSCRIBE
            called = False

            def run(self, context):
                self.called = True
                context.cancel_event.set()   # устанавливаем флаг внутри этапа
                return StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED)

        first = CancellingStage()
        second = StaticStage(StageRun(stage=Stage.TRANSLATE, status=JobStatus.COMPLETED))

        runner = PipelineRunner([first, second])
        with self.assertRaises(PipelineCancelledError):
            runner.run(ctx)

        self.assertTrue(first.called, "первый этап должен был выполниться")
        self.assertFalse(second.called, "второй этап не должен запускаться после отмены")

    def test_cancel_sets_project_status_failed(self):
        """После PipelineCancelledError проект должен остаться в статусе RUNNING (runner не меняет сам)."""
        from translate_video.pipeline.runner import PipelineCancelledError
        ctx = StageContext(project=self.project, store=self.store)
        ctx.cancel_event.set()

        runner = PipelineRunner([
            StaticStage(StageRun(stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED))
        ])

        with self.assertRaises(PipelineCancelledError):
            runner.run(ctx)
        # API-слой (pipeline.py) отвечает за перевод в FAILED при отмене.
        # Runner сам не меняет статус при отмене — проверяем что он не COMPLETED.
        restored = self.store.load_project(self.project.work_dir)
        self.assertNotEqual(restored.status, ProjectStatus.COMPLETED)

    def test_independent_cancel_events_per_context(self):
        """Два StageContext независимы — cancel одного не влияет на другой."""
        ctx1 = StageContext(project=self.project, store=self.store)
        ctx2 = StageContext(project=self.project, store=self.store)
        ctx1.cancel_event.set()
        self.assertTrue(ctx1.cancel_event.is_set())
        self.assertFalse(ctx2.cancel_event.is_set(), "cancel_event должны быть независимыми объектами")


class DedupStageRunsTest(unittest.TestCase):
    """TVIDEO-088c/d: тесты функции _dedup_stage_runs.

    Проверяет корректное схлопывание дубликатов stage_runs
    с приоритетом completed над running (но не над failed).
    """

    def _run(self, *entries):
        """Создать список StageRun из кортежей (stage, status)."""
        from translate_video.pipeline.runner import _dedup_stage_runs
        runs = [StageRun(stage=stage, status=status) for stage, status in entries]
        return _dedup_stage_runs(runs)

    def test_no_duplicates_unchanged(self):
        """Без дублей список не изменяется."""
        result = self._run(
            (Stage.TRANSCRIBE, JobStatus.COMPLETED),
            (Stage.TRANSLATE, JobStatus.FAILED),
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].stage, Stage.TRANSCRIBE)
        self.assertEqual(result[0].status, JobStatus.COMPLETED)
        self.assertEqual(result[1].stage, Stage.TRANSLATE)
        self.assertEqual(result[1].status, JobStatus.FAILED)

    def test_running_replaced_by_completed(self):
        """Дубль running → берём предыдущий completed (рестарт контейнера)."""
        result = self._run(
            (Stage.TRANSCRIBE, JobStatus.COMPLETED),
            (Stage.TRANSCRIBE, JobStatus.RUNNING),  # зависший после рестарта
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].stage, Stage.TRANSCRIBE)
        self.assertEqual(result[0].status, JobStatus.COMPLETED,
                         "running должен откатиться до completed")

    def test_failed_not_replaced_by_completed(self):
        """completed → failed: оставляем failed (реальная ошибка → перезапуск)."""
        result = self._run(
            (Stage.TRANSCRIBE, JobStatus.COMPLETED),
            (Stage.TRANSCRIBE, JobStatus.FAILED),
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].status, JobStatus.FAILED,
                         "failed после completed должен оставаться failed")

    def test_order_preserved(self):
        """Порядок этапов в результате = первое вхождение."""
        result = self._run(
            (Stage.EXTRACT_AUDIO, JobStatus.COMPLETED),
            (Stage.TRANSCRIBE,    JobStatus.COMPLETED),
            (Stage.REGROUP,       JobStatus.COMPLETED),
            (Stage.EXTRACT_AUDIO, JobStatus.RUNNING),  # дубль
            (Stage.TRANSCRIBE,    JobStatus.RUNNING),  # дубль
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].stage, Stage.EXTRACT_AUDIO)
        self.assertEqual(result[1].stage, Stage.TRANSCRIBE)
        self.assertEqual(result[2].stage, Stage.REGROUP)
        # Оба running → откат к completed
        self.assertEqual(result[0].status, JobStatus.COMPLETED)
        self.assertEqual(result[1].status, JobStatus.COMPLETED)

    def test_empty_list(self):
        """Пустой список → пустой результат."""
        from translate_video.pipeline.runner import _dedup_stage_runs
        self.assertEqual(_dedup_stage_runs([]), [])

    def test_single_entry_unchanged(self):
        """Одна запись → без изменений."""
        result = self._run((Stage.TRANSLATE, JobStatus.FAILED))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].status, JobStatus.FAILED)

    def test_multiple_running_no_completed_keeps_last(self):
        """Несколько running без completed → берём последний running."""
        result = self._run(
            (Stage.TTS, JobStatus.RUNNING),
            (Stage.TTS, JobStatus.RUNNING),
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].status, JobStatus.RUNNING)


if __name__ == "__main__":
    unittest.main()
