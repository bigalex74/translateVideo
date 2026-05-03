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


class EffectiveTtsSpeedTest(unittest.TestCase):
    """Проверяет _effective_tts_speed — мультипликатор CPS по скорости TTS."""

    def _speed(self, **kwargs) -> float:
        from translate_video.timing.natural import _effective_tts_speed
        return _effective_tts_speed(PipelineConfig(**kwargs))

    def test_no_provider_returns_1(self):
        """Edge TTS (пустой провайдер) → скорость 1.0."""
        self.assertAlmostEqual(self._speed(professional_tts_provider=""), 1.0)

    def test_neuroapi_provider_returns_calibration_factor(self):
        """neuroapi (OpenAI-совместимый) → коэффициент 0.82 (tts-1 default)."""
        v = self._speed(
            professional_tts_provider="neuroapi",
            professional_tts_model="tts-1",
        )
        self.assertAlmostEqual(v, 0.82)

    def test_polza_gpt4o_mini_tts_returns_calibrated_factor(self):
        """polza + gpt-4o-mini-tts → коэффициент 0.78 (замерено)."""
        v = self._speed(
            professional_tts_provider="polza",
            professional_tts_model="openai/gpt-4o-mini-tts",
        )
        self.assertAlmostEqual(v, 0.78)

    def test_polza_elevenlabs_returns_calibrated_factor(self):
        """polza + ElevenLabs → коэффициент 0.90."""
        v = self._speed(
            professional_tts_provider="polza",
            professional_tts_model="elevenlabs/text-to-speech-turbo-2-5",
        )
        self.assertAlmostEqual(v, 0.90)

    def test_unknown_provider_returns_1(self):
        """Неизвестный провайдер → скорость 1.0 (Edge TTS дефолт)."""
        self.assertAlmostEqual(self._speed(professional_tts_provider="some_other"), 1.0)

    def test_yandex_single_speed_15(self):
        """Yandex single voice, speed=1.5 → возвращает 1.5."""
        v = self._speed(
            professional_tts_provider="yandex",
            professional_tts_speed=1.5,
            voice_strategy="single",
        )
        self.assertAlmostEqual(v, 1.5)

    def test_yandex_two_voices_takes_minimum(self):
        """Yandex two_voices: speed_1=2.0, speed_2=1.2 → возвращает 1.2 (консервативно)."""
        v = self._speed(
            professional_tts_provider="yandex",
            professional_tts_speed=2.0,
            professional_tts_speed_2=1.2,
            voice_strategy="two_voices",
        )
        self.assertAlmostEqual(v, 1.2)

    def test_yandex_speed_1_is_identity(self):
        """Speed=1.0 — нет изменений в CPS."""
        v = self._speed(
            professional_tts_provider="yandex",
            professional_tts_speed=1.0,
        )
        self.assertAlmostEqual(v, 1.0)


class SpeedAwareTimingFitTest(unittest.TestCase):
    """Проверяет что при speed>1.0 timing_fit позволяет больше текста."""

    BASE_TEXT = "А" * 42  # 42 символа: при CPS=14 и duration=2.0 — ровно максимум

    def _fit(self, speed: float) -> str:
        """Прогнать текст через timing_fit и вернуть результат."""
        cfg = PipelineConfig(
            target_chars_per_second=14.0,
            use_cloud_timing_rewriter=False,
            professional_tts_provider="yandex",
            professional_tts_speed=speed,
        )
        project = _project(cfg)
        segment = Segment(
            id="seg_1",
            start=0.0,
            end=3.0,  # 3 сек × 14 cps = 42 символа базовый лимит
            source_text="Hello",
            translated_text=self.BASE_TEXT,
        )
        fitter = NaturalVoiceTimingFitter(rewriter=RuleBasedTimingRewriter())
        result = fitter.fit(project, [segment])
        return result[0].tts_text

    def test_speed_1_text_fits_exactly(self):
        """При speed=1.0 текст из 42 символов ровно влезает (не сокращается)."""
        result = self._fit(1.0)
        self.assertEqual(len(result), len(self.BASE_TEXT))

    def test_speed_15_allows_63_chars(self):
        """При speed=1.5 лимит увеличивается до 63 символов — текст 42 символа не трогается."""
        # Создаём текст длиннее базового лимита (42), но меньше speed=1.5 лимита (63)
        long_text = "А" * 55
        cfg = PipelineConfig(
            target_chars_per_second=14.0,
            use_cloud_timing_rewriter=False,
            professional_tts_provider="yandex",
            professional_tts_speed=1.5,
        )
        project = _project(cfg)
        segment = Segment(
            id="seg_1", start=0.0, end=3.0,
            source_text="Hello",
            translated_text=long_text,
        )
        fitter = NaturalVoiceTimingFitter(rewriter=RuleBasedTimingRewriter())
        result = fitter.fit(project, [segment])
        # При speed=1.5: effective_cps = 14 * 1.5 = 21, max_chars = 21 * 3 = 63
        # Текст из 55 символов должен пройти без изменений
        self.assertEqual(result[0].tts_text, long_text,
                         "При speed=1.5 текст из 55 символов не должен сокращаться")
        self.assertNotIn("translation_rewritten_for_timing", result[0].qa_flags)

    def test_speed_05_requires_shorter_text(self):
        """При speed=0.5 лимит уменьшается вдвое — даже 42 символа не влезают."""
        cfg = PipelineConfig(
            target_chars_per_second=14.0,
            use_cloud_timing_rewriter=False,
            professional_tts_provider="yandex",
            professional_tts_speed=0.5,
        )
        project = _project(cfg)
        # 42 символа при speed=0.5: effective_cps=7, max_chars=7*3=21 → не влезет
        segment = Segment(
            id="seg_1", start=0.0, end=3.0,
            source_text="Hello",
            translated_text=self.BASE_TEXT,
        )
        fitter = NaturalVoiceTimingFitter(rewriter=RuleBasedTimingRewriter())
        result = fitter.fit(project, [segment])
        # Ожидаем timing_fit_failed (rule-based не может сократить "А"×42)
        self.assertIn("timing_fit_failed", result[0].qa_flags)


if __name__ == "__main__":
    unittest.main()
