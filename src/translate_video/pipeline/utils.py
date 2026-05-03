"""Публичные утилиты пайплайна: сборка этапов и сводка проекта."""

from __future__ import annotations

from typing import Any

from translate_video.core.schemas import Segment, VideoProject
from translate_video.pipeline import (
    ExtractAudioStage,
    PipelineRunner,  # noqa: F401 — переэкспорт для удобства
    RegroupStage,
    RenderStage,
    ExportSubtitlesStage,
    TTSStage,
    TimingFitStage,
    TranscribeStage,
    TranslateStage,
)


class FakeMediaProvider:
    """Имитационный медиа-провайдер без внешних зависимостей."""

    stage = None  # присваивается в ExtractAudioStage

    def extract_audio(self, project: VideoProject):
        """Создать минимальный аудио-артефакт."""
        output = project.work_dir / "source_audio.wav"
        output.write_bytes(b"fake audio")
        return output


class FakeTranscriber:
    """Имитационный распознаватель для дымовых сценариев."""

    def transcribe(self, audio_path, config, progress_callback=None):
        """Вернуть один сегмент без обращения к внешним моделям."""
        return [Segment(id="seg_1", start=0.0, end=1.0, source_text="Пример речи")]


class FakeTranslator:
    """Имитационный переводчик с детерминированным поведением."""

    def translate(self, segments, config):
        """Вернуть сегменты с текстом, помеченным целевым языком."""
        return [
            Segment(
                id=segment.id,
                start=segment.start,
                end=segment.end,
                source_text=segment.source_text,
                translated_text=f"{config.target_language}: {segment.source_text}",
            )
            for segment in segments
        ]


class FakeTTSProvider:
    """Имитационный TTS-провайдер для создания локальных аудио-файлов."""

    def synthesize(self, project: VideoProject, segments):
        """Записать минимальные TTS-файлы и обновить пути сегментов."""
        for segment in segments:
            tts_path = project.work_dir / "tts" / f"{segment.id}.wav"
            tts_path.write_bytes(b"fake speech")
            segment.tts_path = tts_path.relative_to(project.work_dir).as_posix()
        return segments


class FakeTimingFitter:
    """Имитационная подгонка таймингов без изменения текста."""

    def fit(self, project: VideoProject, segments, progress_callback=None):
        """Заполнить tts_text для smoke-тестов."""

        total = len(segments)
        if progress_callback is not None:
            progress_callback(0, total, "Подготовка сегментов")
        for segment in segments:
            segment.tts_text = segment.translated_text
        if progress_callback is not None:
            progress_callback(total, total, f"Готово {total}/{total}")
        return segments


class FakeRenderer:
    """Имитационный рендерер для создания итогового видео-артефакта."""

    def render(self, project: VideoProject, segments):
        """Записать минимальный итоговый файл."""
        output = project.work_dir / "output" / "translated.mp4"
        output.write_bytes(b"fake video")
        return output


def build_stages(provider: str, project_config=None) -> list:
    """Создать этапы пайплайна для выбранного набора провайдеров.

    Поддерживаемые провайдеры:
    - ``fake`` — имитационные провайдеры без внешних зависимостей.
    - ``legacy`` — реальные провайдеры (moviepy, faster-whisper, edge-tts).
    ``project_config`` — PipelineConfig проекта (нужен для выбора TTS-провайдера).
    """
    if provider == "fake":
        return [
            ExtractAudioStage(FakeMediaProvider()),
            TranscribeStage(FakeTranscriber()),
            RegroupStage(),
            TranslateStage(FakeTranslator()),
            TimingFitStage(FakeTimingFitter()),
            TTSStage(FakeTTSProvider()),
            RenderStage(FakeRenderer()),
            ExportSubtitlesStage(),
        ]
    if provider == "legacy":
        from translate_video.media import LegacyMoviePyMediaProvider
        from translate_video.render import MoviePyVoiceoverRenderer
        from translate_video.speech import FasterWhisperTranscriber
        from translate_video.timing import NaturalVoiceTimingFitter
        from translate_video.translation import CloudFallbackSegmentTranslator, GoogleSegmentTranslator
        from translate_video.tts import EdgeTTSProvider, build_openai_tts_provider, build_speechkit_tts_provider

        # Профессиональный TTS: Yandex SpeechKit → OpenAI-совместимый → Edge TTS (бесплатный)
        tts_provider = None
        if project_config is not None:
            tts_provider = (
                build_speechkit_tts_provider(project_config)
                or build_openai_tts_provider(project_config)
            )
        tts_provider = tts_provider or EdgeTTSProvider()

        return [
            ExtractAudioStage(LegacyMoviePyMediaProvider()),
            TranscribeStage(FasterWhisperTranscriber()),
            RegroupStage(),
            TranslateStage(CloudFallbackSegmentTranslator(fallback=GoogleSegmentTranslator())),
            TimingFitStage(NaturalVoiceTimingFitter()),
            TTSStage(tts_provider),
            RenderStage(MoviePyVoiceoverRenderer()),
            ExportSubtitlesStage(),
        ]
    raise ValueError(f"неподдерживаемый провайдер: {provider!r}")


def project_summary(project: VideoProject) -> dict[str, Any]:
    """Вернуть короткое JSON-представление проекта для CLI и API."""
    return {
        "project_id": project.id,
        "status": project.status,
        "input_video": project.input_video.as_posix(),
        "work_dir": project.work_dir.as_posix(),
        "segments": len(project.segments),
        "artifacts": dict(project.artifacts),
    }
