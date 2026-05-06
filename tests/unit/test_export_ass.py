"""Unit-тесты генератора ASS-субтитров (NC5-01).

Проверяет: формат таймкода, структуру заголовка, сегменты, перенос строк.
"""

import unittest

from translate_video.core.schemas import Segment, SegmentStatus
from translate_video.export.ass import _ass_time, segments_to_ass


def _seg(start: float, end: float, source: str = "src", translated: str = "") -> Segment:
    return Segment(
        id="s1", start=start, end=end,
        source_text=source, translated_text=translated,
        status=SegmentStatus.TRANSLATED,
    )


class AssTimeFormatTest(unittest.TestCase):
    """Проверяет формат таймкода ASS: H:MM:SS.cc"""

    def test_zero(self):
        """Ноль — 0:00:00.00"""
        self.assertEqual(_ass_time(0.0), "0:00:00.00")

    def test_one_second(self):
        """Одна секунда."""
        self.assertEqual(_ass_time(1.0), "0:00:01.00")

    def test_hundredths(self):
        """Сотые доли секунды — используется int()/floor, не round."""
        self.assertEqual(_ass_time(1.255), "0:00:01.25")

    def test_minutes_hours(self):
        """Часы и минуты."""
        self.assertEqual(_ass_time(3661.0), "1:01:01.00")

    def test_large_value(self):
        """Большое значение (2 часа 30 мин)."""
        result = _ass_time(2 * 3600 + 30 * 60 + 15.5)
        self.assertEqual(result, "2:30:15.50")


class SegmentsToAssTest(unittest.TestCase):
    """Проверяет генерацию ASS-строки из сегментов."""

    def test_empty_returns_header_only(self):
        """Пустой список — только заголовок ASS без Dialogue строк."""
        result = segments_to_ass([])
        self.assertIn("[Script Info]", result)
        self.assertIn("[Events]", result)
        self.assertNotIn("Dialogue:", result)

    def test_header_contains_sections(self):
        """Заголовок содержит обязательные секции."""
        result = segments_to_ass([])
        self.assertIn("[V4+ Styles]", result)
        self.assertIn("PlayResX: 1920", result)
        self.assertIn("PlayResY: 1080", result)

    def test_dialogue_format(self):
        """Dialogue строка формируется корректно."""
        seg = _seg(1.0, 3.5, translated="Привет мир")
        result = segments_to_ass([seg])
        self.assertIn("Dialogue: 0,", result)
        self.assertIn("Привет мир", result)

    def test_uses_translated_text(self):
        """Используется переведённый текст, а не исходный."""
        seg = _seg(0.0, 1.0, source="Hello", translated="Привет")
        result = segments_to_ass([seg])
        self.assertIn("Привет", result)
        self.assertNotIn("Hello", result)

    def test_falls_back_to_source(self):
        """При отсутствии перевода — исходный текст."""
        seg = _seg(0.0, 1.0, source="Hello", translated="")
        result = segments_to_ass([seg])
        self.assertIn("Hello", result)

    def test_skips_empty_segments(self):
        """Пустые сегменты не включаются в вывод."""
        segs = [
            _seg(0.0, 1.0, source="", translated=""),
            _seg(1.0, 2.0, source="Valid", translated="Верно"),
        ]
        result = segments_to_ass(segs)
        dialogue_count = result.count("Dialogue:")
        self.assertEqual(dialogue_count, 1)

    def test_newline_replaced_with_ass_soft_break(self):
        """Перенос строки заменяется на \\N (soft break ASS)."""
        seg = _seg(0.0, 1.0, translated="Строка один\nСтрока два")
        result = segments_to_ass([seg])
        self.assertIn(r"\N", result)
        # Оригинальный \n не должен быть в Dialogue строке
        dialogue_line = [l for l in result.splitlines() if l.startswith("Dialogue:")][0]
        self.assertNotIn("\n", dialogue_line.split("Dialogue:")[1])

    def test_custom_style(self):
        """Пользовательский стиль передаётся в Dialogue."""
        seg = _seg(0.0, 1.0, translated="Текст")
        result = segments_to_ass([seg], style="Top")
        self.assertIn(",Top,", result)

    def test_multiple_segments(self):
        """Несколько сегментов — несколько Dialogue строк."""
        segs = [_seg(float(i), float(i + 1), translated=f"Сегмент {i}") for i in range(5)]
        result = segments_to_ass(segs)
        self.assertEqual(result.count("Dialogue:"), 5)

    def test_timecodes_in_dialogue(self):
        """Таймкоды присутствуют в Dialogue строке."""
        seg = _seg(60.0, 62.5, translated="Минута")
        result = segments_to_ass([seg])
        self.assertIn("0:01:00.00", result)
        self.assertIn("0:01:02.50", result)


if __name__ == "__main__":
    unittest.main()
