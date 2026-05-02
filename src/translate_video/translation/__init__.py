"""Интерфейсы сервисов перевода."""

from translate_video.translation.base import Translator
from translate_video.translation.cloud import CloudFallbackSegmentTranslator
from translate_video.translation.legacy import GoogleSegmentTranslator

__all__ = ["CloudFallbackSegmentTranslator", "GoogleSegmentTranslator", "Translator"]
