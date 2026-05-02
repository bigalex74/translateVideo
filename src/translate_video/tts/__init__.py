"""Интерфейсы TTS-сервисов."""

from translate_video.tts.base import TTSProvider
from translate_video.tts.legacy import EdgeTTSProvider
from translate_video.tts.openai_tts import OpenAITTSProvider, TTS_VOICES, build_openai_tts_provider
from translate_video.tts.speechkit_tts import SPEECHKIT_VOICES, YandexSpeechKitTTSProvider, build_speechkit_tts_provider

__all__ = [
    "EdgeTTSProvider",
    "OpenAITTSProvider",
    "TTS_VOICES",
    "TTSProvider",
    "SPEECHKIT_VOICES",
    "YandexSpeechKitTTSProvider",
    "build_openai_tts_provider",
    "build_speechkit_tts_provider",
]
