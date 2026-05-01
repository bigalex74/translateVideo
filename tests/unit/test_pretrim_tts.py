"""Тесты pre-trim TTS текста (TVIDEO-030c).

Покрывает:
- Текст в пределах слота → не трогаем
- Текст слишком длинный → обрезаем на конце предложения
- Нет предложения → обрезаем на слове
- Нет пробела → жёсткая обрезка
- Пустой слот или нулевой текст
"""

from __future__ import annotations

import unittest

from translate_video.tts.legacy import (
    _compute_tts_text,
    _trim_at_natural_boundary,
    _CHARS_PER_SECOND,
    _OVERFLOW_THRESHOLD,
)


class TestComputeTtsText(unittest.TestCase):
    """TVIDEO-030c: _compute_tts_text — основная логика."""

    def test_short_text_unchanged(self):
        """Текст укладывается в слот → возвращается без изменений."""
        # 3 секунды * 14 cps = 42 символа. Текст 20 символов — OK
        text = "Короткий текст здесь"
        result = _compute_tts_text(text, slot_duration=3.0)
        self.assertEqual(result, text)

    def test_text_within_threshold_unchanged(self):
        """Текст чуть длиннее слота но в пределах threshold → не трогаем."""
        # 14 cps * 3.0s = 42 chars, threshold 1.15 → до 48 chars OK
        text = "А" * 46  # 46 < 48.3 → не трогаем
        result = _compute_tts_text(text, slot_duration=3.0)
        self.assertEqual(result, text)

    def test_long_text_gets_trimmed(self):
        """Текст намного длиннее слота → укорачивается."""
        # 2 секунды * 14 = 28 chars, threshold 1.15 → 32 chars max
        text = "Это очень длинный текст который явно не уложится в два секунды никак."
        result = _compute_tts_text(text, slot_duration=2.0)
        self.assertLess(len(result), len(text))

    def test_zero_slot_returns_text_unchanged(self):
        """Слот 0 секунд → возвращаем без изменений (нет основы для оценки)."""
        text = "Привет мир."
        result = _compute_tts_text(text, slot_duration=0.0)
        self.assertEqual(result, text)

    def test_empty_text_unchanged(self):
        """Пустой текст → возвращается пустой."""
        result = _compute_tts_text("", slot_duration=3.0)
        self.assertEqual(result, "")


class TestTrimAtNaturalBoundary(unittest.TestCase):
    """TVIDEO-030c: _trim_at_natural_boundary — обрезка на границах."""

    def test_cuts_at_sentence_end(self):
        """Предпочитает обрезку на конце предложения."""
        text = "Первое предложение. Второе предложение которое длиннее."
        # max_chars = 25 → должен взять первое предложение целиком
        result = _trim_at_natural_boundary(text, max_chars=25)
        self.assertTrue(result.endswith("."), f"Ожидали конец предложения, получили: {result!r}")
        self.assertIn("Первое", result)

    def test_cuts_at_word_boundary_if_no_sentence(self):
        """Если нет знака препинания — обрезает на пробеле."""
        text = "Очень длинное слово за словом без знаков препинания вообще"
        result = _trim_at_natural_boundary(text, max_chars=20)
        # Не должно обрываться на полуслове
        self.assertFalse(result.endswith(text[len(result)]) if len(result) < len(text) else False)
        # Последний символ не должен быть серединой слова
        if len(result) < len(text):
            next_char = text[len(result)] if len(result) < len(text) else ' '
            self.assertIn(next_char, (' ', ''), f"Должен обрезать на пробеле, а не на: {next_char!r}")

    def test_no_trimming_if_within_limit(self):
        """Если текст короче max_chars — возвращает без изменений."""
        text = "Короткий текст."
        result = _trim_at_natural_boundary(text, max_chars=100)
        self.assertEqual(result, text)

    def test_result_not_empty(self):
        """Результат никогда не пустой (если исходный текст не пустой)."""
        text = "Слово"
        result = _trim_at_natural_boundary(text, max_chars=3)
        self.assertTrue(len(result) > 0)

    def test_exclamation_and_question_marks(self):
        """Поддерживает ! и ? как границы предложения."""
        text = "Привет! Это второе предложение которое длиннее."
        result = _trim_at_natural_boundary(text, max_chars=10)
        self.assertTrue(result.endswith("!"), f"Ожидали '!', получили: {result!r}")

    def test_result_is_stripped(self):
        """Результат не содержит пробелов в начале/конце."""
        text = "Первое. Второе длинное предложение."
        result = _trim_at_natural_boundary(text, max_chars=20)
        self.assertEqual(result, result.strip())


class TestTtsProviderPretrim(unittest.TestCase):
    """TVIDEO-030c: EdgeTTSProvider не синтезирует обрезанные куски неестественно."""

    def test_synthesize_uses_trimmed_text(self):
        """Провайдер передаёт в communicate укороченный текст при длинном сегменте."""
        from unittest.mock import MagicMock, patch
        import tempfile
        from pathlib import Path
        from translate_video.tts.legacy import EdgeTTSProvider
        from translate_video.core.schemas import Segment

        synthesized_texts = []

        def fake_communicate(text, voice, rate=None):
            synthesized_texts.append(text)
            mock_comm = MagicMock()
            mock_comm.save = MagicMock(return_value=None)
            return mock_comm

        provider = EdgeTTSProvider(
            communicate_factory=fake_communicate,
            async_runner=lambda coro: None,
        )

        # Сегмент 1 секунда, текст явно длиннее (>16 chars)
        long_translated = "Очень длинный переведённый текст который не уложится в одну секунду точно нет."
        seg = Segment(start=0.0, end=1.0, source_text="Short", translated_text=long_translated)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            project = MagicMock()
            project.config.target_language = "ru"
            project.work_dir = tmp

            provider.synthesize(project, [seg])

        # Текст который попал в communicate должен быть короче исходного
        self.assertEqual(len(synthesized_texts), 1)
        self.assertLess(
            len(synthesized_texts[0]),
            len(long_translated),
            "TTS должен получить укороченный текст"
        )

    def test_synthesize_unchanged_for_short_segment(self):
        """Короткий перевод в большом слоте → текст не трогается."""
        from unittest.mock import MagicMock
        import tempfile
        from pathlib import Path
        from translate_video.tts.legacy import EdgeTTSProvider
        from translate_video.core.schemas import Segment

        synthesized_texts = []

        def fake_communicate(text, voice, rate=None):
            synthesized_texts.append(text)
            mock_comm = MagicMock()
            mock_comm.save = MagicMock(return_value=None)
            return mock_comm

        provider = EdgeTTSProvider(
            communicate_factory=fake_communicate,
            async_runner=lambda coro: None,
        )

        short_text = "Привет мир."  # 11 символов, слот 5 секунд = 70 chars
        seg = Segment(start=0.0, end=5.0, source_text="Hello world.", translated_text=short_text)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "tts").mkdir()
            project = MagicMock()
            project.config.target_language = "ru"
            project.work_dir = tmp

            provider.synthesize(project, [seg])

        self.assertEqual(synthesized_texts[0], short_text)


if __name__ == "__main__":
    unittest.main()
