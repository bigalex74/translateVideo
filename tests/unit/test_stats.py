"""TVIDEO-079: тесты compute_project_stats — проверяет правильное использование
JobStatus.COMPLETED (был ошибочный JobStatus.DONE → AttributeError 500).
"""
import unittest
from translate_video.core.schemas import (
    JobStatus, Segment, SegmentStatus, Stage, StageRun, VideoProject,
)
from translate_video.core.stats import compute_project_stats


def _make_project(**kwargs) -> VideoProject:
    from unittest.mock import MagicMock
    p = MagicMock(spec=VideoProject)
    p.id = "test_project"
    p.status = "completed"
    p.segments = kwargs.get("segments", [])
    p.stage_runs = kwargs.get("stage_runs", [])
    p.config = MagicMock()
    p.config.translation_quality = "amateur"
    p.config.source_language = "en"
    p.config.target_language = "ru"
    p.config.dev_mode = False
    return p


def _make_run(stage: Stage, status: JobStatus,
              started_at: str = "2026-05-01T10:00:00+00:00",
              finished_at: str = "2026-05-01T10:01:00+00:00") -> StageRun:
    r = StageRun(stage=stage, status=status)
    r.started_at = started_at
    r.finished_at = finished_at
    return r


def _make_segment(idx: int, source="Hello", translated="Привет",
                  qa_flags=None) -> Segment:
    s = Segment(
        id=f"seg_{idx}",
        start=float(idx),
        end=float(idx + 1),
        source_text=source,
        status=SegmentStatus.TRANSLATED,
    )
    s.translated_text = translated
    s.qa_flags = qa_flags or []
    s.tts_path = None
    s.tts_text = None
    s.confidence = 0.95
    return s


class ComputeProjectStatsJobStatusFixed(unittest.TestCase):
    """TVIDEO-079: compute_project_stats использует JobStatus.COMPLETED, не DONE."""

    def test_no_attributeerror_with_completed_runs(self):
        """compute_project_stats не бросает AttributeError при COMPLETED stage_runs."""
        runs = [
            _make_run(Stage.EXTRACT_AUDIO, JobStatus.COMPLETED),
            _make_run(Stage.TRANSCRIBE, JobStatus.COMPLETED),
            _make_run(Stage.TRANSLATE, JobStatus.COMPLETED,
                      started_at="2026-05-01T10:02:00",
                      finished_at="2026-05-01T10:05:00"),
        ]
        project = _make_project(stage_runs=runs)
        # Не должно бросать AttributeError: DONE
        result = compute_project_stats(project)
        self.assertIn("timing", result)
        self.assertIn("summary", result)

    def test_stage_times_computed_for_completed_runs(self):
        """Время этапов вычисляется для COMPLETED (не DONE)."""
        runs = [
            _make_run(Stage.TRANSLATE, JobStatus.COMPLETED,
                      started_at="2026-05-01T10:00:00+00:00",
                      finished_at="2026-05-01T10:02:00+00:00"),  # 120s
        ]
        project = _make_project(stage_runs=runs)
        result = compute_project_stats(project)
        stage_times = result["timing"]["stage_times"]
        self.assertIn("translate", stage_times)
        self.assertAlmostEqual(stage_times["translate"], 120.0, places=0)

    def test_failed_runs_not_in_stage_times(self):
        """FAILED stage_runs не попадают в stage_times."""
        runs = [
            _make_run(Stage.TRANSLATE, JobStatus.FAILED),
        ]
        project = _make_project(stage_runs=runs)
        result = compute_project_stats(project)
        self.assertEqual(result["timing"]["stage_times"], {})

    def test_stages_done_counts_completed(self):
        """stages_done считает COMPLETED, а не 'done'."""
        runs = [
            _make_run(Stage.EXTRACT_AUDIO, JobStatus.COMPLETED),
            _make_run(Stage.TRANSCRIBE, JobStatus.COMPLETED),
            _make_run(Stage.TRANSLATE, JobStatus.FAILED),
        ]
        project = _make_project(stage_runs=runs)
        result = compute_project_stats(project)
        self.assertEqual(result["summary"]["stages_done"], 2)
        self.assertEqual(result["summary"]["stages_failed"], 1)

    def test_empty_project_no_crash(self):
        """Пустой проект без сегментов и runs не падает."""
        project = _make_project()
        result = compute_project_stats(project)
        self.assertEqual(result["segments"]["count"], 0)
        self.assertIsNone(result["timing"]["total_elapsed_s"])

    def test_qa_flags_distribution(self):
        """qa_flags_distribution правильно считает флаги."""
        segs = [
            _make_segment(0, qa_flags=["tts_overflow_natural_rate", "timeline_shifted"]),
            _make_segment(1, qa_flags=["tts_overflow_natural_rate"]),
            _make_segment(2, qa_flags=["rewrite_provider_rate_limited"]),
        ]
        project = _make_project(segments=segs)
        result = compute_project_stats(project)
        dist = result["quality"]["qa_flags_distribution"]
        self.assertEqual(dist.get("tts_overflow_natural_rate"), 2)
        self.assertEqual(dist.get("timeline_shifted"), 1)
        self.assertEqual(dist.get("rewrite_provider_rate_limited"), 1)


if __name__ == "__main__":
    unittest.main()
