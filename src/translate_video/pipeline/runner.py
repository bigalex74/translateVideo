"""Простой последовательный раннер пайплайна."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from translate_video.core.log import Timer, get_logger
from translate_video.core.schemas import JobStatus, ProjectStatus, Stage, StageRun
from translate_video.pipeline.context import StageContext

_log = get_logger(__name__)

# Платные провайдеры, для которых делаем балансовые снапшоты.
_BILLING_PROVIDERS = ("polza", "neuroapi")


class PipelineCancelledError(Exception):
    """Пайплайн прерван по запросу пользователя."""


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
        Проверяет `context.cancel_event` между этапами — если установлен,
        выбрасывает `PipelineCancelledError`.
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
        if self.force:
            # При force-запуске чистим историю этапов — чтобы UI показывал
            # только текущий прогон, а не артефакты предыдущих.
            context.project.stage_runs = []
            context.project.billing_snapshots = {}  # чистим старые снапшоты
            _log.info("pipeline.stage_runs_reset", project=project_id)
        context.store.save_project(context.project)

        # ── Снапшот баланса ДО запуска этапов ──────────────────────────────
        _snapshot_balances(context, suffix="before")
        context.store.save_project(context.project)

        runs: list[StageRun] = []

        with Timer() as total:
            for stage in self.stages:
                # ── Проверка отмены ПЕРЕД каждым этапом ──────────────────────
                if context.cancel_event.is_set():
                    _log.info(
                        "pipeline.cancelled",
                        project=project_id,
                        stage=stage.stage.value,
                        reason="cancel_requested",
                    )
                    raise PipelineCancelledError(
                        f"Pipeline cancelled before stage {stage.stage.value}"
                    )

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

        # ── Снапшот баланса ПОСЛЕ завершения этапов ────────────────────────
        _snapshot_balances(context, suffix="after")
        context.store.save_project(context.project)

        total_s = total.elapsed
        _log.info(
            "pipeline.done",
            project=project_id,
            status=context.project.status.value,
            total_elapsed_s=total_s,
            stages_ran=sum(1 for r in runs if r.status != JobStatus.SKIPPED),
            stages_skipped=sum(1 for r in runs if r.status == JobStatus.SKIPPED),
        )

        # ── Автосводка: pipeline.summary — все этапы с временем ──────────────
        # Удобна для log_analyze.py: одна строка = весь прогон.
        stage_times: dict[str, float | None] = {
            r.stage.value: _elapsed_from_run(r)
            for r in runs
            if r.status != JobStatus.SKIPPED
        }
        failed_stages = [r.stage.value for r in runs if r.status == JobStatus.FAILED]
        _log.info(
            "pipeline.summary",
            project=project_id,
            status=context.project.status.value,
            total_elapsed_s=round(total_s, 2),
            stage_times=stage_times,
            failed_stages=failed_stages or None,
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


def _elapsed_from_run(run: StageRun) -> float | None:
    """Вычислить длительность этапа из ISO-меток started_at / finished_at."""
    if run.started_at is None or run.finished_at is None:
        return None
    try:
        fmt = "%Y-%m-%dT%H:%M:%S.%f"
        start = datetime.strptime(run.started_at[:26], fmt).replace(tzinfo=timezone.utc)
        end = datetime.strptime(run.finished_at[:26], fmt).replace(tzinfo=timezone.utc)
        return round((end - start).total_seconds(), 2)
    except (ValueError, TypeError):
        return None


def _snapshot_balances(context: StageContext, *, suffix: str) -> None:
    """Записать баланс каждого платного провайдера в context.project.billing_snapshots.

    suffix = "before" | "after"
    Ошибки сети/API логируются, но не прерывают пайплайн.
    """
    from translate_video.core.provider_catalog import get_provider_balance  # lazy

    for provider in _BILLING_PROVIDERS:
        key = f"{provider}_{suffix}"
        try:
            balance = get_provider_balance(provider)
            # Сохраняем текущий остаток счёта (balance.balance).
            # Расход = before.balance - after.balance
            if balance.configured and balance.balance is not None:
                context.project.billing_snapshots[key] = balance.balance
                _log.info(
                    "billing.snapshot",
                    provider=provider,
                    suffix=suffix,
                    balance=balance.balance,
                    currency=balance.currency,
                )
            elif not balance.configured:
                _log.debug("billing.skip", provider=provider, reason="not_configured")
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "billing.snapshot_error",
                provider=provider,
                suffix=suffix,
                error=str(exc),
            )
