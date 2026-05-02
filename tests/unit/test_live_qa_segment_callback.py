"""TVIDEO-078: тесты live QA — segment_callback вызывается после каждого сегмента.

Проверяет:
- CloudFallbackSegmentTranslator передаёт segment_callback в translate()
- segment_callback вызывается после каждого переведённого сегмента
- Исключение в segment_callback не прерывает перевод
- Если segment_callback не передан — работает без него (обратная совместимость)
- _translate_with_progress в stages.py пробрасывает segment_callback
"""
import unittest
from unittest.mock import MagicMock, call, patch
from translate_video.core.schemas import Segment, SegmentStatus


def _make_segment(idx: int, text: str = "Hello") -> Segment:
    return Segment(
        id=f"seg_{idx}",
        start=float(idx),
        end=float(idx + 1),
        source_text=text,
        status=SegmentStatus.TRANSCRIBED,
    )


class SegmentCallbackTranslateWithProgress(unittest.TestCase):
    """_translate_with_progress пробрасывает segment_callback в translator."""

    def test_segment_callback_forwarded(self):
        """segment_callback пробрасывается в translator.translate()."""
        from translate_video.pipeline.stages import _translate_with_progress

        translator = MagicMock()
        translator.translate.return_value = [_make_segment(0)]
        segs = [_make_segment(0)]
        seg_cb = MagicMock()
        prog_cb = MagicMock()

        _translate_with_progress(
            translator,
            segs,
            config=MagicMock(),
            progress_callback=prog_cb,
            segment_callback=seg_cb,
        )

        translator.translate.assert_called_once()
        _, kwargs = translator.translate.call_args
        self.assertEqual(kwargs.get("segment_callback"), seg_cb)

    def test_segment_callback_none_by_default(self):
        """Без segment_callback работает без ошибок (обратная совместимость)."""
        from translate_video.pipeline.stages import _translate_with_progress

        translator = MagicMock()
        translator.translate.return_value = [_make_segment(0)]

        result = _translate_with_progress(
            translator,
            [_make_segment(0)],
            config=MagicMock(),
            progress_callback=MagicMock(),
        )

        self.assertEqual(len(result), 1)


class SegmentCallbackCloudTranslator(unittest.TestCase):
    """CloudFallbackSegmentTranslator вызывает segment_callback после каждого сегмента."""

    def _make_translator(self, provider_result):
        """Создать CloudFallbackSegmentTranslator с мок-провайдером."""
        from translate_video.translation.cloud import CloudFallbackSegmentTranslator
        from unittest.mock import patch

        translator = CloudFallbackSegmentTranslator.__new__(CloudFallbackSegmentTranslator)
        # Устанавливаем атрибуты вручную (без __init__)
        translator.providers = [MagicMock()]
        translator.allow_fallback = False
        translator._current_index = 0
        translator._dev_log = MagicMock()

        # Патчим _translate_one чтобы возвращал результат
        translator._translate_one = MagicMock(return_value=provider_result)
        return translator

    def test_segment_callback_called_for_each_segment(self):
        """segment_callback вызывается после каждого сегмента."""
        from translate_video.translation.cloud import CloudFallbackSegmentTranslator, TranslationProviderResult

        provider_result = TranslationProviderResult(text="Привет", provider="test")
        translator = self._make_translator(provider_result)

        segs = [_make_segment(i, f"Hello {i}") for i in range(3)]
        seg_cb = MagicMock()
        config = MagicMock()

        with patch("translate_video.translation.cloud.context_window", return_value=([], [])):
            translator.translate(segs, config, segment_callback=seg_cb)

        self.assertEqual(seg_cb.call_count, 3, "segment_callback должен быть вызван для каждого сегмента")

    def test_segment_callback_exception_does_not_stop_translation(self):
        """Исключение в segment_callback не прерывает перевод."""
        from translate_video.translation.cloud import CloudFallbackSegmentTranslator, TranslationProviderResult

        provider_result = TranslationProviderResult(text="Привет", provider="test")
        translator = self._make_translator(provider_result)

        segs = [_make_segment(i) for i in range(3)]

        def bad_callback(seg):
            raise RuntimeError("callback error")

        config = MagicMock()

        with patch("translate_video.translation.cloud.context_window", return_value=([], [])):
            # Не должно бросить исключение
            result = translator.translate(segs, config, segment_callback=bad_callback)

        self.assertEqual(len(result), 3, "Все сегменты должны быть переведены несмотря на ошибку callback")

    def test_no_segment_callback_works(self):
        """Без segment_callback перевод работает штатно."""
        from translate_video.translation.cloud import CloudFallbackSegmentTranslator, TranslationProviderResult

        provider_result = TranslationProviderResult(text="Привет", provider="test")
        translator = self._make_translator(provider_result)
        segs = [_make_segment(0)]
        config = MagicMock()

        with patch("translate_video.translation.cloud.context_window", return_value=([], [])):
            result = translator.translate(segs, config)

        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
