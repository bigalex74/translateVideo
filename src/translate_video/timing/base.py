"""Контракты подгонки перевода под тайминг естественной речи."""

from __future__ import annotations

from typing import Protocol

from translate_video.core.schemas import Segment, VideoProject


class TimingFitter(Protocol):
    """Адаптирует переведённые сегменты до TTS без ускорения голоса."""

    def fit(self, project: VideoProject, segments: list[Segment]) -> list[Segment]:
        """Вернуть сегменты с текстом, подготовленным под естественную озвучку."""


class TimingRewriter(Protocol):
    """Переписывает одну фразу под ограничение длительности."""

    def rewrite(
        self,
        text: str,
        *,
        source_text: str,
        max_chars: int,
        attempt: int,
    ) -> str:
        """Вернуть более короткую фразу или исходный текст, если сокращение рискованно."""
