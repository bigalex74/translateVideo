"""Простой последовательный раннер пайплайна."""

from __future__ import annotations

from typing import Protocol

from translate_video.core.schemas import JobStatus, ProjectStatus, Stage, StageRun
from translate_video.pipeline.context import StageContext


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

        context.project.status = ProjectStatus.RUNNING
        context.store.save_project(context.project)
        runs: list[StageRun] = []
        for stage in self.stages:
            if not self.force and self._already_completed(context, stage.stage):
                skipped = StageRun(
                    stage=stage.stage,
                    status=JobStatus.SKIPPED,
                )
                runs.append(skipped)
                continue
            run = stage.run(context)
            runs.append(run)
            if run.status == JobStatus.FAILED:
                context.project.status = ProjectStatus.FAILED
                context.store.save_project(context.project)
                break
        else:
            context.project.status = ProjectStatus.COMPLETED
            context.store.save_project(context.project)
        return runs

    @staticmethod
    def _already_completed(context: StageContext, stage: Stage) -> bool:
        """Проверить наличие завершённого запуска данного этапа в проекте."""

        return any(
            run.stage == stage and run.status == JobStatus.COMPLETED
            for run in context.project.stage_runs
        )
