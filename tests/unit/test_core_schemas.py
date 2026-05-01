"""Модульные тесты схем ядра."""

import unittest
from pathlib import Path

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment, VideoProject


class SegmentTest(unittest.TestCase):
    """Проверяет поведение речевого сегмента."""

    def test_duration_is_derived_from_timing(self):
        """Длительность сегмента должна вычисляться из таймкодов."""

        segment = Segment(start=1.25, end=3.75, source_text="Hello")

        self.assertEqual(segment.duration, 2.5)

    def test_invalid_timing_raises(self):
        """Некорректные таймкоды должны отклоняться."""

        with self.assertRaises(ValueError):
            Segment(start=5.0, end=4.9, source_text="Некорректный тайминг")

    def test_empty_source_text(self):
        """Сегмент может иметь пустой текст."""
        
        segment = Segment(start=0.0, end=1.0, source_text="")
        self.assertEqual(segment.source_text, "")

    def test_zero_duration(self):
        """Сегмент может иметь нулевую длительность."""
        
        segment = Segment(start=2.0, end=2.0, source_text="Zero")
        self.assertEqual(segment.duration, 0.0)

    def test_unicode_text(self):
        """Сегмент должен корректно хранить юникод (кириллица, эмодзи, CJK)."""
        
        text = "Привет, мир! 🌍 こんにちは"
        segment = Segment(start=0.0, end=1.0, source_text=text, translated_text=text)
        self.assertEqual(segment.source_text, text)
        self.assertEqual(segment.translated_text, text)


class VideoProjectTest(unittest.TestCase):
    """Проверяет сериализацию проекта перевода."""

    def test_project_round_trip_preserves_segments(self):
        """Проект должен сохранять сегменты и артефакты при полном цикле."""

        from translate_video.core.schemas import ArtifactRecord, ArtifactKind, Stage, StageRun, JobStatus
        
        project = VideoProject(
            input_video=Path("input.mp4"),
            work_dir=Path("runs/input"),
            config=PipelineConfig(source_language="en", target_language="es"),
            segments=[
                Segment(
                    id="seg_1",
                    start=0.0,
                    end=1.0,
                    source_text="Привет",
                    translated_text="Hola",
                )
            ],
            artifacts={"source_audio": "runs/input/source_audio.wav"},
            artifact_records=[
                ArtifactRecord(kind=ArtifactKind.SOURCE_AUDIO, path="a.wav", stage=Stage.EXTRACT_AUDIO)
            ],
            stage_runs=[
                StageRun(stage=Stage.EXTRACT_AUDIO, status=JobStatus.COMPLETED)
            ]
        )

        restored = VideoProject.from_dict(project.to_dict())

        self.assertEqual(restored.input_video, Path("input.mp4"))
        self.assertEqual(restored.config.target_language, "es")
        self.assertEqual(restored.segments[0].translated_text, "Hola")
        self.assertEqual(restored.artifacts["source_audio"], "runs/input/source_audio.wav")
        self.assertEqual(restored.artifact_records[0].kind, ArtifactKind.SOURCE_AUDIO)
        self.assertEqual(restored.stage_runs[0].status, JobStatus.COMPLETED)

    def test_stagerun_from_dict_minimal(self):
        """StageRun должен успешно десериализовываться с минимальным payload."""
        from translate_video.core.schemas import Stage, StageRun, JobStatus
        
        payload = {"stage": "translate"}
        run = StageRun.from_dict(payload)
        
        self.assertEqual(run.stage, Stage.TRANSLATE)
        self.assertEqual(run.status, JobStatus.PENDING)
        self.assertEqual(run.attempt, 1)
        self.assertIsNotNone(run.id)


if __name__ == "__main__":
    unittest.main()
