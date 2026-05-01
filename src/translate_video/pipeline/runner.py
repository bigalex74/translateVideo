"""Простой последовательный раннер пайплайна."""

from __future__ import annotations

from typing import Protocol

from translate_video.core.log import Timer, get_logger
from translate_video.core.schemas import JobStatus, ProjectStatus, Stage, StageRun
from translate_video.pipeline.context import StageContext

_log = get_logger(__name__)


class PipelineStage(Protocol):
    """Перезапускаемая единица работы пайплайна."""

    stage: Stage

    def run(self, context: StageContext) -> StageRun:
        """Выполнить этап и вернуть запись запуска."""


class PipelineRunner:
    """Запускает этапы последовательно и останавливается на первой ошибке."""

    def __init__(self, stages: list[PipelineStage], *, force: bool = False) -> None:
        self.stages = stages
        self.force = force

    def run(self, context: StageContext) -> list[StageRun]:
        """Выполнить настроенные этапы по порядку.

        Ранее завершённые этапы пропускаются, если ``force`` не установлен.
        """
        project_id = context.project.id
        stage_names = [s.stage.value for s in self.stages]

        _log.info(
            "pipeline.start",
            project=project_id,
            stages=stage_names,
            force=self.force,
        )

        context.project.status = ProjectStatus.RUNNING
        context.store.save_project(context.project)
        runs: list[StageRun] = []

        with Timer() as total:
            for stage in self.stages:
                if not self.force and self._already_completed(context, stage.stage):
                    skipped = StageRun(
                        stage=stage.stage,
                        status=JobStatus.SKIPPED,
                    )
                    runs.append(skipped)
                    _log.info(
                        "pipeline.skip",
                        project=project_id,
                        stage=stage.stage.value,
                        reason="already_completed",
                    )
                    continue
                run = stage.run(context)
                runs.append(run)
                if run.status == JobStatus.FAILED:
                    context.project.status = ProjectStatus.FAILED
                    context.store.save_project(context.project)
                    _log.error(
                        "pipeline.fail",
                        project=project_id,
                        stage=stage.stage.value,
                        total_elapsed_s=total.elapsed,
                    )
                    break
            else:
                context.project.status = ProjectStatus.COMPLETED
                context.store.save_project(context.project)

        _log.info(
            "pipeline.done",
            project=project_id,
            status=context.project.status.value,
            total_elapsed_s=total.elapsed,
            stages_ran=sum(1 for r in runs if r.status != JobStatus.SKIPPED),
            stages_skipped=sum(1 for r in runs if r.status == JobStatus.SKIPPED),
        )
        return runs

    @staticmethod
    def _already_completed(context: StageContext, stage: Stage) -> bool:
        """Проверить что последний запуск данного этапа завершился успешно.

        Используем ПОСЛЕДНЮЮ запись для этапа, а не любую из всех.
        Это исправляет баг resume: старые COMPLETED-записи из прошлых
        запусков не должны блокировать повторное выполнение этапа.
        """
        last = next(
            (r for r in reversed(context.project.stage_runs) if r.stage == stage),
            None,
        )
        return last is not None and last.status == JobStatus.COMPLETED
