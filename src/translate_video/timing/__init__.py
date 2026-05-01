"""Провайдеры подгонки таймингов под естественную озвучку."""

from translate_video.timing.base import TimingFitter, TimingRewriter
from translate_video.timing.natural import NaturalVoiceTimingFitter, RuleBasedTimingRewriter

__all__ = [
    "NaturalVoiceTimingFitter",
    "RuleBasedTimingRewriter",
    "TimingFitter",
    "TimingRewriter",
]
