"""Simple sequential pipeline runner."""

from __future__ import annotations

from typing import Protocol

from translate_video.core.schemas import JobStatus, ProjectStatus, StageRun
from translate_video.pipeline.context import StageContext


class PipelineStage(Protocol):
    """A rerunnable unit of pipeline work."""

    def run(self, context: StageContext) -> StageRun:
        """Execute a stage and return its recorded run."""


class PipelineRunner:
    """Runs stages sequentially and stops on the first failure."""

    def __init__(self, stages: list[PipelineStage]) -> None:
        self.stages = stages

    def run(self, context: StageContext) -> list[StageRun]:
        """Execute configured stages in order."""

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
