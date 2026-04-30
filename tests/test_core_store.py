import tempfile
import unittest
from pathlib import Path

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment
from translate_video.core.store import ProjectStore


class ProjectStoreTest(unittest.TestCase):
    def test_create_project_writes_layout_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")

            project = store.create_project(
                "lesson.mp4",
                config=PipelineConfig(source_language="en", target_language="ru"),
                project_id="lesson",
            )

            self.assertTrue((project.work_dir / "project.json").exists())
            self.assertTrue((project.work_dir / "settings.json").exists())
            self.assertTrue((project.work_dir / "subtitles").is_dir())
            self.assertTrue((project.work_dir / "tts").is_dir())
            self.assertTrue((project.work_dir / "output").is_dir())

            restored = store.load_project(project.work_dir)
            self.assertEqual(restored.id, "lesson")
            self.assertEqual(restored.config.source_language, "en")

    def test_save_segments_updates_project_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project("clip.mp4", project_id="clip")
            segments = [Segment(id="seg_1", start=0.0, end=1.0, source_text="Hello")]

            output_path = store.save_segments(project, segments, translated=True)

            self.assertTrue(output_path.exists())
            restored = store.load_project(project.work_dir)
            self.assertIn("translated_transcript", restored.artifacts)
            self.assertEqual(restored.segments[0].source_text, "Hello")


if __name__ == "__main__":
    unittest.main()

