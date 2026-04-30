"""Unit-тесты генератора отчёта по таймингам."""

import unittest

from translate_video.core.schemas import Segment, SegmentStatus
from translate_video.export.timing_report import build_timing_report


def _seg(seg_id, start, end, source="src", translated="", status=SegmentStatus.TRANSLATED):
    """Вспомогательная функция создания сегмента."""
    return Segment(
        id=seg_id, start=start, end=end,
        source_text=source, translated_text=translated,
        status=status,
    )


class TimingReportEmptyTest(unittest.TestCase):
    """Проверяет поведение при пустом списке сегментов."""

    def test_empty_list_returns_zeros(self):
        """Пустой список возвращает отчёт с нулевыми счётчиками."""
        report = build_timing_report([])
        self.assertEqual(report["total_segments"], 0)
        self.assertEqual(report["total_duration"], 0.0)
        self.assertEqual(report["segments"], [])


class TimingReportCountsTest(unittest.TestCase):
    """Проверяет счётчики переведенных и пустых сегментов."""

    def setUp(self):
        self.segments = [
            _seg("s1", 0.0, 2.0, source="Hello", translated="Привет"),
            _seg("s2", 2.5, 4.0, source="World", translated=""),
            _seg("s3", 4.5, 6.0, source="Test",  translated="Тест"),
        ]
        self.report = build_timing_report(self.segments)

    def test_total_segments(self):
        """total_segments равен числу переданных сегментов."""
        self.assertEqual(self.report["total_segments"], 3)

    def test_translated_count(self):
        """translated_count считает только непустые переводы."""
        self.assertEqual(self.report["translated_count"], 2)

    def test_empty_count(self):
        """empty_count считает сегменты с пустым переводом."""
        self.assertEqual(self.report["empty_count"], 1)


class TimingReportDurationsTest(unittest.TestCase):
    """Проверяет вычисление длительностей."""

    def setUp(self):
        self.segments = [
            _seg("s1", 0.0, 1.0, translated="A"),   # 1.0 с
            _seg("s2", 2.0, 4.0, translated="BB"),  # 2.0 с
            _seg("s3", 5.0, 8.0, translated="CCC"), # 3.0 с
        ]
        self.report = build_timing_report(self.segments)

    def test_total_duration(self):
        """total_duration — сумма длительностей сегментов."""
        self.assertAlmostEqual(self.report["total_duration"], 6.0)

    def test_avg_duration(self):
        """avg_duration — среднее значение длительности."""
        self.assertAlmostEqual(self.report["avg_duration"], 2.0)

    def test_min_duration(self):
        """min_duration — минимальная длительность."""
        self.assertAlmostEqual(self.report["min_duration"], 1.0)

    def test_max_duration(self):
        """max_duration — максимальная длительность."""
        self.assertAlmostEqual(self.report["max_duration"], 3.0)


class TimingReportDetailTest(unittest.TestCase):
    """Проверяет детальную таблицу сегментов."""

    def test_segment_detail_fields(self):
        """Каждая запись содержит все обязательные поля."""
        seg = _seg("seg_x", 1.0, 3.0, source="Hello world", translated="Привет мир")
        report = build_timing_report([seg])
        row = report["segments"][0]
        required = {"id", "start", "end", "duration", "chars_source",
                    "chars_translated", "chars_per_sec", "status"}
        self.assertEqual(required, set(row.keys()))

    def test_chars_per_sec_calculation(self):
        """chars_per_sec = len(translated) / duration."""
        seg = _seg("s1", 0.0, 2.0, source="Hi", translated="Привет")
        report = build_timing_report([seg])
        row = report["segments"][0]
        expected = round(len("Привет") / 2.0, 2)
        self.assertAlmostEqual(row["chars_per_sec"], expected)

    def test_chars_per_sec_zero_when_no_translation(self):
        """chars_per_sec равен 0 при пустом переводе."""
        seg = _seg("s1", 0.0, 2.0, source="Hi", translated="")
        report = build_timing_report([seg])
        self.assertEqual(report["segments"][0]["chars_per_sec"], 0.0)

    def test_segment_count_in_detail(self):
        """Число записей в segments совпадает с total_segments."""
        segs = [_seg(f"s{i}", i, i + 1.0, translated="T") for i in range(5)]
        report = build_timing_report(segs)
        self.assertEqual(len(report["segments"]), report["total_segments"])


if __name__ == "__main__":
    unittest.main()
