"""Контракты провайдеров финального рендера."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from translate_video.core.schemas import Segment, VideoProject


class Renderer(Protocol):
    """Создает итоговые видео/аудио выходы проекта."""

    def render(self, project: VideoProject, segments: list[Segment]) -> Path:
        """Создать итоговый артефакт и вернуть путь к нему."""
