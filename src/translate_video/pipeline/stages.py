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
        action: Callable[[StageRun], tuple[list[str], list[str]]],
    ) -> StageRun:
        project_id = context.project.id
        stage_name = self.stage.value

        started_at = datetime.now(UTC).isoformat()
        run = StageRun(stage=self.stage, status=JobStatus.RUNNING, started_at=started_at)
        context.store.record_stage_run(context.project, run)

        _log.info("stage.start", stage=stage_name, project=project_id)

        with Timer() as t:
            try:
                inputs, outputs = action(run)
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
                    progress_current=run.progress_current,
                    progress_total=run.progress_total,
                    progress_message=run.progress_message,
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
            progress_current=run.progress_current,
            progress_total=run.progress_total,
            progress_message=run.progress_message,
            metadata=dict(run.metadata),   # переносим metadata, накопленное action()
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
        def action(_run: StageRun) -> tuple[list[str], list[str]]:
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
    """Создает исходные сегменты расшифровки из извлечённого аудио.

    После успешной транскрипции source_audio.wav удаляется
    (аудио больше не нужно — сегменты уже сохранены в transcript.source.json).
    """

    stage = Stage.TRANSCRIBE

    def __init__(self, transcriber: Transcriber) -> None:
        self.transcriber = transcriber

    def run(self, context: StageContext) -> StageRun:
        def action(run: StageRun) -> tuple[list[str], list[str]]:
            source_audio = _required_artifact(context, ArtifactKind.SOURCE_AUDIO)
            raw_path = Path(source_audio.path)
            if raw_path.is_absolute():
                audio_path = raw_path
            else:
                candidate = (context.project.work_dir / raw_path).resolve()
                if not candidate.exists():
                    audio_path = context.project.work_dir.resolve() / raw_path.name
                else:
                    audio_path = candidate

            def on_progress(current: int, total: int, message: str | None) -> None:
                """Прогресс транскрипции (единицы — секунды аудио)."""
                run.progress_current = current
                run.progress_total = total
                run.progress_message = message
                context.store.update_stage_progress(
                    context.project,
                    run.id,
                    current=current,
                    total=total,
                    message=message,
                )

            segments = self.transcriber.transcribe(
                audio_path,
                context.project.config,
                progress_callback=on_progress,
            )
            for segment in segments:
                segment.status = SegmentStatus.TRANSCRIBED
            output_path = context.store.save_segments(context.project, segments, translated=False)
            output = output_path.relative_to(context.project.work_dir).as_posix()

            # Удаляем WAV: транскрипция завершена, файл больше не нужен.
            try:
                if audio_path.exists():
                    audio_path.unlink()
                    _log.info("transcribe.wav_deleted", path=str(audio_path))
                    # Убираем запись source_audio из артефактов — файл удалён
                    context.project.artifact_records = [
                        r for r in context.project.artifact_records
                        if r.kind != ArtifactKind.SOURCE_AUDIO
                    ]
                    context.project.artifacts.pop(ArtifactKind.SOURCE_AUDIO.value, None)
                    context.store.save_project(context.project)
            except OSError as e:
                _log.warning("transcribe.wav_delete_failed", path=str(audio_path), error=str(e))

            return [source_audio.path], [output]

        return self._record(context, action)





class RegroupStage(BaseStage):
    """Объединяет Whisper-фрагменты в сегменты уровня предложения (TVIDEO-039).

    Запускается после TranscribeStage и до TranslateStage.
    Не обращается к внешним сервисам — только чистая логика.
    """

    stage = Stage.REGROUP

    def run(self, context: StageContext) -> StageRun:
        def action(_run: StageRun) -> tuple[list[str], list[str]]:
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
        def action(run: StageRun) -> tuple[list[str], list[str]]:
            from translate_video.pipeline.runner import PipelineCancelledError
            source_transcript = _required_artifact(context, ArtifactKind.SOURCE_TRANSCRIPT)
            if not context.project.segments:
                raise ValueError("исходный transcript не содержит сегментов")

            # Накапливаем переведённые сегменты для live-обновления.
            partial_translated: list = []

            def on_segment(segment) -> None:
                """Вызывается после каждого переведённого сегмента.

                Обновляет project.segments в памяти и сохраняет на диск чтобы
                UI мог видеть qa_flags в реальном времени через polling.
                """
                partial_translated.append(segment)
                # Обновляем сегменты в памяти: заменяем по индексу
                idx = next(
                    (i for i, s in enumerate(context.project.segments) if s.id == segment.id),
                    None,
                )
                if idx is not None:
                    context.project.segments[idx] = segment
                context.store.save_project(context.project)

            def on_progress(current: int, total: int, message: str | None) -> None:
                """Сохранить прогресс перевода для UI и API-поллинга.

                Проверяем cancel_event после каждого сегмента — отмена
                срабатывает без ожидания окончания всего этапа.
                """

                run.progress_current = current
                run.progress_total = total
                run.progress_message = message
                context.store.update_stage_progress(
                    context.project,
                    run.id,
                    current=current,
                    total=total,
                    message=message,
                )
                # Проверяем флаг отмены после каждого сегмента
                if context.cancel_event.is_set():
                    raise PipelineCancelledError(
                        f"cancel запрошен на сегменте {current}/{total}"
                    )

            translated_segments = _translate_with_progress(
                self.translator,
                context.project.segments,
                context.project.config,
                progress_callback=on_progress,
                segment_callback=on_segment,
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
        def action(run: StageRun) -> tuple[list[str], list[str]]:
            from translate_video.pipeline.runner import PipelineCancelledError
            translated_transcript = _required_artifact(
                context,
                ArtifactKind.TRANSLATED_TRANSCRIPT,
            )
            if not context.project.segments:
                raise ValueError("переведенный transcript не содержит сегментов")

            def on_progress(current: int, total: int, message: str | None) -> None:
                """Сохранить прогресс этапа для UI и API-поллинга."""

                run.progress_current = current
                run.progress_total = total
                run.progress_message = message
                context.store.update_stage_progress(
                    context.project,
                    run.id,
                    current=current,
                    total=total,
                    message=message,
                )
                if context.cancel_event.is_set():
                    raise PipelineCancelledError(
                        f"cancel запрошен на сегменте {current}/{total}"
                    )

            segments = self.timing_fitter.fit(
                context.project,
                context.project.segments,
                progress_callback=on_progress,
            )
            context.project.segments = segments
            output_path = context.store.save_segments(
                context.project,
                segments,
                translated=True,
                stage=self.stage,
            )
            output = output_path.relative_to(context.project.work_dir).as_posix()
            # Сохраняем скорость TTS в metadata чтобы UI мог определить,
            # изменилась ли скорость с момента последнего timing_fit.
            cfg = context.project.config
            run.metadata["tts_speed_1"] = float(getattr(cfg, "professional_tts_speed",   1.0))
            run.metadata["tts_speed_2"] = float(getattr(cfg, "professional_tts_speed_2", 1.0))
            return [translated_transcript.path], [output]

        return self._record(context, action)



class TTSStage(BaseStage):
    """Синтезирует переведенную речь для переведенных сегментов."""

    stage = Stage.TTS

    def __init__(self, tts_provider: TTSProvider) -> None:
        self.tts_provider = tts_provider

    def run(self, context: StageContext) -> StageRun:
        def action(_run: StageRun) -> tuple[list[str], list[str]]:
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
    """Рендерит итоговый медиа-артефакт.

    После успешного рендера MP3-файлы отдельных TTS-сегментов
    удаляются: они уже смонтированы в output_video.
    """

    stage = Stage.RENDER

    def __init__(self, renderer: Renderer) -> None:
        self.renderer = renderer

    def run(self, context: StageContext) -> StageRun:
        def action(_run: StageRun) -> tuple[list[str], list[str]]:
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

            # Удаляем TTS-сегменты: они смонтированы в output_video
            tts_dir = context.project.work_dir / "tts"
            deleted = 0
            try:
                for f in tts_dir.glob("*"):
                    if f.is_file():
                        f.unlink()
                        deleted += 1
                _log.info("render.tts_cleaned", deleted=deleted, dir=str(tts_dir))
            except OSError as e:
                _log.warning("render.tts_clean_failed", error=str(e))

            return [translated_transcript.path, tts_audio.path], [record.path]

        return self._record(context, action)


class ExportSubtitlesStage(BaseStage):
    """Экспортирует субтитры (VTT + SRT) после рендера.

    Гарантирует, что файлы субтитров всегда соответствуют текущему
    translated_text сегментов — и совпадают с тем, что показывает редактор.
    """

    stage = Stage.EXPORT

    def run(self, context: StageContext) -> StageRun:
        def action(_run: StageRun) -> tuple[list[str], list[str]]:
            # Генерируем VTT (для видеоплеера) и SRT (для скачивания)
            vtt_path = context.store.export_subtitles(context.project, fmt="vtt")
            srt_path = context.store.export_subtitles(context.project, fmt="srt")
            return [], [
                vtt_path.relative_to(context.project.work_dir).as_posix(),
                srt_path.relative_to(context.project.work_dir).as_posix(),
            ]

        return self._record(context, action)


class EmbedSubtitlesStage(BaseStage):
    """Встраивает субтитры в выходное видео через ffmpeg.

    Режимы (subtitle_embed_mode в конфиге):
    - "soft" — SRT мультиплексируется как дополнительный трек в MP4.
               Можно включить/выключить в плеере (VLC, mpv, браузер).
    - "burn" — субтитры вжигаются в видеопоток (hardcoded).
               Всегда видны, не зависят от поддержки субтитров в плеере.
    - "none" — этап пропускается.
    """

    stage = Stage.EMBED_SUBTITLES

    def run(self, context: StageContext) -> StageRun:
        def action(_run: StageRun) -> tuple[list[str], list[str]]:
            import subprocess  # noqa: PLC0415

            mode = getattr(context.project.config, "subtitle_embed_mode", "none")
            if mode not in ("soft", "burn"):
                _log.info("embed_subtitles.skip", mode=mode)
                return [], []

            video_rec = _required_artifact(context, ArtifactKind.OUTPUT_VIDEO)
            subs_rec  = _required_artifact(context, ArtifactKind.SUBTITLES)

            video_path = (context.project.work_dir / video_rec.path).resolve()
            subs_path  = (context.project.work_dir / subs_rec.path).resolve()

            # Всегда работаем с SRT — если артефакт указывает на VTT, ищем SRT
            srt_path = subs_path if subs_path.suffix.lower() == ".srt" else (
                context.project.work_dir / "subtitles" / "translated.srt"
            )
            if not srt_path.exists():
                raise FileNotFoundError(f"SRT-файл не найден: {srt_path}")

            output_path = video_path.parent / (video_path.stem + f"_sub_{mode}.mp4")

            if mode == "soft":
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(video_path),
                    "-i", str(srt_path),
                    "-c", "copy",
                    "-c:s", "mov_text",
                    "-metadata:s:s:0",
                    f"language={context.project.config.target_language}",
                    str(output_path),
                ]
            else:  # burn
                safe_srt = str(srt_path).replace("\\", "/").replace(":", "\\:")
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(video_path),
                    "-vf", f"subtitles='{safe_srt}'",
                    "-c:a", "copy",
                    str(output_path),
                ]

            _log.info("embed_subtitles.start", mode=mode, srt=str(srt_path))
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(
                    f"ffmpeg embed_subtitles failed (code {result.returncode}):\n"
                    f"{result.stderr[-2000:]}"
                )

            record = context.store.add_artifact(
                context.project,
                kind=ArtifactKind.OUTPUT_VIDEO_WITH_SUBS,
                path=output_path,
                stage=self.stage,
                content_type="video/mp4",
                metadata={"subtitle_mode": mode},
            )
            _log.info("embed_subtitles.done", mode=mode, output=str(output_path))
            return [video_rec.path, subs_rec.path], [record.path]

        return self._record(context, action)


def _required_artifact(context: StageContext, kind: ArtifactKind):
    record = context.store.get_artifact(context.project, kind)
    if record is None:
        raise ValueError(f"обязательный артефакт отсутствует: {kind.value}")
    return record


def _translate_with_progress(translator, segments, config, *, progress_callback, segment_callback=None):
    """Вызвать переводчик с прогрессом, сохранив совместимость со старыми адаптерами.

    segment_callback(segment) — вызывается после каждого переведённого сегмента
    для live-обновления qa_flags в UI через polling.
    """

    try:
        return translator.translate(
            segments,
            config,
            progress_callback=progress_callback,
            segment_callback=segment_callback,
        )
    except TypeError as exc:
        if "unexpected keyword" not in str(exc):
            raise
        # Старый адаптер не принимает keyword-аргументы — fallback без live QA.
        progress_callback(0, len(segments), "Перевод сегментов")
        result = translator.translate(segments, config)
        progress_callback(len(segments), len(segments), "Перевод готов")
        return result
