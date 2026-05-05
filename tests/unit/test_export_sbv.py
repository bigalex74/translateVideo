"""Unit-тесты генератора YouTube SBV субтитров (Z3.4).

Проверяет: формат таймкода, структуру блоков, разделители.
"""

import unittest

from translate_video.core.schemas import Segment, SegmentStatus
from translate_video.export.sbv import _sbv_time, segments_to_sbv


def _seg(start: float, end: float, source: str = "src", translated: str = "") -> Segment:
    return Segment(
        id="s1", start=start, end=end,
        source_text=source, translated_text=translated,
        status=SegmentStatus.TRANSLATED,
    )


class SbvTimeFormatTest(unittest.TestCase):
    """Проверяет формат таймкода SBV: H:MM:SS.mmm"""

    def test_zero(self):
        """Ноль — 0:00:00.000"""
        self.assertEqual(_sbv_time(0.0), "0:00:00.000")

    def test_milliseconds(self):
        """Миллисекунды."""
        self.assertEqual(_sbv_time(1.500), "0:00:01.500")

    def test_minutes(self):
        """Минуты."""
        self.assertEqual(_sbv_time(90.0), "0:01:30.000")

    def test_hours(self):
        """Часы."""
        self.assertEqual(_sbv_time(7261.0), "2:01:01.000")

    def test_rounding(self):
        """Дробные миллисекунды округляются."""
        self.assertEqual(_sbv_time(0.9999), "0:00:01.000")


class SegmentsToSbvTest(unittest.TestCase):
    """Проверяет генерацию YouTube SBV из сегментов."""

    def test_empty_returns_empty(self):
        """Пустой список — пустая строка."""
        result = segments_to_sbv([])
        self.assertEqual(result.strip(), "")

    def test_single_block_format(self):
        """Формат одного блока: тайминг на первой строке, текст на второй."""
        seg = _seg(1.0, 3.0, translated="Привет")
        result = segments_to_sbv([seg])
        lines = result.strip().splitlines()
        self.assertEqual(len(lines), 2)
        # Тайминговая строка SBV: start,end (start,end через запятую)
        self.assertIn(",", lines[0])   # тайминговая строка: start,end
        self.assertEqual(lines[1], "Привет")

    def test_sbv_timing_format_comma_separated(self):
        """SBV разделяет start и end запятой, не стрелкой."""
        seg = _seg(1.0, 3.0, translated="Текст")
        result = segments_to_sbv([seg])
        timing_line = result.strip().splitlines()[0]
        self.assertIn(",", timing_line)
        # SBV не использует --> в отличие от VTT/SRT
        self.assertNotIn("-->", timing_line)

    def test_multiple_blocks_separated_by_blank_line(self):
        """Блоки разделяются пустой строкой."""
        segs = [
            _seg(0.0, 1.0, translated="Первый"),
            _seg(2.0, 3.0, translated="Второй"),
        ]
        result = segments_to_sbv(segs)
        self.assertIn("\n\n", result)

    def test_uses_translated_text(self):
        """Приоритет переведённого текста."""
        seg = _seg(0.0, 1.0, source="Hello", translated="Привет")
        result = segments_to_sbv([seg])
        self.assertIn("Привет", result)
        self.assertNotIn("Hello", result)

    def test_falls_back_to_source(self):
        """Fallback на исходный текст."""
        seg = _seg(0.0, 1.0, source="Hello", translated="")
        result = segments_to_sbv([seg])
        self.assertIn("Hello", result)

    def test_skips_empty_segments(self):
        """Пустые сегменты пропускаются."""
        segs = [
            _seg(0.0, 1.0, source="", translated=""),
            _seg(1.0, 2.0, source="Valid", translated="Верно"),
        ]
        result = segments_to_sbv(segs)
        self.assertEqual(result.count("Верно"), 1)
        self.assertNotIn("0:00:00.000", result)

    def test_ends_with_newline(self):
        """Файл заканчивается переносом строки."""
        seg = _seg(0.0, 1.0, translated="Текст")
        result = segments_to_sbv([seg])
        self.assertTrue(result.endswith("\n"))

    def test_timecodes_correct(self):
        """Таймкоды соответствуют сегменту."""
        seg = _seg(65.0, 70.5, translated="Тест")
        result = segments_to_sbv([seg])
        self.assertIn("0:01:05.000", result)
        self.assertIn("0:01:10.500", result)


if __name__ == "__main__":
    unittest.main()
