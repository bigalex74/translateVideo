"""faster-whisper адаптер распознавания речи."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from translate_video.core.log import Timer, get_logger
from translate_video.core.schemas import Segment

if TYPE_CHECKING:
    from translate_video.speech.base import ProgressCallback

_log = get_logger(__name__)

# Минимальный интервал между вызовами progress_callback (в секундах аудио).
# При 1800 сегментах и 0.5с интервале — ~3600 вызовов: приемлемо.
_PROGRESS_INTERVAL_S = 5.0


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

    def transcribe(
        self,
        audio_path: Path | str,
        config,
        progress_callback: "ProgressCallback | None" = None,
    ) -> list[Segment]:
        """Распознать аудио и вернуть сегменты с таймкодами.

        progress_callback(current_sec, total_sec, message) вызывается
        каждые ~5 секунд аудио по мере обработки генератором Whisper.
        """

        _log.info("transcribe.start", model=self.model_size, audio=str(audio_path))

        with Timer() as t:
            model = self.model_factory(
                self.model_size,
                device="cpu",
                compute_type="int8",
                cpu_threads=self.cpu_threads,
            )
            # transcribe() возвращает (generator, TranscriptionInfo)
            # Генератор — ленивый: сегменты появляются по мере обработки аудио.
            whisper_segments, info = model.transcribe(str(audio_path), beam_size=5)
            total_sec = int(getattr(info, "duration", 0) or 0)

            segments: list[Segment] = []
            _last_reported: float = -_PROGRESS_INTERVAL_S

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
                # Прогресс: репортим каждые _PROGRESS_INTERVAL_S секунд аудио
                if progress_callback and total_sec > 0:
                    current_sec = int(item.end)
                    if current_sec - _last_reported >= _PROGRESS_INTERVAL_S:
                        _last_reported = current_sec
                        progress_callback(
                            min(current_sec, total_sec),
                            total_sec,
                            f"Транскрипция: {current_sec // 60}:{current_sec % 60:02d} / "
                            f"{total_sec // 60}:{total_sec % 60:02d}",
                        )

            # Финальный вызов — 100%
            if progress_callback and total_sec > 0:
                progress_callback(total_sec, total_sec, "Транскрипция завершена")

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

    from faster_whisper import WhisperModel  # noqa: PLC0415

    return WhisperModel(*args, **kwargs)
