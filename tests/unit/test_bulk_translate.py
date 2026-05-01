"""Тесты перевода через маркер-разделитель ||| (TVIDEO-040a).

Покрывает:
- _split_by_separator: корректное разбиение, потеря маркера, alt-разбиение
- _make_sentence_chunks: один чанк, несколько чанков по числу предложений
- _translate_batch: маркер сохранён, маркер потерян (fallback), одиночный сегмент
- GoogleSegmentTranslator.translate: end-to-end с mock translator
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from translate_video.core.schemas import Segment
from translate_video.translation.legacy import (
    GoogleSegmentTranslator,
    _SEP,
    _make_sentence_chunks,
    _split_by_separator,
    _translate_batch,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _seg(text: str, start: float = 0.0, end: float = 1.0) -> Segment:
    return Segment(start=start, end=end, source_text=text)


def _mock_translator(response: str):
    """Создать mock-переводчик возвращающий фиксированную строку."""
    t = MagicMock()
    t.translate = MagicMock(return_value=response)
    return t


# ─── _split_by_separator ─────────────────────────────────────────────────────

class TestSplitBySeparator(unittest.TestCase):
    """TVIDEO-040a: _split_by_separator — разбиение по |||."""

    def test_exact_match(self):
        """Маркер сохранён точно — возвращает список частей."""
        translated = "Привет мир. ||| Как дела? ||| Я в порядке."
        result = _split_by_separator(translated, expected=3)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "Привет мир.")
        self.assertEqual(result[1], "Как дела?")
        self.assertEqual(result[2], "Я в порядке.")

    def test_returns_none_on_wrong_count(self):
        """Количество частей не совпадает → None."""
        translated = "Один. ||| Два."
        result = _split_by_separator(translated, expected=3)
        self.assertIsNone(result)

    def test_no_separator_returns_none(self):
        """Маркер отсутствует → None."""
        result = _split_by_separator("Просто текст без маркера.", expected=2)
        self.assertIsNone(result)

    def test_strips_whitespace(self):
        """Пробелы вокруг частей убираются."""
        translated = "  Привет.  ||| Мир.  "
        result = _split_by_separator(translated, expected=2)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "Привет.")
        self.assertEqual(result[1], "Мир.")

    def test_alt_split_fallback(self):
        """Альтернативное разбиение по ||| без пробелов работает."""
        translated = "Первый.|||Второй.|||Третий."
        result = _split_by_separator(translated, expected=3)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)

    def test_single_expected(self):
        """Один сегмент — нет маркера — корректно."""
        result = _split_by_separator("Только один.", expected=1)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "Только один.")


# ─── _make_sentence_chunks ────────────────────────────────────────────────────

class TestMakeSentenceChunks(unittest.TestCase):
    """TVIDEO-040a: _make_sentence_chunks — разбивка по числу предложений."""

    def test_all_fits_in_one_chunk(self):
        """5 предложений при chunk_size=12 → один чанк."""
        segs = [_seg(f"Sentence {i}.") for i in range(5)]
        chunks = _make_sentence_chunks(segs, chunk_size=12)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]), 5)

    def test_splits_into_multiple_chunks(self):
        """20 предложений при chunk_size=12 → 2 чанка (12 + 8)."""
        segs = [_seg(f"Sentence {i}.") for i in range(20)]
        chunks = _make_sentence_chunks(segs, chunk_size=12)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), 12)
        self.assertEqual(len(chunks[1]), 8)

    def test_all_segments_covered(self):
        """Все сегменты попадают в чанки без потерь."""
        segs = [_seg(f"Segment {i}") for i in range(30)]
        chunks = _make_sentence_chunks(segs, chunk_size=12)
        all_segs = [s for c in chunks for s in c]
        self.assertEqual(len(all_segs), 30)

    def test_exact_chunk_size(self):
        """Ровно chunk_size сегментов → один чанк."""
        segs = [_seg(f"S {i}.") for i in range(12)]
        chunks = _make_sentence_chunks(segs, chunk_size=12)
        self.assertEqual(len(chunks), 1)


# ─── _translate_batch ─────────────────────────────────────────────────────────

class TestTranslateBatch(unittest.TestCase):
    """TVIDEO-038: _translate_batch — перевод батча с маркером."""

    def test_marker_preserved_returns_correct_parts(self):
        """Маркер сохранён → части разбиты корректно."""
        segs = [_seg("Hello"), _seg("World"), _seg("Foo")]
        translator = _mock_translator("Привет ||| Мир ||| Фу")
        result = _translate_batch(segs, translator)
        self.assertEqual(result, ["Привет", "Мир", "Фу"])

    def test_fallback_when_marker_lost(self):
        """Маркер потерян → поштучный fallback."""
        segs = [_seg("Hello"), _seg("World")]
        # Переводчик вернул без маркера
        translator = MagicMock()
        translator.translate = MagicMock(side_effect=[
            "Привет Мир",    # batch call — нет маркера
            "Привет",        # fallback: сег 1
            "Мир",           # fallback: сег 2
        ])
        result = _translate_batch(segs, translator)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "Привет")
        self.assertEqual(result[1], "Мир")

    def test_single_segment_no_marker(self):
        """Один сегмент переводится без маркера."""
        segs = [_seg("Hello")]
        translator = _mock_translator("Привет")
        result = _translate_batch(segs, translator)
        self.assertEqual(result, ["Привет"])
        # Один вызов без ||| в аргументах
        call_arg = translator.translate.call_args[0][0]
        self.assertNotIn("|||", call_arg)

    def test_wrong_part_count_triggers_fallback(self):
        """Неверное количество частей → fallback."""
        segs = [_seg("A"), _seg("B"), _seg("C")]
        # Возвращаем только 2 части вместо 3
        translator = MagicMock()
        translator.translate = MagicMock(side_effect=[
            "Первый ||| Второй",  # batch — неверно
            "А",                  # fallback А
            "В",                  # fallback В
            "С",                  # fallback С
        ])
        result = _translate_batch(segs, translator)
        self.assertEqual(len(result), 3)

    def test_translator_exception_triggers_fallback(self):
        """Исключение при переводе → поштучный fallback."""
        segs = [_seg("Hello"), _seg("World")]
        translator = MagicMock()
        translator.translate = MagicMock(side_effect=[
            Exception("API Error"),  # batch провалился
            "Привет",                # fallback: сег 1
            "Мир",                   # fallback: сег 2
        ])
        result = _translate_batch(segs, translator)
        self.assertEqual(len(result), 2)

    def test_combined_text_contains_separator(self):
        """Объединённый текст содержит разделитель |||."""
        segs = [_seg("Hello"), _seg("World")]
        translator = _mock_translator("Привет ||| Мир")
        _translate_batch(segs, translator)
        call_arg = translator.translate.call_args[0][0]
        self.assertIn("|||", call_arg)


# ─── GoogleSegmentTranslator (end-to-end) ────────────────────────────────────

class TestGoogleSegmentTranslator(unittest.TestCase):
    """TVIDEO-038: GoogleSegmentTranslator.translate — end-to-end с mock."""

    def _make_config(self, source="en", target="ru"):
        cfg = MagicMock()
        cfg.source_language = source
        cfg.target_language = target
        return cfg

    def test_all_segments_get_translations(self):
        """Все сегменты получают перевод — нет пустых."""
        segs = [_seg(f"Sentence {i}") for i in range(5)]
        # Маркер корректно сохраняется
        expected = " ||| ".join(f"Предложение {i}" for i in range(5))
        translator_instance = _mock_translator(expected)
        translator = GoogleSegmentTranslator(
            translator_factory=lambda **kw: translator_instance
        )
        result = translator.translate(segs, self._make_config())
        self.assertEqual(len(result), 5)
        for seg in result:
            self.assertTrue(seg.translated_text.strip(), f"Пустой перевод: {seg}")

    def test_no_segments_returns_empty(self):
        """Пустой список → пустой список."""
        translator = GoogleSegmentTranslator()
        result = translator.translate([], self._make_config())
        self.assertEqual(result, [])

    def test_translation_count_equals_segment_count(self):
        """Количество результатов равно количеству сегментов (62 → 62)."""
        n = 62
        segs = [_seg(f"Short text {i}") for i in range(n)]
        # Симулируем: маркер сохранился
        translated_parts = [f"Текст {i}" for i in range(n)]
        # Переводчик возвращает части через маркер (батчами)
        responses = []
        # _make_batches разобьёт 62 коротких сегмента вероятно в 1-2 батча
        # Мокируем чтобы каждый вызов возвращал нужное количество частей
        call_count = [0]
        batch_size_tracker = []

        def smart_translate(text):
            parts = text.split("|||")
            n_parts = len(parts)
            batch_size_tracker.append(n_parts)
            return " ||| ".join(f"Рус {call_count[0]}_{i}" for i in range(n_parts))

        translator_instance = MagicMock()
        translator_instance.translate = MagicMock(side_effect=smart_translate)
        translator = GoogleSegmentTranslator(
            translator_factory=lambda **kw: translator_instance
        )
        result = translator.translate(segs, self._make_config())
        self.assertEqual(len(result), n, f"Ожидали {n} сегментов, получили {len(result)}")
        empty = [s for s in result if not s.translated_text.strip()]
        self.assertEqual(len(empty), 0, f"Пустых сегментов: {len(empty)}")

    def test_qa_flag_on_empty_translation(self):
        """Пустой перевод → qa_flag translation_empty."""
        segs = [_seg("Hello"), _seg("World")]
        # Первый сегмент переведён, второй — пустой (переводчик вернул "")
        translator_instance = MagicMock()
        translator_instance.translate = MagicMock(side_effect=[
            "Привет ||| ",   # batch — второй сегмент пустой, trailing strip → fallback
            "Привет",        # fallback: seg 0
            "",              # fallback: seg 1 → пустой
        ])
        translator = GoogleSegmentTranslator(
            translator_factory=lambda **kw: translator_instance
        )
        result = translator.translate(segs, self._make_config())
        self.assertEqual(len(result), 2)
        self.assertIn("translation_empty", result[1].qa_flags)

    def test_qa_flag_fallback_source(self):
        """Перевод совпал с источником → qa_flag translation_fallback_source."""
        segs = [_seg("Hello")]
        translator_instance = _mock_translator("Hello")  # не перевёл
        translator = GoogleSegmentTranslator(
            translator_factory=lambda **kw: translator_instance
        )
        result = translator.translate(segs, self._make_config())
        self.assertIn("translation_fallback_source", result[0].qa_flags)


if __name__ == "__main__":
    unittest.main()
