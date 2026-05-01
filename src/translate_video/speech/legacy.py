"""faster-whisper адаптер распознавания речи."""

from __future__ import annotations

import os

from translate_video.core.log import Timer, get_logger
from translate_video.core.schemas import Segment

_log = get_logger(__name__)


class FasterWhisperTranscriber:
    """Распознает аудио через `faster-whisper` и возвращает сегменты ядра."""

    def __init__(
        self,
        model_size: str = "base",
        model_factory=None,
        cpu_threads: int | None = None,
    ) -> None:
        self.model_size = model_size
        self.model_factory = model_factory or _whisper_model
        self.cpu_threads = cpu_threads or os.cpu_count()

    def transcribe(self, audio_path, config):
        """Распознать аудио и сохранить таймкоды сегментов."""

        _log.info("transcribe.start", model=self.model_size, audio=str(audio_path))

        with Timer() as t:
            model = self.model_factory(
                self.model_size,
                device="cpu",
                compute_type="int8",
                cpu_threads=self.cpu_threads,
            )
            whisper_segments, info = model.transcribe(str(audio_path), beam_size=5)
            segments: list[Segment] = []
            for index, item in enumerate(whisper_segments):
                text = item.text.strip()
                if not text:
                    continue
                segments.append(
                    Segment(
                        id=f"seg_{index + 1}",
                        start=float(item.start),
                        end=float(item.end),
                        source_text=text,
                        confidence=getattr(item, "avg_logprob", None),
                    )
                )

        language = getattr(info, "language", "?")
        duration = getattr(info, "duration", None)
        _log.info(
            "transcribe.done",
            elapsed_s=t.elapsed,
            segments=len(segments),
            language=language,
            audio_duration_s=round(duration, 1) if duration else None,
            model=self.model_size,
            cpu_threads=self.cpu_threads,
        )
        if duration and t.elapsed > duration * 5:
            _log.warning(
                "transcribe.slow",
                elapsed_s=t.elapsed,
                audio_duration_s=round(duration, 1),
                ratio=round(t.elapsed / duration, 1),
                hint="Нет GPU — рассмотрите модель 'tiny' или 'base' вместо 'large'",
            )
        return segments


def _whisper_model(*args, **kwargs):
    """Лениво импортировать `faster-whisper`."""

    from faster_whisper import WhisperModel

    return WhisperModel(*args, **kwargs)
