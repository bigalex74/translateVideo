"""Контракты провайдеров распознавания речи."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment


class Transcriber(Protocol):
    """Преобразует аудиофайл в сегменты исходного языка с таймкодами."""

    def transcribe(self, audio_path: Path, config: PipelineConfig) -> list[Segment]:
        """Вернуть исходные сегменты для аудио-артефакта."""
