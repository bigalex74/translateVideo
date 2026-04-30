"""Интерфейсы сервисов распознавания речи."""

from translate_video.speech.base import Transcriber
from translate_video.speech.legacy import FasterWhisperTranscriber

__all__ = ["FasterWhisperTranscriber", "Transcriber"]
