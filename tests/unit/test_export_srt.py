"""Unit-тесты генератора SRT-субтитров."""

import unittest

from translate_video.core.schemas import Segment, SegmentStatus
from translate_video.export.srt import _format_srt_time, segments_to_srt


def _seg(start, end, source="src", translated="") -> Segment:
    """Вспомогательная функция создания сегмента."""
    return Segment(
        id="s1", start=start, end=end,
        source_text=source, translated_text=translated,
        status=SegmentStatus.TRANSLATED,
    )


class SrtTimeFormatTest(unittest.TestCase):
    """Проверяет форматирование таймкода SRT."""

    def test_zero(self):
        """Ноль секунд форматируется как 00:00:00,000."""
        self.assertEqual(_format_srt_time(0.0), "00:00:00,000")

    def test_milliseconds(self):
        """Миллисекунды округляются корректно."""
        self.assertEqual(_format_srt_time(1.5), "00:00:01,500")

    def test_hours_minutes(self):
        """Часы и минуты форматируются с ведущими нулями."""
        self.assertEqual(_format_srt_time(3661.001), "01:01:01,001")

    def test_rounding(self):
        """Дробные миллисекунды округляются."""
        self.assertEqual(_format_srt_time(0.9999), "00:00:01,000")


class SegmentsToSrtTest(unittest.TestCase):
    """Проверяет генерацию SRT-строки из сегментов."""

    def test_empty_segments_returns_empty_string(self):
        """Пустой список сегментов возвращает пустую строку."""
        self.assertEqual(segments_to_srt([]), "")

    def test_uses_translated_text_if_present(self):
        """Если есть перевод, используется переведенный текст."""
        seg = _seg(0.5, 2.0, source="Hello", translated="Привет")
        result = segments_to_srt([seg])
        self.assertIn("Привет", result)
        self.assertNotIn("Hello", result)

    def test_falls_back_to_source_text(self):
        """При отсутствии перевода используется исходный текст."""
        seg = _seg(0.5, 2.0, source="Hello", translated="")
        result = segments_to_srt([seg])
        self.assertIn("Hello", result)

    def test_skips_empty_segments(self):
        """Сегменты с пустым текстом пропускаются."""
        segs = [
            _seg(0.0, 1.0, source="", translated=""),
            _seg(1.0, 2.0, source="Valid", translated="Верно"),
        ]
        result = segments_to_srt(segs)
        self.assertIn("1\n", result)
        self.assertNotIn("2\n", result)

    def test_numbering_skips_gaps(self):
        """Нумерация непрерывна даже при пропуске пустых сегментов."""
        segs = [
            _seg(0.0, 1.0, source="First", translated="Первый"),
            _seg(1.0, 2.0, source="", translated=""),
            _seg(2.0, 3.0, source="Third", translated="Третий"),
        ]
        result = segments_to_srt(segs)
        self.assertIn("1\n", result)
        self.assertIn("2\n", result)
        # Нет "3\n" — только 2 непустых сегмента
        self.assertNotIn("3\n", result)

    def test_srt_format_structure(self):
        """Проверяет структуру блока SRT: N → тайминг → текст."""
        seg = _seg(1.0, 3.5, source="Hi", translated="Привет")
        result = segments_to_srt([seg])
        lines = result.strip().split("\n")
        self.assertEqual(lines[0], "1")
        self.assertIn("-->", lines[1])
        self.assertIn(",", lines[1])  # SRT использует запятую в миллисекундах
        self.assertEqual(lines[2], "Привет")

    def test_multiple_segments_separated_by_blank_line(self):
        """Блоки SRT разделяются пустой строкой."""
        segs = [
            _seg(0.0, 1.0, translated="Первый"),
            _seg(1.5, 2.5, translated="Второй"),
        ]
        result = segments_to_srt(segs)
        self.assertIn("\n\n", result)


if __name__ == "__main__":
    unittest.main()
