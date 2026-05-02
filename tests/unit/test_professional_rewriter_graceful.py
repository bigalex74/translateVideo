"""TVIDEO-081: тест что pipeline НЕ прерывается при провале professional rewriter.

Регрессионный тест на конкретный сценарий:
- translation_quality = "professional"
- professional rewriter не возвращает полезного ответа
- До фикса: TimingFitStage.FAILED → pipeline abort → видео не создавалось
- После фикса: stage остаётся completed, QA-флаг добавляется, pipeline продолжается
"""
import threading
import unittest

from translate_video.core.schemas import JobStatus
from translate_video.timing.cloud import CloudFallbackTimingRewriter


class ProfessionalRewriterGracefulFallbackTest(unittest.TestCase):
    """TVIDEO-081: professional rewriter провал не роняет pipeline."""

    def test_no_raise_when_all_providers_fail_in_professional_mode(self):
        """При allow_rule_based_fallback=False реврайтер НЕ бросает — возвращает текст."""
        router = CloudFallbackTimingRewriter(
            providers=[],
            allow_rule_based_fallback=False,
        )

        original = "Это длинный текст перевода который не влезает в тайминг"
        result = router.rewrite(original, source_text="source", max_chars=10, attempt=1)

        # Возвращает исходный текст, не бросает
        self.assertEqual(result, original)

    def test_qa_flag_added_on_professional_rewriter_failure(self):
        """QA-флаг rewrite_provider_no_timing_fit добавляется при провале."""
        router = CloudFallbackTimingRewriter(
            providers=[],
            allow_rule_based_fallback=False,
        )

        router.rewrite("длинный текст", source_text="src", max_chars=5, attempt=1)
        events = router.consume_events()

        self.assertIn("rewrite_provider_no_timing_fit", events)

    def test_qa_flag_absent_when_rewrite_succeeds(self):
        """QA-флаг rewrite_provider_no_timing_fit НЕ добавляется когда rewrite успешен."""
        from tests.unit.test_cloud_timing import _StaticProvider  # type: ignore[import]

        router = CloudFallbackTimingRewriter(
            providers=[_StaticProvider("gemini", "кратко")],
            allow_rule_based_fallback=True,
        )

        result = router.rewrite("длинный текст", source_text="src", max_chars=10, attempt=1)
        events = router.consume_events()

        self.assertEqual(result, "кратко")
        self.assertNotIn("rewrite_provider_no_timing_fit", events)

    def test_rewrite_provider_failed_flag_present_before_no_timing_fit(self):
        """rewrite_provider_failed выставляется ДО rewrite_provider_no_timing_fit."""
        from tests.unit.test_cloud_timing import _StaticProvider  # type: ignore[import]

        # Провайдер возвращает текст длиннее max_chars → rejected → failed
        router = CloudFallbackTimingRewriter(
            providers=[_StaticProvider("gemini", "всё равно длинный текст")],
            allow_rule_based_fallback=False,
        )

        router.rewrite("исходный", source_text="src", max_chars=5, attempt=1)
        events = router.consume_events()

        self.assertIn("rewrite_provider_failed", events)
        self.assertIn("rewrite_provider_no_timing_fit", events)

    def test_pipeline_continues_after_timing_fit_with_failed_rewriter(self):
        """TVIDEO-081: end-to-end — TimingFitStage не FAILED при провале rewriter.

        Использует fake-pipeline с Patched rewriter который всегда возвращает rejected.
        """
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock, patch

        from translate_video.core.config import PipelineConfig
        from translate_video.core.schemas import Segment, SegmentStatus
        from translate_video.core.store import ProjectStore
        from translate_video.pipeline import ExportSubtitlesStage
        from translate_video.pipeline.context import StageContext
        from translate_video.pipeline.stages import TimingFitStage
        from translate_video.timing.natural import NaturalVoiceTimingFitter

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            store = ProjectStore(tmp_path / "runs")
            cfg = PipelineConfig()
            cfg.translation_quality = "professional"
            project = store.create_project(
                tmp_path / "inp.mp4", config=cfg, project_id="test_timing_graceful"
            )
            (tmp_path / "inp.mp4").write_bytes(b"FAKE")

            seg = Segment(id="s1", start=0.0, end=1.0, source_text="Hello")
            seg.translated_text = "Привет мир, длинный текст"
            seg.qa_flags = []
            seg.tts_path = None
            seg.tts_text = None
            seg.confidence = None
            seg.status = SegmentStatus.TRANSLATED
            project.segments = [seg]
            store.save_segments(project, [seg], translated=True)

            cancel = threading.Event()
            ctx = StageContext(project=project, store=store, cancel_event=cancel)

            # Создаём fitter с rewriter напрямую (конструктор принимает rewriter)
            failing_rewriter = CloudFallbackTimingRewriter(
                providers=[],
                allow_rule_based_fallback=False,
            )
            fitter = NaturalVoiceTimingFitter(rewriter=failing_rewriter)
            stage = TimingFitStage(fitter)
            run = stage.run(ctx)

            # Ключевое условие: статус НЕ FAILED — pipeline не прерывается
            self.assertNotEqual(
                run.status,
                JobStatus.FAILED,
                f"TimingFitStage не должна падать при провале rewriter. "
                f"status={run.status}, error={run.error}",
            )


if __name__ == "__main__":
    unittest.main()
