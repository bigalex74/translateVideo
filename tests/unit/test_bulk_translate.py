"""Тесты перевода единым текстом (TVIDEO-029c, заменяет TVIDEO-027 bulk).

Покрывает:
- Единый текст → 1 API-запрос
- Жадное выравнивание переведённых предложений по сегментам
- Батчинг при превышении MAX_CHARS
- Fallback на поштучный перевод
- Сохранение тайминга и ID
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from translate_video.core.schemas import Segment
from translate_video.translation.legacy import (
    GoogleSegmentTranslator,
    _align_translation,
    _split_sentences,
    _make_batches,
    _MAX_CHARS,
)


def _seg(source: str, start: float = 0.0, end: float = 1.0) -> Segment:
    return Segment(start=start, end=end, source_text=source)


# ─── _split_sentences ────────────────────────────────────────────────────────

class TestSplitSentences(unittest.TestCase):

    def test_single_sentence(self):
        result = _split_sentences("Привет мир.")
        self.assertEqual(result, ["Привет мир."])

    def test_multiple_sentences(self):
        result = _split_sentences("Первое. Второе. Третье.")
        self.assertEqual(len(result), 3)

    def test_question_exclamation(self):
        result = _split_sentences("Как дела? Хорошо! Спасибо.")
        self.assertEqual(len(result), 3)

    def test_empty_string(self):
        result = _split_sentences("")
        self.assertEqual(result, [])

    def test_strips_whitespace(self):
        result = _split_sentences("  Привет.  Мир.  ")
        for s in result:
            self.assertEqual(s, s.strip())


# ─── _align_translation ──────────────────────────────────────────────────────

class TestAlignTranslation(unittest.TestCase):

    def test_align_two_segs_two_sentences(self):
        """2 сегмента + 2 предложения → каждому по предложению."""
        segs = [
            _seg("Hello world how are you", 0.0, 2.0),
            _seg("I am fine thank you", 2.0, 4.0),
        ]
        translated = "Привет мир как дела. Я в порядке спасибо."
        result = _align_translation(translated, segs)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        self.assertIn("Привет", result[0])
        self.assertIn("порядке", result[1])

    def test_last_segment_gets_remainder(self):
        """Последний сегмент всегда получает оставшийся текст (не пустой)."""
        segs = [_seg("Short"), _seg("Also short")]
        translated = "Короткий. Тоже короткий. Ещё что-то лишнее."
        result = _align_translation(translated, segs)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)
        # Последний должен быть непустым
        self.assertTrue(result[1].strip(), "последний сегмент не должен быть пустым")

    def test_returns_none_for_empty_translation(self):
        segs = [_seg("Hello")]
        result = _align_translation("", segs)
        self.assertIsNone(result)

    def test_single_segment_gets_all(self):
        """Один сегмент → весь переведённый текст."""
        segs = [_seg("Everything here")]
        translated = "Всё здесь. Включая это. И это тоже."
        result = _align_translation(translated, segs)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertGreater(len(result[0]), 0)


# ─── _make_batches ────────────────────────────────────────────────────────────

class TestMakeBatches(unittest.TestCase):

    def test_small_input_one_batch(self):
        segs = [_seg("A"), _seg("B"), _seg("C")]
        batches = _make_batches(segs)
        self.assertEqual(len(batches), 1)

    def test_large_input_multiple_batches(self):
        long_text = "x" * 1000
        segs = [_seg(long_text) for _ in range(10)]
        batches = _make_batches(segs)
        self.assertGreater(len(batches), 1)

    def test_all_segments_in_batches(self):
        segs = [_seg("word") for _ in range(20)]
        batches = _make_batches(segs)
        total = sum(len(b) for b in batches)
        self.assertEqual(total, 20)


# ─── GoogleSegmentTranslator ─────────────────────────────────────────────────

class TestGoogleSegmentTranslator(unittest.TestCase):

    def _make_translator(self, response: str):
        mock_api = MagicMock()
        mock_api.translate.return_value = response

        def factory(source, target):
            return mock_api

        self._mock_api = mock_api
        return GoogleSegmentTranslator(translator_factory=factory)

    def _config(self):
        cfg = MagicMock()
        cfg.source_language = "en"
        cfg.target_language = "ru"
        return cfg

    def test_single_api_call_for_multiple_segments(self):
        """N сегментов → 1 вызов API (единый текст)."""
        translator = self._make_translator(
            "Привет мир. Я в порядке. Пока."
        )
        segs = [_seg("Hello world."), _seg("I am fine."), _seg("Goodbye.")]

        result = translator.translate(segs, self._config())

        # Ровно один вызов translate (единый текст)
        self.assertEqual(self._mock_api.translate.call_count, 1)
        self.assertEqual(len(result), 3)

    def test_combined_text_sent_as_one_request(self):
        """Тексты объединяются перед отправкой."""
        translator = self._make_translator("Текст.")
        segs = [_seg("Hello"), _seg("World")]

        translator.translate(segs, self._config())

        call_arg = self._mock_api.translate.call_args[0][0]
        # Аргумент должен содержать оба текста
        self.assertIn("Hello", call_arg)
        self.assertIn("World", call_arg)

    def test_original_timings_preserved(self):
        """Тайминги не меняются при переводе."""
        translator = self._make_translator("Привет. Мир.")
        segs = [_seg("Hello.", 0.0, 2.5), _seg("World.", 2.5, 5.0)]

        result = translator.translate(segs, self._config())

        self.assertAlmostEqual(result[0].start, 0.0)
        self.assertAlmostEqual(result[0].end, 2.5)
        self.assertAlmostEqual(result[1].start, 2.5)
        self.assertAlmostEqual(result[1].end, 5.0)

    def test_ids_preserved(self):
        """ID сегментов сохраняются."""
        translator = self._make_translator("Привет. Мир.")
        segs = [_seg("Hello."), _seg("World.")]
        ids = [s.id for s in segs]

        result = translator.translate(segs, self._config())

        self.assertEqual(result[0].id, ids[0])
        self.assertEqual(result[1].id, ids[1])

    def test_empty_returns_empty(self):
        """Пустой список → пустой результат без API."""
        translator = self._make_translator("")
        result = translator.translate([], self._config())
        self.assertEqual(result, [])
        self._mock_api.translate.assert_not_called()

    def test_fallback_on_api_error(self):
        """При ошибке API → fallback поштучный перевод."""
        responses = iter(["Привет.", "Мир."])

        def mock_translate(text):
            if "Hello" in text and "World" in text:
                raise RuntimeError("API error")
            return next(responses)

        mock_api = MagicMock()
        mock_api.translate.side_effect = mock_translate

        translator = GoogleSegmentTranslator(
            translator_factory=lambda **kw: mock_api
        )
        segs = [_seg("Hello."), _seg("World.")]
        result = translator.translate(segs, self._config())

        # Fallback должен был отработать
        self.assertEqual(len(result), 2)
        for r in result:
            self.assertIsInstance(r.translated_text, str)

    def test_source_fallback_gets_qa_flag(self):
        """Если переводчик вернул исходный текст, сегмент получает QA-флаг."""
        translator = self._make_translator("Hello.")
        segs = [_seg("Hello.")]

        result = translator.translate(segs, self._config())

        self.assertIn("translation_fallback_source", result[0].qa_flags)

    def test_source_text_preserved(self):
        """source_text сегмента не меняется после перевода."""
        translator = self._make_translator("Привет мир.")
        segs = [_seg("Hello world.")]

        result = translator.translate(segs, self._config())

        self.assertEqual(result[0].source_text, "Hello world.")


if __name__ == "__main__":
    unittest.main()
