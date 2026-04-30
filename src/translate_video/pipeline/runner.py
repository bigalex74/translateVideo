"""Простой последовательный раннер пайплайна."""

from __future__ import annotations

from typing import Protocol

from translate_video.core.schemas import JobStatus, ProjectStatus, StageRun
from translate_video.pipeline.context import StageContext


class PipelineStage(Protocol):
    """Перезапускаемая единица работы пайплайна."""

    def run(self, context: StageContext) -> StageRun:
        """Выполнить этап и вернуть запись запуска."""


class PipelineRunner:
    """Запускает этапы последовательно и останавливается на первой ошибке."""

    def __init__(self, stages: list[PipelineStage]) -> None:
        self.stages = stages

    def run(self, context: StageContext) -> list[StageRun]:
        """Выполнить настроенные этапы по порядку."""

        context.project.status = ProjectStatus.RUNNING
        context.store.save_project(context.project)
        runs: list[StageRun] = []
        for stage in self.stages:
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
