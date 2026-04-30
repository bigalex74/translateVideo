"""Интерфейсы сервисов рендера."""

from translate_video.render.base import Renderer
from translate_video.render.legacy import MoviePyVoiceoverRenderer

__all__ = ["MoviePyVoiceoverRenderer", "Renderer"]
