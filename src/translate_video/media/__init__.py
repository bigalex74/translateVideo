"""Интерфейсы медиа-сервисов."""

from translate_video.media.base import MediaProvider
from translate_video.media.legacy import LegacyMoviePyMediaProvider

__all__ = ["LegacyMoviePyMediaProvider", "MediaProvider"]
