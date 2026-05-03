"""Тесты этапа встраивания субтитров в выходное видео (TVIDEO-126)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import ArtifactKind, JobStatus, Stage
from translate_video.core.store import ProjectStore
from translate_video.pipeline import EmbedSubtitlesStage, StageContext


class EmbedSubtitlesStageTest(unittest.TestCase):
    """Проверяет EmbedSubtitlesStage в режимах none/soft/burn."""

    def _make_context(
        self, temp_dir: str, subtitle_embed_mode: str = "none"
    ) -> tuple[StageContext, ProjectStore]:
        store = ProjectStore(Path(temp_dir) / "runs")
        project = store.create_project(
            "video.mp4",
            config=PipelineConfig(subtitle_embed_mode=subtitle_embed_mode),
            project_id="embed_test",
        )
        # Создаём выходное видео и SRT
        output_dir = project.work_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        video_file = output_dir / "translated.mp4"
        video_file.write_bytes(b"fake-video")

        subs_dir = project.work_dir / "subtitles"
        subs_dir.mkdir(parents=True, exist_ok=True)
        srt_file = subs_dir / "translated.srt"
        srt_file.write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nПривет, мир!\n\n",
            encoding="utf-8",
        )

        # Регистрируем артефакты output_video и subtitles
        store.add_artifact(project, ArtifactKind.OUTPUT_VIDEO, video_file, Stage.RENDER, content_type="video/mp4")
        store.add_artifact(project, ArtifactKind.SUBTITLES, srt_file, Stage.EXPORT, content_type="text/plain")

        context = StageContext(project=project, store=store)
        return context, store

    def test_mode_none_skips_embedding(self):
        """Режим 'none' должен пропустить этап без ошибок и без output."""

        with tempfile.TemporaryDirectory() as temp_dir:
            context, _ = self._make_context(temp_dir, subtitle_embed_mode="none")
            run = EmbedSubtitlesStage().run(context)

        self.assertEqual(run.status, JobStatus.COMPLETED)
        self.assertEqual(run.outputs, [])

    def test_mode_soft_calls_ffmpeg_with_copy(self):
        """Режим 'soft' вызывает ffmpeg с -c copy -c:s mov_text."""

        with tempfile.TemporaryDirectory() as temp_dir:
            context, store = self._make_context(temp_dir, subtitle_embed_mode="soft")
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run",
                       return_value=mock_result) as mock_run:
                # ffmpeg создаёт выходной файл вручную
                output = (
                    context.project.work_dir / "output" / "translated_sub_soft.mp4"
                )
                output.write_bytes(b"fake-video-with-soft-subs")
                run = EmbedSubtitlesStage().run(context)

        self.assertEqual(run.status, JobStatus.COMPLETED)
        cmd = mock_run.call_args[0][0]
        self.assertIn("-c", cmd)
        self.assertIn("copy", cmd)
        self.assertIn("mov_text", cmd)

    def test_mode_burn_calls_ffmpeg_with_subtitles_filter(self):
        """Режим 'burn' вызывает ffmpeg с -vf subtitles=..."""

        with tempfile.TemporaryDirectory() as temp_dir:
            context, store = self._make_context(temp_dir, subtitle_embed_mode="burn")
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run",
                       return_value=mock_result) as mock_run:
                output = (
                    context.project.work_dir / "output" / "translated_sub_burn.mp4"
                )
                output.write_bytes(b"fake-burned-video")
                run = EmbedSubtitlesStage().run(context)

        self.assertEqual(run.status, JobStatus.COMPLETED)
        cmd = mock_run.call_args[0][0]
        self.assertTrue(any("subtitles=" in arg for arg in cmd))
        self.assertIn("-c:a", cmd)
        self.assertIn("copy", cmd)

    def test_mode_soft_registers_output_video_with_subs_artifact(self):
        """После успешного embed должен появиться артефакт output_video_with_subs."""

        with tempfile.TemporaryDirectory() as temp_dir:
            context, store = self._make_context(temp_dir, subtitle_embed_mode="soft")
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run",
                       return_value=mock_result):
                output = (
                    context.project.work_dir / "output" / "translated_sub_soft.mp4"
                )
                output.write_bytes(b"fake-video-with-soft-subs")
                EmbedSubtitlesStage().run(context)

            restored = store.load_project(context.project.work_dir)
            self.assertIn("output_video_with_subs", restored.artifacts)


    def test_ffmpeg_error_fails_stage(self):
        """Если ffmpeg возвращает ненулевой код — этап должен упасть."""

        with tempfile.TemporaryDirectory() as temp_dir:
            context, _ = self._make_context(temp_dir, subtitle_embed_mode="burn")
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Error: no such filter 'subtitles'"

            with patch("subprocess.run",
                       return_value=mock_result):
                run = EmbedSubtitlesStage().run(context)

        self.assertEqual(run.status, JobStatus.FAILED)
        self.assertIn("ffmpeg", run.error)


if __name__ == "__main__":
    unittest.main()
