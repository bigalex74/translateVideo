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


class VideoProjectTest(unittest.TestCase):
    """Проверяет сериализацию проекта перевода."""

    def test_project_round_trip_preserves_segments(self):
        """Проект должен сохранять сегменты и артефакты при полном цикле."""

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
        )

        restored = VideoProject.from_dict(project.to_dict())

        self.assertEqual(restored.input_video, Path("input.mp4"))
        self.assertEqual(restored.config.target_language, "es")
        self.assertEqual(restored.segments[0].translated_text, "Hola")
        self.assertEqual(restored.artifacts["source_audio"], "runs/input/source_audio.wav")


if __name__ == "__main__":
    unittest.main()
