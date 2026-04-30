"""Контракты медиа-провайдеров, используемые этапами пайплайна."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from translate_video.core.schemas import VideoProject


class MediaProvider(Protocol):
    """Извлекает исходное аудио из входного видео."""

    def extract_audio(self, project: VideoProject) -> Path:
        """Создать артефакт исходного аудио и вернуть путь к нему."""
