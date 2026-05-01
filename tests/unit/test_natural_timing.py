"""Тесты естественной подгонки текста под тайминг без ускорения TTS."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import ArtifactKind, JobStatus, Segment, Stage, VideoProject
from translate_video.core.store import ProjectStore
from translate_video.pipeline.context import StageContext
from translate_video.pipeline.stages import TimingFitStage
from translate_video.timing.natural import NaturalVoiceTimingFitter, RuleBasedTimingRewriter


class NaturalVoiceTimingFitterTest(unittest.TestCase):
    """Проверяет подготовку текста к естественной озвучке."""

    def test_short_text_is_unchanged(self):
        """Короткий текст не переписывается и попадает в tts_text."""

        project = _project(PipelineConfig(target_chars_per_second=14.0, use_cloud_timing_rewriter=False))
        segment = Segment(
            id="seg_1",
            start=0.0,
            end=2.0,
            source_text="Hello",
            translated_text="Привет.",
        )

        result = NaturalVoiceTimingFitter().fit(project, [segment])

        self.assertEqual(result[0].translated_text, "Привет.")
        self.assertEqual(result[0].tts_text, "Привет.")
        self.assertEqual(result[0].qa_flags, [])

    def test_rewriter_compacts_text_when_possible(self):
        """Очевидно длинные обороты заменяются короткими эквивалентами."""

        project = _project(PipelineConfig(target_chars_per_second=14.0, use_cloud_timing_rewriter=False))
        segment = Segment(
            id="seg_1",
            start=0.0,
            end=2.0,
            source_text="Now this is important.",
            translated_text="На сегодняшний день это является важным.",
        )

        result = NaturalVoiceTimingFitter().fit(project, [segment])

        self.assertEqual(result[0].translated_text, "сейчас это важно.")
        self.assertEqual(result[0].tts_text, "сейчас это важно.")
        self.assertIn("translation_rewritten_for_timing", result[0].qa_flags)
        self.assertNotIn("timing_fit_failed", result[0].qa_flags)

    def test_failed_fit_is_reported_without_truncation(self):
        """Если безопасно сократить нельзя, текст сохраняется и помечается QA-флагом."""

        original = "Очень длинный технический текст без очевидных вводных слов и сокращаемых оборотов."
        project = _project(PipelineConfig(target_chars_per_second=6.0, use_cloud_timing_rewriter=False))
        segment = Segment(
            id="seg_1",
            start=0.0,
            end=2.0,
            source_text="Long text.",
            translated_text=original,
        )

        result = NaturalVoiceTimingFitter().fit(project, [segment])

        self.assertEqual(result[0].translated_text, original)
        self.assertEqual(result[0].tts_text, original)
        self.assertIn("timing_fit_failed", result[0].qa_flags)

    def test_invalid_slot_is_reported(self):
        """Нулевая длительность сегмента не ломает подгонку."""

        project = _project(PipelineConfig(use_cloud_timing_rewriter=False))
        segment = Segment(
            id="seg_1",
            start=1.0,
            end=1.0,
            source_text="Hello",
            translated_text="Привет.",
        )

        result = NaturalVoiceTimingFitter().fit(project, [segment])

        self.assertIn("timing_fit_invalid_slot", result[0].qa_flags)

    def test_progress_callback_receives_segment_progress(self):
        """Fitter должен отдавать прогресс после каждого обработанного сегмента."""

        project = _project(PipelineConfig(use_cloud_timing_rewriter=False))
        segments = [
            Segment(id="seg_1", start=0.0, end=1.0, source_text="One", translated_text="Один."),
            Segment(id="seg_2", start=1.0, end=2.0, source_text="Two", translated_text="Два."),
        ]
        events: list[tuple[int, int, str | None]] = []

        NaturalVoiceTimingFitter().fit(
            project,
            segments,
            progress_callback=lambda current, total, message: events.append(
                (current, total, message)
            ),
        )

        self.assertEqual(events[0], (0, 2, "Подготовка сегментов"))
        self.assertIn((1, 2, "Готово 1/2"), events)
        self.assertEqual(events[-1], (2, 2, "Готово 2/2"))


class RuleBasedTimingRewriterTest(unittest.TestCase):
    """Проверяет безопасные rule-based сокращения."""

    def test_rewriter_does_not_hard_cut_text(self):
        """Rewriter не должен резать строку по лимиту символов."""

        text = "Уникальный смысловой текст без вводных слов."
        rewritten = RuleBasedTimingRewriter().rewrite(
            text,
            source_text="source",
            max_chars=5,
            attempt=3,
        )

        self.assertEqual(rewritten, text)


class TimingFitStageTest(unittest.TestCase):
    """Проверяет этап timing_fit в пайплайне."""

    def test_stage_saves_translated_transcript_with_timing_stage(self):
        """Этап сохраняет обновлённый transcript и stage metadata."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project(
                "lesson.mp4",
                config=PipelineConfig(target_chars_per_second=14.0, use_cloud_timing_rewriter=False),
                project_id="lesson",
            )
            project.segments = [
                Segment(
                    id="seg_1",
                    start=0.0,
                    end=2.0,
                    source_text="Hello",
                    translated_text="На сегодняшний день это является важным.",
                )
            ]
            store.save_segments(project, project.segments, translated=True)

            run = TimingFitStage(NaturalVoiceTimingFitter()).run(
                StageContext(project=project, store=store)
            )
            restored = store.load_project(project.work_dir)
            record = store.get_artifact(restored, ArtifactKind.TRANSLATED_TRANSCRIPT)

            self.assertEqual(run.status, JobStatus.COMPLETED)
            self.assertEqual(record.stage, Stage.TIMING_FIT)
            self.assertIn("translation_rewritten_for_timing", restored.segments[0].qa_flags)
            self.assertEqual(restored.stage_runs[0].progress_current, 1)
            self.assertEqual(restored.stage_runs[0].progress_total, 1)


def _project(config: PipelineConfig) -> VideoProject:
    """Создать минимальный проект для unit-тестов timing."""

    return VideoProject(
        id="lesson",
        input_video=Path("lesson.mp4"),
        work_dir=Path("runs/lesson"),
        config=config,
    )


if __name__ == "__main__":
    unittest.main()
