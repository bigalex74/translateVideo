"""Интерфейсы TTS-сервисов."""

from translate_video.tts.base import TTSProvider
from translate_video.tts.legacy import EdgeTTSProvider

__all__ = ["EdgeTTSProvider", "TTSProvider"]
