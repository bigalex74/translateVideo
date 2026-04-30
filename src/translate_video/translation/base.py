"""Контракты провайдеров перевода."""

from __future__ import annotations

from typing import Protocol

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment


class Translator(Protocol):
    """Переводит исходные сегменты согласно конфигурации проекта."""

    def translate(self, segments: list[Segment], config: PipelineConfig) -> list[Segment]:
        """Вернуть переведенные сегменты, сохранив тайминги и ID."""
