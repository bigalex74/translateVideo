"""Тесты для модуля ssml_enhance (TVIDEO-094)."""

import unittest
import xml.etree.ElementTree as ET

from translate_video.tts.ssml_enhance import EMOTION_OFF, enhance


def _parse_ssml(text: str) -> ET.Element:
    """Разобрать SSML-строку в XML-дерево."""
    return ET.fromstring(text)


class EmotionOffTest(unittest.TestCase):
    """Уровень 0 — возвращается исходный текст без изменений."""

    def test_plain_text_returned_unchanged(self):
        text = "Привет, мир!"
        self.assertEqual(enhance(text, EMOTION_OFF), text)

    def test_no_ssml_tags_in_output(self):
        result = enhance("Тест.", 0)
        self.assertNotIn("<speak>", result)

    def test_empty_string_returned_unchanged(self):
        self.assertEqual(enhance("", 0), "")


class SSMLStructureTest(unittest.TestCase):
    """Уровни 1-3 возвращают валидный SSML."""

    def test_level1_has_speak_root(self):
        result = enhance("Привет. Как дела?", 1)
        self.assertTrue(result.startswith("<speak>"))
        self.assertTrue(result.endswith("</speak>"))

    def test_level2_valid_xml(self):
        result = enhance("Отлично! Понял.", 2)
        # Должен парситься без исключений
        _parse_ssml(result)

    def test_level3_valid_xml(self):
        result = enhance("Внимание! Это важно. Понял?", 3)
        _parse_ssml(result)

    def test_special_chars_are_escaped(self):
        """Символы < > & в тексте должны быть экранированы."""
        result = enhance("Результат: 2 > 1 и x < 5.", 1)
        self.assertNotIn(" > 1", result)   # '>' → '&gt;'
        self.assertNotIn("x < 5", result)  # '<' → '&lt;'
        _parse_ssml(result)  # должен быть валидным XML

    def test_ampersand_escaped(self):
        result = enhance("Tom & Jerry вернулись.", 1)
        self.assertIn("&amp;", result)
        _parse_ssml(result)


class PauseTest(unittest.TestCase):
    """Паузы добавляются на знаках препинания."""

    def test_level1_has_break_after_exclamation(self):
        result = enhance("Ура! Победа.", 1)
        self.assertIn("<break", result)

    def test_level1_has_break_after_period(self):
        result = enhance("Первое. Второе.", 1)
        self.assertIn("<break", result)

    def test_level2_exclamation_has_prosody(self):
        result = enhance("Отлично! Идём дальше.", 2)
        self.assertIn("prosody", result)

    def test_level3_question_has_prosody(self):
        result = enhance("Как дела? Всё хорошо.", 3)
        self.assertIn("prosody", result)


class EmphasisTest(unittest.TestCase):
    """Ударение на ключевых словах (уровень 3)."""

    def test_level3_adds_emphasis_on_intro_word(self):
        result = enhance("Внимание! Данные изменились.", 3)
        self.assertIn("emphasis", result)

    def test_level2_does_not_add_emphasis(self):
        result = enhance("Внимание! Данные изменились.", 2)
        self.assertNotIn("emphasis", result)

    def test_level1_does_not_add_emphasis(self):
        result = enhance("Внимание! Данные изменились.", 1)
        self.assertNotIn("emphasis", result)


class EmotionLevelClampTest(unittest.TestCase):
    """Граничные значения уровня (out-of-range)."""

    def test_negative_level_treated_as_zero(self):
        """Отрицательный уровень → plain text (как 0)."""
        text = "Привет!"
        result = enhance(text, -5)
        self.assertEqual(result, text)

    def test_level_above_max_treated_as_3(self):
        """Уровень > 3 зажимается до 3 → возвращает валидный SSML."""
        result = enhance("Привет!", 99)
        self.assertTrue(result.startswith("<speak>"))
        _parse_ssml(result)


if __name__ == "__main__":
    unittest.main()
