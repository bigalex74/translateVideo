"""Unit-тесты генератора WebVTT-субтитров."""

import unittest

from translate_video.core.schemas import Segment, SegmentStatus
from translate_video.export.vtt import _format_vtt_time, segments_to_vtt


def _seg(start, end, source="src", translated="") -> Segment:
    """Вспомогательная функция создания сегмента."""
    return Segment(
        id="v1", start=start, end=end,
        source_text=source, translated_text=translated,
        status=SegmentStatus.TRANSLATED,
    )


class VttTimeFormatTest(unittest.TestCase):
    """Проверяет форматирование таймкода VTT."""

    def test_zero(self):
        """Ноль секунд форматируется как 00:00:00.000."""
        self.assertEqual(_format_vtt_time(0.0), "00:00:00.000")

    def test_uses_dot_not_comma(self):
        """VTT использует точку (не запятую) в миллисекундах."""
        result = _format_vtt_time(1.5)
        self.assertIn(".", result)
        self.assertNotIn(",", result)
        self.assertEqual(result, "00:00:01.500")

    def test_hours(self):
        """Часы форматируются корректно."""
        self.assertEqual(_format_vtt_time(7200.0), "02:00:00.000")


class SegmentsToVttTest(unittest.TestCase):
    """Проверяет генерацию WebVTT-строки из сегментов."""

    def test_starts_with_webvtt_header(self):
        """Вывод должен начинаться с заголовка WEBVTT."""
        result = segments_to_vtt([])
        self.assertTrue(result.startswith("WEBVTT"))

    def test_empty_segments_returns_header_only(self):
        """Пустой список сегментов возвращает только заголовок."""
        result = segments_to_vtt([])
        self.assertEqual(result.strip(), "WEBVTT")

    def test_uses_translated_text_if_present(self):
        """Если есть перевод, используется переведенный текст."""
        seg = _seg(0.5, 2.0, source="Hello", translated="Привет")
        result = segments_to_vtt([seg])
        self.assertIn("Привет", result)
        self.assertNotIn("Hello", result)

    def test_falls_back_to_source_text(self):
        """При отсутствии перевода используется исходный текст."""
        seg = _seg(0.5, 2.0, source="Hello", translated="")
        result = segments_to_vtt([seg])
        self.assertIn("Hello", result)

    def test_skips_empty_segments(self):
        """Сегменты с пустым текстом пропускаются."""
        segs = [
            _seg(0.0, 1.0, source="", translated=""),
            _seg(1.0, 2.0, translated="Верно"),
        ]
        result = segments_to_vtt(segs)
        self.assertIn("Верно", result)
        self.assertIn("1\n", result)

    def test_vtt_arrow_format(self):
        """Тайминг использует формат 'HH:MM:SS.mmm --> HH:MM:SS.mmm'."""
        seg = _seg(1.0, 3.0, translated="Текст")
        result = segments_to_vtt([seg])
        self.assertIn("00:00:01.000 --> 00:00:03.000", result)

    def test_srt_vs_vtt_comma_vs_dot(self):
        """SRT использует запятую, VTT — точку в одном и том же значении."""
        from translate_video.export.srt import _format_srt_time  # noqa: PLC0415

        srt_time = _format_srt_time(1.5)
        vtt_time = _format_vtt_time(1.5)
        self.assertIn(",", srt_time)
        self.assertIn(".", vtt_time)
        # Числовые значения одинаковы
        self.assertEqual(srt_time.replace(",", "."), vtt_time)


if __name__ == "__main__":
    unittest.main()
