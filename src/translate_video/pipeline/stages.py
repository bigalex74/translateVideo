"""Provider-backed pipeline stages."""

from __future__ import annotations

from datetime import UTC, datetime
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


class BaseStage:
    """Base implementation for recording success/failure consistently."""

    stage: Stage

    def _record(
        self,
        context: StageContext,
        action: Callable[[], tuple[list[str], list[str]]],
    ) -> StageRun:
        started_at = datetime.now(UTC).isoformat()
        run = StageRun(stage=self.stage, status=JobStatus.RUNNING, started_at=started_at)
        context.store.record_stage_run(context.project, run)
        try:
            inputs, outputs = action()
        except Exception as exc:  # noqa: BLE001 - stage errors must be persisted.
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
        return completed


class ExtractAudioStage(BaseStage):
    """Extract source audio from the input video."""

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
    """Create source transcript segments from extracted audio."""

    stage = Stage.TRANSCRIBE

    def __init__(self, transcriber: Transcriber) -> None:
        self.transcriber = transcriber

    def run(self, context: StageContext) -> StageRun:
        def action() -> tuple[list[str], list[str]]:
            source_audio = _required_artifact(context, ArtifactKind.SOURCE_AUDIO)
            audio_path = context.project.work_dir / source_audio.path
            segments = self.transcriber.transcribe(audio_path, context.project.config)
            for segment in segments:
                segment.status = SegmentStatus.TRANSCRIBED
            output_path = context.store.save_segments(context.project, segments, translated=False)
            output = output_path.relative_to(context.project.work_dir).as_posix()
            return [source_audio.path], [output]

        return self._record(context, action)


class TranslateStage(BaseStage):
    """Translate source segments into the configured target language."""

    stage = Stage.TRANSLATE

    def __init__(self, translator: Translator) -> None:
        self.translator = translator

    def run(self, context: StageContext) -> StageRun:
        def action() -> tuple[list[str], list[str]]:
            source_transcript = _required_artifact(context, ArtifactKind.SOURCE_TRANSCRIPT)
            if not context.project.segments:
                raise ValueError("source transcript has no segments")
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
            )
            output = output_path.relative_to(context.project.work_dir).as_posix()
            return [source_transcript.path], [output]

        return self._record(context, action)


class TTSStage(BaseStage):
    """Synthesize translated speech for translated segments."""

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
                raise ValueError("translated transcript has no segments")
            segments = self.tts_provider.synthesize(context.project, context.project.segments)
            for segment in segments:
                segment.status = SegmentStatus.TTS_READY
            context.project.segments = segments
            tts_outputs = [segment.tts_path for segment in segments if segment.tts_path]
            if not tts_outputs:
                raise ValueError("tts provider did not create any segment audio")
            context.store.add_artifact(
                context.project,
                kind=ArtifactKind.TTS_AUDIO,
                path="tts",
                stage=self.stage,
                content_type="inode/directory",
                metadata={"segments": len(tts_outputs)},
            )
            context.store.save_project(context.project)
            return [translated_transcript.path], tts_outputs

        return self._record(context, action)


class RenderStage(BaseStage):
    """Render the final output media artifact."""

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
        raise ValueError(f"required artifact is missing: {kind.value}")
    return record
