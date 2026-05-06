"""Unit-тесты compute_project_stats и quality report логики (Z3.10, Z3.11).

Проверяет корректность расчёта оценок A/B/C/D, топ-проблем, рекомендаций.
"""

import tempfile
import unittest

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment, SegmentStatus, VideoProject, ProjectStatus
from translate_video.core.stats import compute_project_stats
from translate_video.core.store import ProjectStore
from pathlib import Path


def _make_project(segments: list[Segment], status: str = "completed") -> VideoProject:
    """Создать тестовый VideoProject с заданными сегментами."""
    return VideoProject(
        id="test-project",
        input_video=Path("/dev/null"),
        work_dir=Path("/tmp/test"),
        config=PipelineConfig(),
        segments=segments,
        status=ProjectStatus(status),
    )


def _seg(
    source: str = "Hello world",
    translated: str = "Привет мир",
    flags: list[str] | None = None,
    start: float = 0.0,
    end: float = 2.0,
) -> Segment:
    return Segment(
        id=f"seg_{id(source)}",
        start=start, end=end,
        source_text=source,
        translated_text=translated,
        status=SegmentStatus.TRANSLATED,
        qa_flags=flags or [],
    )


class ComputeProjectStatsTest(unittest.TestCase):
    """Тесты функции compute_project_stats."""

    def test_empty_project_returns_valid_structure(self):
        """Пустой проект (без сегментов) — корректная структура без ошибок."""
        project = _make_project([])
        result = compute_project_stats(project)
        self.assertIn("timing", result)
        self.assertIn("segments", result)
        self.assertIn("quality", result)
        self.assertIn("tts", result)
        self.assertIn("summary", result)
        self.assertIn("billing", result)

    def test_segments_count(self):
        """Количество сегментов учитывается корректно."""
        segs = [_seg() for _ in range(5)]
        result = compute_project_stats(_make_project(segs))
        self.assertEqual(result["segments"]["count"], 5)

    def test_source_word_count(self):
        """Подсчёт слов в исходном тексте."""
        segs = [_seg(source="one two three", translated="раз два три")]
        result = compute_project_stats(_make_project(segs))
        self.assertEqual(result["segments"]["source_words"], 3)

    def test_compression_ratio(self):
        """Коэффициент компрессии рассчитывается."""
        segs = [_seg(source="ab", translated="abcd")]  # 2 → 4 символа = 2.0
        result = compute_project_stats(_make_project(segs))
        self.assertAlmostEqual(result["segments"]["compression_ratio"], 2.0)

    def test_empty_translation_counted(self):
        """Пустые переводы учитываются в empty_translations."""
        segs = [
            _seg(translated=""),
            _seg(translated="Перевод"),
        ]
        result = compute_project_stats(_make_project(segs))
        self.assertEqual(result["segments"]["empty_translations"], 1)

    def test_qa_flags_distribution(self):
        """QA-флаги агрегируются в distribution."""
        segs = [
            _seg(flags=["timing_fit_failed"]),
            _seg(flags=["timing_fit_failed"]),
            _seg(flags=["tts_rate_adapted"]),
        ]
        result = compute_project_stats(_make_project(segs))
        dist = result["quality"]["qa_flags_distribution"]
        self.assertEqual(dist.get("timing_fit_failed", 0), 2)
        self.assertEqual(dist.get("tts_rate_adapted", 0), 1)

    def test_segments_with_issues(self):
        """Сегменты с проблемными флагами считаются."""
        segs = [
            _seg(flags=["timing_fit_failed"]),
            _seg(flags=[]),
            _seg(flags=["render_audio_trimmed"]),
        ]
        result = compute_project_stats(_make_project(segs))
        self.assertEqual(result["quality"]["segments_with_issues"], 2)

    def test_tts_overflow_rate(self):
        """overflow_rate считает сегменты с флагом tts_overflow в секции tts."""
        segs = [
            _seg(flags=["tts_overflow"]),
            _seg(flags=[]),
        ]
        result = compute_project_stats(_make_project(segs))
        # tts.overflow_rate = overflow_count / total
        self.assertAlmostEqual(result["tts"]["overflow_rate"], 0.5)

    def test_summary_project_id(self):
        """project_id в summary соответствует проекту."""
        project = _make_project([_seg()])
        result = compute_project_stats(project)
        self.assertEqual(result["summary"]["project_id"], "test-project")

    def test_billing_no_snapshots(self):
        """При отсутствии снапшотов биллинг возвращает has_real_data=False."""
        result = compute_project_stats(_make_project([_seg()]))
        self.assertFalse(result["billing"]["has_real_data"])


class QualityGradeLogicTest(unittest.TestCase):
    """Тесты логики оценок A/B/C/D из quality-report endpoint."""

    def _grade(self, segs: list[Segment]) -> str:
        """Вычислить оценку через stats (имитирует логику endpoint)."""
        project = _make_project(segs)
        stats = compute_project_stats(project)
        quality = stats["quality"]
        issues_rate = (
            quality["segments_with_issues"] / len(segs) if segs else 0
        )
        critical_flags = {"translation_empty", "tts_invalid_slot", "timing_fit_invalid_slot"}
        critical_count = sum(
            quality["qa_flags_distribution"].get(f, 0) for f in critical_flags
        )
        if critical_count > 0 or issues_rate > 0.5:
            return "D"
        elif issues_rate > 0.3:
            return "C"
        elif issues_rate > 0.1:
            return "B"
        return "A"

    def test_grade_a_no_issues(self):
        """Без проблем — оценка A."""
        segs = [_seg(flags=[]) for _ in range(10)]
        self.assertEqual(self._grade(segs), "A")

    def test_grade_b_some_issues(self):
        """15% проблемных — оценка B."""
        segs = [_seg(flags=["timing_fit_failed"])] * 2 + [_seg(flags=[])] * 11
        self.assertEqual(self._grade(segs), "B")

    def test_grade_c_many_issues(self):
        """35% проблемных — оценка C."""
        segs = [_seg(flags=["timing_fit_failed"])] * 4 + [_seg(flags=[])] * 6
        self.assertEqual(self._grade(segs), "C")

    def test_grade_d_majority_issues(self):
        """60% проблемных — оценка D."""
        segs = [_seg(flags=["timing_fit_failed"])] * 6 + [_seg(flags=[])] * 4
        self.assertEqual(self._grade(segs), "D")

    def test_grade_d_critical_flags(self):
        """Критические флаги → D независимо от процента."""
        segs = [_seg(flags=["translation_empty"])]  # 100% критических
        self.assertEqual(self._grade(segs), "D")

    def test_empty_segments_grade_a(self):
        """Пустой список сегментов — оценка A (нет проблем)."""
        self.assertEqual(self._grade([]), "A")


if __name__ == "__main__":
    unittest.main()
