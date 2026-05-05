"""Unit-тесты нового поля Segment.notes (Z2.11) и механизма impоrта субтитров.

Проверяет:
- Поле notes сохраняется и восстанавливается из JSON
- Поле notes не влияет на пайплайн
- Парсеры SRT/VTT в import-subtitles endpoint (_parse_srt_time, _parse_vtt_time)
"""

import unittest

from translate_video.core.schemas import Segment, SegmentStatus
from translate_video.api.routes.projects import _parse_srt_time, _parse_vtt_time


def _seg(**kwargs) -> Segment:
    defaults = dict(
        id="s1", start=0.0, end=1.0,
        source_text="Hello", translated_text="Привет",
        status=SegmentStatus.TRANSLATED,
    )
    defaults.update(kwargs)
    return Segment(**defaults)


class SegmentNotesFieldTest(unittest.TestCase):
    """Тесты поля notes в Segment (Z2.11)."""

    def test_notes_default_empty_string(self):
        """notes по умолчанию — пустая строка."""
        seg = _seg()
        self.assertEqual(seg.notes, "")

    def test_notes_can_be_set(self):
        """notes можно задать при создании."""
        seg = _seg(notes="Проверить ударение в слове 'дома'")
        self.assertEqual(seg.notes, "Проверить ударение в слове 'дома'")

    def test_notes_serialized_in_to_dict(self):
        """notes включается в to_dict()."""
        seg = _seg(notes="Тест заметки")
        d = seg.to_dict()
        self.assertIn("notes", d)
        self.assertEqual(d["notes"], "Тест заметки")

    def test_notes_deserialized_from_dict(self):
        """notes восстанавливается из from_dict()."""
        d = {
            "id": "s1", "start": 0.0, "end": 1.0,
            "source_text": "Hi", "translated_text": "Привет",
            "status": "translated", "notes": "Важная заметка",
        }
        seg = Segment.from_dict(d)
        self.assertEqual(seg.notes, "Важная заметка")

    def test_notes_missing_from_dict_uses_default(self):
        """Если notes отсутствует в JSON — используется default (пустая строка)."""
        d = {
            "id": "s1", "start": 0.0, "end": 1.0,
            "source_text": "Hi", "translated_text": "Привет",
            "status": "translated",
        }
        seg = Segment.from_dict(d)
        self.assertEqual(seg.notes, "")

    def test_notes_does_not_affect_duration(self):
        """Поле notes не влияет на duration."""
        seg = _seg(start=1.0, end=4.0, notes="Длинная заметка очень важная")
        self.assertAlmostEqual(seg.duration, 3.0)

    def test_notes_roundtrip(self):
        """Полный цикл: создание → to_dict → from_dict → notes совпадает."""
        original = _seg(notes="🎯 Проверить произношение")
        restored = Segment.from_dict(original.to_dict())
        self.assertEqual(restored.notes, original.notes)


class ParseSrtTimeTest(unittest.TestCase):
    """Тесты парсера таймкода SRT (NC6-01)."""

    def test_zero(self):
        """00:00:00,000 → 0.0"""
        self.assertAlmostEqual(_parse_srt_time("00:00:00,000"), 0.0)

    def test_one_second(self):
        """00:00:01,000 → 1.0"""
        self.assertAlmostEqual(_parse_srt_time("00:00:01,000"), 1.0)

    def test_milliseconds(self):
        """Миллисекунды парсируются корректно."""
        self.assertAlmostEqual(_parse_srt_time("00:00:01,500"), 1.5)

    def test_minutes(self):
        """Минуты конвертируются в секунды."""
        self.assertAlmostEqual(_parse_srt_time("00:01:30,000"), 90.0)

    def test_hours(self):
        """Часы конвертируются в секунды."""
        self.assertAlmostEqual(_parse_srt_time("01:00:00,000"), 3600.0)

    def test_full_timecode(self):
        """Полный таймкод: 1ч 2м 3.456с."""
        result = _parse_srt_time("01:02:03,456")
        expected = 3600 + 2 * 60 + 3 + 0.456
        self.assertAlmostEqual(result, expected, places=3)


class ParseVttTimeTest(unittest.TestCase):
    """Тесты парсера таймкода VTT (NC6-01)."""

    def test_zero(self):
        """00:00:00.000 → 0.0"""
        self.assertAlmostEqual(_parse_vtt_time("00:00:00.000"), 0.0)

    def test_one_second(self):
        """00:00:01.000 → 1.0"""
        self.assertAlmostEqual(_parse_vtt_time("00:00:01.000"), 1.0)

    def test_milliseconds(self):
        """Миллисекунды."""
        self.assertAlmostEqual(_parse_vtt_time("00:00:02.500"), 2.5)

    def test_hours(self):
        """Часы."""
        self.assertAlmostEqual(_parse_vtt_time("02:00:00.000"), 7200.0)

    def test_without_hours(self):
        """VTT без часов (MM:SS.mmm)."""
        self.assertAlmostEqual(_parse_vtt_time("01:30.000"), 90.0)


if __name__ == "__main__":
    unittest.main()
