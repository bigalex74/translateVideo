"""Простой последовательный раннер пайплайна."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Protocol

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

    def __init__(
        self,
        stages: list[PipelineStage],
        *,
        force: bool = False,
        from_stage: str | None = None,
    ) -> None:
        self.stages = stages
        self.force = force
        self.from_stage = from_stage
        # Опциональный callback: вызывается после каждого завершённого этапа
        # Сигнатура: on_stage_done(stage_index: int, total_stages: int, elapsed: float) -> None
        self.on_stage_done: "Callable[[int, int, float], None] | None" = None

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
            from_stage=self.from_stage,
        )

        context.project.status = ProjectStatus.RUNNING

        # ── Дедупликация stage_runs ────────────────────────────────────────────
        # После нескольких запусков в stage_runs накапливаются дубли одной стадии.
        # _already_completed берёт ПОСЛЕДНЮЮ запись через reversed() — если она
        # не completed (running/failed от предыдущего запуска), стадия перезапустится.
        # Оставляем только последнюю запись на стадию ПЕРЕД любым сбросом.
        context.project.stage_runs = _dedup_stage_runs(context.project.stage_runs)

        if self.from_stage:
            # from_stage имеет приоритет над force: сбрасываем указанный этап и последующие,
            # предыдущие completed-этапы остаются нетронутыми (будут пропущены).
            self._reset_from(context, self.from_stage)
            _log.info(
                "pipeline.stage_runs_reset_from",
                project=project_id,
                from_stage=self.from_stage,
                force=self.force,
            )
        elif self.force:
            # При force без from_stage — чистим всю историю.
            context.project.stage_runs = []
            context.project.billing_snapshots = {}
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

                # ── Вычисляем множество этапов ДО from_stage ещё до цикла в py3.10+ ──
                # Если from_stage задан — этапы ДО него всегда пропускаются,
                # даже если force=True. force влияет только на этапы НАЧИНАЯ с from_stage.
                is_before_from_stage = (
                    self.from_stage is not None
                    and stage.stage.value != self.from_stage
                    and self._is_before(stage.stage.value, self.from_stage)
                )
                # Пропускаем этап, если:
                # 1) этап до from_stage (from_stage задан) — всегда
                # 2) force=False и этап уже completed
                if is_before_from_stage or (
                    not self.force and self._already_completed(context, stage.stage)
                ):
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
                # Вызываем progress-callback после каждого выполненного этапа
                if self.on_stage_done is not None:
                    stages_done = sum(1 for r in runs if r.status != JobStatus.SKIPPED)
                    try:
                        self.on_stage_done(stages_done, len(self.stages), total.elapsed)
                    except Exception:  # noqa: BLE001
                        pass
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

    def _reset_from(self, context: StageContext, from_stage_value: str) -> None:
        """Удалить stage_runs начиная с from_stage и все последующие.

        Порядок стадий берётся из РЕАЛЬНОГО пайплайна (self.stages),
        а не из Stage-enum (порядок в котором может не совпадать с реальным).
        Предшествующие completed-записи остаются нетронутыми.
        """
        pipeline_order = [s.stage.value for s in self.stages]
        try:
            from_idx = pipeline_order.index(from_stage_value)
        except ValueError:
            # Неизвестный этап — не трогаем ничего
            return

        stages_to_reset = set(pipeline_order[from_idx:])
        # Оставляем только записи для этапов ПЕРЕД from_stage
        context.project.stage_runs = [
            r for r in context.project.stage_runs
            if r.stage.value not in stages_to_reset
        ]

    def _is_before(self, stage_value: str, reference_value: str) -> bool:
        """Вернуть True если stage_value идёт раньше reference_value в пайплайне."""
        pipeline_order = [s.stage.value for s in self.stages]
        try:
            return pipeline_order.index(stage_value) < pipeline_order.index(reference_value)
        except ValueError:
            return False


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


def _dedup_stage_runs(runs: list[StageRun]) -> list[StageRun]:
    """Оставить по одной записи для каждого этапа, предпочитая completed.

    Проблема: после нескольких запусков / рестартов контейнера в stage_runs
    накапливаются дубли:
      extract_audio  completed   ← запуск 1 (валидный)
      transcribe     completed
      extract_audio  completed   ← запуск 2
      transcribe     running     ← прерван рестартом → ЗАВИСШИЙ статус

    Логика выбора для каждой стадии:
      1. Если есть хотя бы одна completed-запись → берём её.
      2. Иначе берём ПОСЛЕДНЮЮ запись (failed / running / etc.).

    Порядок результата = первое вхождение каждой стадии в исходном списке.
    """
    # Собираем все записи по стадиям
    by_stage: dict[str, list[StageRun]] = {}
    order: list[str] = []
    for run in runs:
        key = run.stage.value
        if key not in by_stage:
            by_stage[key] = []
            order.append(key)
        by_stage[key].append(run)

    result: list[StageRun] = []
    for key in order:
        stage_runs = by_stage[key]
        last = stage_runs[-1]
        # Если последняя запись — «running» (зависший статус от рестарта контейнера),
        # ищем последний completed перед ней. Если нашли — берём его.
        # Если последняя — failed (реальная ошибка) — оставляем failed → перезапустится.
        if last.status == JobStatus.RUNNING:
            completed = [r for r in stage_runs if r.status == JobStatus.COMPLETED]
            result.append(completed[-1] if completed else last)
        else:
            result.append(last)
    return result
