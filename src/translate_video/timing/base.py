"""Контракты подгонки перевода под тайминг естественной речи."""

from __future__ import annotations

from typing import Callable, Protocol

from translate_video.core.schemas import Segment, VideoProject

TimingProgressCallback = Callable[[int, int, str | None], None]


class TimingFitter(Protocol):
    """Адаптирует переведённые сегменты до TTS без ускорения голоса."""

    def fit(
        self,
        project: VideoProject,
        segments: list[Segment],
        progress_callback: TimingProgressCallback | None = None,
    ) -> list[Segment]:
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
        segment: Segment | None = None,
        context_before: list[Segment] | None = None,
        context_after: list[Segment] | None = None,
        config=None,
    ) -> str:
        """Вернуть более короткую фразу или исходный текст, если сокращение рискованно."""
