"""Контракты провайдеров синтеза речи."""

from __future__ import annotations

from typing import Protocol

from translate_video.core.schemas import Segment, VideoProject


class TTSProvider(Protocol):
    """Синтезирует переведенные сегменты и обновляет их метаданные."""

    def synthesize(self, project: VideoProject, segments: list[Segment]) -> list[Segment]:
        """Сгенерировать аудиофайлы и вернуть сегменты с заполненным `tts_path`."""
