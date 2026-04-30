"""Unit-тесты генератора артефакта ревью перевода."""

import unittest

from translate_video.core.schemas import Segment, SegmentStatus
from translate_video.export.review import build_review_artifact


def _seg(seg_id, start, end, source="src", translated="") -> Segment:
    """Вспомогательная функция создания сегмента."""
    return Segment(
        id=seg_id, start=start, end=end,
        source_text=source, translated_text=translated,
        status=SegmentStatus.TRANSLATED,
    )


class ReviewArtifactStructureTest(unittest.TestCase):
    """Проверяет структуру возвращаемого артефакта."""

    def test_required_top_level_fields(self):
        """Отчёт содержит все обязательные поля верхнего уровня."""
        report = build_review_artifact([])
        for field in ("reviewed_at", "total_segments", "needs_review_count", "segments"):
            self.assertIn(field, report)

    def test_config_field_present_when_passed(self):
        """Поле config присутствует, если конфиг передан."""
        report = build_review_artifact([], config_dict={"target_language": "ru"})
        self.assertIn("config", report)
        self.assertEqual(report["config"]["target_language"], "ru")

    def test_config_field_absent_when_not_passed(self):
        """Поле config отсутствует, если конфиг не передан."""
        report = build_review_artifact([])
        self.assertNotIn("config", report)

    def test_reviewed_at_is_iso_string(self):
        """reviewed_at содержит ISO-строку с датой."""
        report = build_review_artifact([])
        # Проверяем что это похоже на ISO-дату
        self.assertIn("T", report["reviewed_at"])
        self.assertIn("+", report["reviewed_at"] + "Z")  # UTC или с оффсетом


class ReviewNeedsReviewFlagTest(unittest.TestCase):
    """Проверяет логику флага needs_review."""

    def test_empty_translation_needs_review(self):
        """Пустой перевод помечается как needs_review=True."""
        seg = _seg("s1", 0.0, 1.0, source="Hello", translated="")
        report = build_review_artifact([seg])
        self.assertTrue(report["segments"][0]["needs_review"])

    def test_whitespace_only_translation_needs_review(self):
        """Перевод из пробелов помечается как needs_review=True."""
        seg = _seg("s1", 0.0, 1.0, source="Hello", translated="   ")
        report = build_review_artifact([seg])
        self.assertTrue(report["segments"][0]["needs_review"])

    def test_translation_same_as_source_needs_review(self):
        """Перевод, совпадающий с исходным текстом, помечается needs_review=True."""
        seg = _seg("s1", 0.0, 1.0, source="Hello", translated="Hello")
        report = build_review_artifact([seg])
        self.assertTrue(report["segments"][0]["needs_review"])

    def test_proper_translation_does_not_need_review(self):
        """Корректный перевод не помечается как needs_review."""
        seg = _seg("s1", 0.0, 1.0, source="Hello", translated="Привет")
        report = build_review_artifact([seg])
        self.assertFalse(report["segments"][0]["needs_review"])


class ReviewCountsTest(unittest.TestCase):
    """Проверяет счётчики в отчёте ревью."""

    def setUp(self):
        self.segments = [
            _seg("s1", 0.0, 1.0, source="Hi",    translated="Привет"),    # OK
            _seg("s2", 1.0, 2.0, source="World",  translated=""),           # needs review
            _seg("s3", 2.0, 3.0, source="Test",   translated="Test"),       # needs review (same)
            _seg("s4", 3.0, 4.0, source="Good",   translated="Хорошо"),    # OK
        ]
        self.report = build_review_artifact(self.segments)

    def test_total_segments(self):
        """total_segments равен числу переданных сегментов."""
        self.assertEqual(self.report["total_segments"], 4)

    def test_needs_review_count(self):
        """needs_review_count считает только проблемные сегменты."""
        self.assertEqual(self.report["needs_review_count"], 2)

    def test_segment_detail_fields(self):
        """Каждая запись содержит все обязательные поля."""
        row = self.report["segments"][0]
        for field in ("id", "start", "end", "source_text", "translated_text",
                      "needs_review", "status"):
            self.assertIn(field, row)


if __name__ == "__main__":
    unittest.main()
