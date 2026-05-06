"""Контракты провайдеров распознавания речи."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment

# (current_sec: int, total_sec: int, message: str | None) -> None
ProgressCallback = Callable[[int, int, "str | None"], None]


class Transcriber(Protocol):
    """Преобразует аудиофайл в сегменты исходного языка с таймкодами."""

    def transcribe(
        self,
        audio_path: Path,
        config: PipelineConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> list[Segment]:
        """Вернуть исходные сегменты для аудио-артефакта.

        progress_callback(current_sec, total_sec, message) вызывается
        по мере обработки аудио (единицы — секунды аудио, не сегменты).
        """
