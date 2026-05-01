"""Этапы пайплайна, использующие провайдеры через контракты."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from translate_video.core.schemas import (
    ArtifactKind,
    JobStatus,
    Segment,
    SegmentStatus,
    Stage,
    StageRun,
)
from translate_video.media.base import MediaProvider
from translate_video.pipeline.context import StageContext
from translate_video.render.base import Renderer
from translate_video.speech.base import Transcriber
from translate_video.translation.base import Translator
from translate_video.tts.base import TTSProvider
from translate_video.timing.base import TimingFitter


from translate_video.core.log import Timer, get_logger

_log = get_logger(__name__)


class BaseStage:
    """Базовая реализация единообразной записи успеха и ошибки этапа."""

    stage: Stage

    def _record(
        self,
        context: StageContext,
        action: Callable[[], tuple[list[str], list[str]]],
    ) -> StageRun:
        project_id = context.project.id
        stage_name = self.stage.value

        started_at = datetime.now(UTC).isoformat()
        run = StageRun(stage=self.stage, status=JobStatus.RUNNING, started_at=started_at)
        context.store.record_stage_run(context.project, run)

        _log.info("stage.start", stage=stage_name, project=project_id)

        with Timer() as t:
            try:
                inputs, outputs = action()
            except Exception as exc:  # noqa: BLE001 - ошибки этапа нужно сохранить.
                failed = StageRun(
                    id=run.id,
                    stage=self.stage,
                    status=JobStatus.FAILED,
                    inputs=run.inputs,
                    outputs=[],
                    error=str(exc),
                    attempt=run.attempt,
                    started_at=started_at,
                    finished_at=datetime.now(UTC).isoformat(),
                )
                context.store.record_stage_run(context.project, failed)
                _log.error(
                    "stage.fail",
                    stage=stage_name,
                    project=project_id,
                    elapsed_s=t.elapsed,
                    error=str(exc),
                )
                return failed

        completed = StageRun(
            id=run.id,
            stage=self.stage,
            status=JobStatus.COMPLETED,
            inputs=inputs,
            outputs=outputs,
            attempt=run.attempt,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
        )
        context.store.record_stage_run(context.project, completed)
        _log.info(
            "stage.done",
            stage=stage_name,
            project=project_id,
            elapsed_s=t.elapsed,
            outputs=len(outputs),
        )
        return completed


class ExtractAudioStage(BaseStage):
    """Извлекает исходное аудио из входного видео."""

    stage = Stage.EXTRACT_AUDIO

    def __init__(self, media_provider: MediaProvider) -> None:
        self.media_provider = media_provider

    def run(self, context: StageContext) -> StageRun:
        def action() -> tuple[list[str], list[str]]:
            audio_path = self.media_provider.extract_audio(context.project)
            record = context.store.add_artifact(
                context.project,
                kind=ArtifactKind.SOURCE_AUDIO,
                path=audio_path,
                stage=self.stage,
                content_type="audio/wav",
            )
            return [context.project.input_video.as_posix()], [record.path]

        return self._record(context, action)


class TranscribeStage(BaseStage):
    """Создает исходные сегменты расшифровки из извлеченного аудио."""

    stage = Stage.TRANSCRIBE

    def __init__(self, transcriber: Transcriber) -> None:
        self.transcriber = transcriber

    def run(self, context: StageContext) -> StageRun:
        def action() -> tuple[list[str], list[str]]:
            source_audio = _required_artifact(context, ArtifactKind.SOURCE_AUDIO)
            raw_path = Path(source_audio.path)
            if raw_path.is_absolute():
                audio_path = raw_path
            else:
                candidate = (context.project.work_dir / raw_path).resolve()
                if not candidate.exists():
                    # Старый формат: path содержит work_dir внутри (runs/proj/runs/proj/file)
                    # Пробуем просто basename
                    audio_path = context.project.work_dir.resolve() / raw_path.name
                else:
                    audio_path = candidate
            segments = self.transcriber.transcribe(audio_path, context.project.config)
            for segment in segments:
                segment.status = SegmentStatus.TRANSCRIBED
            output_path = context.store.save_segments(context.project, segments, translated=False)
            output = output_path.relative_to(context.project.work_dir).as_posix()
            return [source_audio.path], [output]

        return self._record(context, action)



class RegroupStage(BaseStage):
    """Объединяет Whisper-фрагменты в сегменты уровня предложения (TVIDEO-039).

    Запускается после TranscribeStage и до TranslateStage.
    Не обращается к внешним сервисам — только чистая логика.
    """

    stage = Stage.REGROUP

    def run(self, context: StageContext) -> StageRun:
        def action() -> tuple[list[str], list[str]]:
            from translate_video.speech.regroup import regroup_by_sentences

            before = len(context.project.segments)
            context.project.segments = regroup_by_sentences(
                context.project.segments,
                max_slot=context.project.config.regroup_max_slot,
            )
            after = len(context.project.segments)

            # Перезаписываем source transcript с перегруппированными сегментами
            output_path = context.store.save_segments(
                context.project,
                context.project.segments,
                translated=False,
                stage=self.stage,
            )
            output = output_path.relative_to(context.project.work_dir).as_posix()

            import logging
            logging.getLogger(__name__).info(
                "regroup: %d фрагментов → %d предложений (max_slot=%.1f)",
                before, after, context.project.config.regroup_max_slot,
            )
            return [], [output]

        return self._record(context, action)


class TranslateStage(BaseStage):
    """Переводит исходные сегменты на настроенный целевой язык."""

    stage = Stage.TRANSLATE

    def __init__(self, translator: Translator) -> None:
        self.translator = translator

    def run(self, context: StageContext) -> StageRun:
        def action() -> tuple[list[str], list[str]]:
            source_transcript = _required_artifact(context, ArtifactKind.SOURCE_TRANSCRIPT)
            if not context.project.segments:
                raise ValueError("исходный transcript не содержит сегментов")
            translated_segments = self.translator.translate(
                context.project.segments,
                context.project.config,
            )
            for segment in translated_segments:
                segment.status = SegmentStatus.TRANSLATED
            output_path = context.store.save_segments(
                context.project,
                translated_segments,
                translated=True,
                stage=self.stage,
            )
            output = output_path.relative_to(context.project.work_dir).as_posix()
            return [source_transcript.path], [output]

        return self._record(context, action)


class TimingFitStage(BaseStage):
    """Адаптирует перевод под естественную озвучку до TTS."""

    stage = Stage.TIMING_FIT

    def __init__(self, timing_fitter: TimingFitter) -> None:
        self.timing_fitter = timing_fitter

    def run(self, context: StageContext) -> StageRun:
        def action() -> tuple[list[str], list[str]]:
            translated_transcript = _required_artifact(
                context,
                ArtifactKind.TRANSLATED_TRANSCRIPT,
            )
            if not context.project.segments:
                raise ValueError("переведенный transcript не содержит сегментов")
            segments = self.timing_fitter.fit(context.project, context.project.segments)
            context.project.segments = segments
            output_path = context.store.save_segments(
                context.project,
                segments,
                translated=True,
                stage=self.stage,
            )
            output = output_path.relative_to(context.project.work_dir).as_posix()
            return [translated_transcript.path], [output]

        return self._record(context, action)


class TTSStage(BaseStage):
    """Синтезирует переведенную речь для переведенных сегментов."""

    stage = Stage.TTS

    def __init__(self, tts_provider: TTSProvider) -> None:
        self.tts_provider = tts_provider

    def run(self, context: StageContext) -> StageRun:
        def action() -> tuple[list[str], list[str]]:
            translated_transcript = _required_artifact(
                context,
                ArtifactKind.TRANSLATED_TRANSCRIPT,
            )
            if not context.project.segments:
                raise ValueError("переведенный transcript не содержит сегментов")
            segments = self.tts_provider.synthesize(context.project, context.project.segments)
            for segment in segments:
                segment.status = SegmentStatus.TTS_READY
            context.project.segments = segments
            tts_outputs = [segment.tts_path for segment in segments if segment.tts_path]
            if not tts_outputs:
                raise ValueError("tts-провайдер не создал аудио сегментов")
            context.store.add_artifact(
                context.project,
                kind=ArtifactKind.TTS_AUDIO,
                path=context.project.work_dir / "tts",
                stage=self.stage,
                content_type="inode/directory",
                metadata={"segments": len(tts_outputs)},
            )
            context.store.save_project(context.project)
            return [translated_transcript.path], tts_outputs

        return self._record(context, action)


class RenderStage(BaseStage):
    """Рендерит итоговый медиа-артефакт."""

    stage = Stage.RENDER

    def __init__(self, renderer: Renderer) -> None:
        self.renderer = renderer

    def run(self, context: StageContext) -> StageRun:
        def action() -> tuple[list[str], list[str]]:
            translated_transcript = _required_artifact(
                context,
                ArtifactKind.TRANSLATED_TRANSCRIPT,
            )
            tts_audio = _required_artifact(context, ArtifactKind.TTS_AUDIO)
            output_path = self.renderer.render(context.project, context.project.segments)
            record = context.store.add_artifact(
                context.project,
                kind=ArtifactKind.OUTPUT_VIDEO,
                path=output_path,
                stage=self.stage,
                content_type="video/mp4",
            )
            return [translated_transcript.path, tts_audio.path], [record.path]

        return self._record(context, action)


def _required_artifact(context: StageContext, kind: ArtifactKind):
    record = context.store.get_artifact(context.project, kind)
    if record is None:
        raise ValueError(f"обязательный артефакт отсутствует: {kind.value}")
    return record
