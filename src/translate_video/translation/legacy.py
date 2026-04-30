"""deep-translator адаптер перевода сегментов."""

from __future__ import annotations

from translate_video.core.schemas import Segment


class GoogleSegmentTranslator:
    """Переводит сегменты через `deep-translator` GoogleTranslator."""

    def __init__(self, translator_factory=None) -> None:
        self.translator_factory = translator_factory or _google_translator

    def translate(self, segments, config):
        """Перевести непустые сегменты на целевой язык проекта."""

        translator = self.translator_factory(
            source=config.source_language,
            target=config.target_language,
        )
        translated_segments: list[Segment] = []
        for segment in segments:
            text = segment.source_text.strip()
            translated_text = translator.translate(text) if text else ""
            translated_segments.append(
                Segment(
                    id=segment.id,
                    start=segment.start,
                    end=segment.end,
                    source_text=segment.source_text,
                    translated_text=translated_text,
                    speaker_id=segment.speaker_id,
                    confidence=segment.confidence,
                )
            )
        return translated_segments


def _google_translator(*args, **kwargs):
    """Лениво импортировать `deep-translator`."""

    from deep_translator import GoogleTranslator

    return GoogleTranslator(*args, **kwargs)
