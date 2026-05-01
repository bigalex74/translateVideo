"""Модульные тесты хранилища проектов и артефактов."""

import tempfile
import unittest
from pathlib import Path

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import ArtifactKind, JobStatus, Segment, Stage, StageRun
from translate_video.core.store import ProjectStore, sanitize_filename, sanitize_project_id


class ProjectStoreTest(unittest.TestCase):
    """Проверяет сохранение проектов, артефактов и запусков этапов."""

    def test_create_project_writes_layout_and_metadata(self):
        """Создание проекта должно записывать базовую структуру и метаданные."""

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
            self.assertEqual(restored.work_dir.name, restored.id)
            self.assertEqual(restored.config.source_language, "en")

    def test_generated_project_id_matches_work_dir_name(self):
        """Автоматический ID проекта должен совпадать с именем рабочей папки."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")

            project = store.create_project("lesson.mp4")

            self.assertEqual(project.work_dir.name, project.id)
            self.assertTrue(project.id.startswith("lesson-"))

    def test_create_project_rejects_path_traversal_id(self):
        """ID проекта не должен позволять выходить из корня runs."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")

            with self.assertRaises(ValueError):
                store.create_project("lesson.mp4", project_id="../evil")

    def test_attach_input_video_copies_source_into_project(self):
        """Исходное видео должно копироваться в рабочую папку проекта."""

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "upload.mp4"
            source.write_bytes(b"video")
            store = ProjectStore(root / "runs")
            project = store.create_project(source, project_id="lesson")

            copied = store.attach_input_video(project, source)
            restored = store.load_project(project.work_dir)

            self.assertEqual(copied, project.work_dir / "input.mp4")
            self.assertEqual(copied.read_bytes(), b"video")
            self.assertEqual(restored.input_video, copied)

    def test_sanitize_helpers_block_unsafe_values(self):
        """Нормализация имен должна запрещать небезопасные пути."""

        self.assertEqual(sanitize_project_id("Мой проект!"), "Мой-проект")
        self.assertEqual(sanitize_filename("../video.mp4"), "video.mp4")
        with self.assertRaises(ValueError):
            sanitize_project_id("bad/project")

    def test_save_segments_updates_project_artifacts(self):
        """Сохранение сегментов должно обновлять артефакты проекта."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project("clip.mp4", project_id="clip")
            segments = [Segment(id="seg_1", start=0.0, end=1.0, source_text="Привет")]

            output_path = store.save_segments(project, segments, translated=True)

            self.assertTrue(output_path.exists())
            restored = store.load_project(project.work_dir)
            self.assertIn("translated_transcript", restored.artifacts)
            self.assertEqual(restored.artifacts["translated_transcript"], "transcript.translated.json")
            self.assertEqual(restored.artifact_records[0].kind, "translated_transcript")
            self.assertEqual(restored.artifact_records[0].metadata["segments"], 1)
            self.assertEqual(restored.segments[0].source_text, "Привет")

    def test_add_artifact_stores_relative_typed_record(self):
        """Новый артефакт должен сохраняться как относительная типизированная запись."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project("clip.mp4", project_id="clip")
            audio_path = project.work_dir / "source_audio.wav"

            record = store.add_artifact(
                project,
                kind=ArtifactKind.SOURCE_AUDIO,
                path=audio_path,
                stage=Stage.EXTRACT_AUDIO,
                content_type="audio/wav",
            )

            restored = store.load_project(project.work_dir)
            self.assertEqual(record.path, "source_audio.wav")
            self.assertEqual(restored.artifacts["source_audio"], "source_audio.wav")
            self.assertEqual(restored.artifact_records[0].stage, Stage.EXTRACT_AUDIO)

    def test_record_stage_run_replaces_same_run_id(self):
        """Повторная запись запуска этапа с тем же ID должна заменять старую."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project("clip.mp4", project_id="clip")
            first = StageRun(id="stage_1", stage=Stage.TRANSCRIBE, status=JobStatus.RUNNING)
            completed = StageRun(id="stage_1", stage=Stage.TRANSCRIBE, status=JobStatus.COMPLETED)

            store.record_stage_run(project, first)
            store.record_stage_run(project, completed)

            restored = store.load_project(project.work_dir)
            self.assertEqual(len(restored.stage_runs), 1)
            self.assertEqual(restored.stage_runs[0].status, JobStatus.COMPLETED)

    def test_repeated_save_segments_replaces_artifact(self):
        """Повторное сохранение сегментов заменяет существующий артефакт того же типа."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project("clip.mp4", project_id="clip")
            
            segments1 = [Segment(id="seg_1", start=0.0, end=1.0, source_text="Первый")]
            store.save_segments(project, segments1, translated=True)
            
            segments2 = [Segment(id="seg_2", start=0.0, end=1.0, source_text="Второй")]
            store.save_segments(project, segments2, translated=True)

            restored = store.load_project(project.work_dir)
            
            # Должен быть только один артефакт translated_transcript
            translated_records = [r for r in restored.artifact_records if r.kind == ArtifactKind.TRANSLATED_TRANSCRIPT]
            self.assertEqual(len(translated_records), 1)
            self.assertEqual(restored.segments[0].source_text, "Второй")

    def test_load_non_existent_project_raises(self):
        """Загрузка несуществующего проекта должна вызывать FileNotFoundError."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            with self.assertRaises(FileNotFoundError):
                store.load_project(Path(temp_dir) / "runs" / "non_existent")

    def test_export_subtitles_empty_segments(self):
        """Экспорт пустых субтитров должен завершаться успешно, но создавать пустой файл."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project("clip.mp4", project_id="clip")
            
            # segments изначально пуст
            output_path = store.export_subtitles(project, fmt="srt")
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8").strip(), "")

    def test_export_subtitles_invalid_format_raises(self):
        """Экспорт в неизвестный формат должен вызывать ValueError."""

        with tempfile.TemporaryDirectory() as temp_dir:
            store = ProjectStore(Path(temp_dir) / "runs")
            project = store.create_project("clip.mp4", project_id="clip")
            
            with self.assertRaises(ValueError):
                store.export_subtitles(project, fmt="invalid_format")


if __name__ == "__main__":
    unittest.main()
