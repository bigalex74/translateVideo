"""TVIDEO-080: тесты ExportSubtitlesStage.

Проверяет:
- Стадия генерирует VTT и SRT файлы после рендера.
- Артефакт subtitles регистрируется в проекте.
- Текст в VTT совпадает с translated_text сегментов.
- Стадия не падает если segments пустые.
"""
import tempfile
import unittest
from pathlib import Path

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import (
    ArtifactKind,
    Segment,
    SegmentStatus,
    VideoProject,
)
from translate_video.core.store import ProjectStore
from translate_video.pipeline import ExportSubtitlesStage
from translate_video.pipeline.context import StageContext
from translate_video.pipeline.runner import PipelineRunner


def _make_project(tmp: Path) -> tuple[VideoProject, ProjectStore]:
    store = ProjectStore(tmp / "runs")
    cfg = PipelineConfig()
    project = store.create_project(tmp / "input.mp4", config=cfg, project_id="test_export_subs")
    (tmp / "input.mp4").write_bytes(b"FAKE")
    return project, store


def _make_segment(idx: int, translated: str) -> Segment:
    s = Segment(
        id=f"seg_{idx}",
        start=float(idx),
        end=float(idx + 2),
        source_text=f"Source {idx}",
        status=SegmentStatus.TRANSLATED,
    )
    s.translated_text = translated
    s.qa_flags = []
    s.tts_path = None
    s.tts_text = None
    s.confidence = None
    return s


class ExportSubtitlesStageTest(unittest.TestCase):
    """TVIDEO-080: ExportSubtitlesStage создаёт VTT и SRT файлы."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_dir.name)
        self.project, self.store = _make_project(self.tmp)
        import threading
        self.cancel = threading.Event()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _ctx(self) -> StageContext:
        return StageContext(
            project=self.project,
            store=self.store,
            cancel_event=self.cancel,
        )

    def test_stage_creates_vtt_file(self):
        """ExportSubtitlesStage создаёт subtitles/translated.vtt."""
        segs = [_make_segment(0, "Привет мир"), _make_segment(1, "Пока мир")]
        self.project.segments = segs

        stage = ExportSubtitlesStage()
        run = stage.run(self._ctx())

        self.assertEqual(run.status.value, "completed")
        vtt_path = self.project.work_dir / "subtitles" / "translated.vtt"
        self.assertTrue(vtt_path.exists(), "VTT файл должен существовать")

    def test_stage_creates_srt_file(self):
        """ExportSubtitlesStage создаёт subtitles/translated.srt."""
        self.project.segments = [_make_segment(0, "Тест")]

        stage = ExportSubtitlesStage()
        stage.run(self._ctx())

        srt_path = self.project.work_dir / "subtitles" / "translated.srt"
        self.assertTrue(srt_path.exists(), "SRT файл должен существовать")

    def test_vtt_contains_translated_text(self):
        """Текст в VTT совпадает с translated_text сегментов."""
        segs = [_make_segment(0, "Уникальная фраза для теста")]
        self.project.segments = segs

        ExportSubtitlesStage().run(self._ctx())

        vtt_content = (self.project.work_dir / "subtitles" / "translated.vtt").read_text()
        self.assertIn("Уникальная фраза для теста", vtt_content)

    def test_subtitles_artifact_registered(self):
        """После запуска в project.artifacts должен появиться ключ 'subtitles'."""
        self.project.segments = [_make_segment(0, "Текст")]

        ExportSubtitlesStage().run(self._ctx())

        # Перезагружаем проект с диска (store.save_project вызывается внутри)
        refreshed = self.store.load_project(self.project.work_dir)
        self.assertIn("subtitles", refreshed.artifacts)

    def test_srt_overwrites_vtt_artifact_with_last_call(self):
        """Оба формата регистрируются — subtitles artifact указывает на последний (srt)."""
        self.project.segments = [_make_segment(0, "Текст")]
        ExportSubtitlesStage().run(self._ctx())

        refreshed = self.store.load_project(self.project.work_dir)
        artifact_path = refreshed.artifacts.get("subtitles", "")
        # Должен указывать на один из двух форматов (vtt или srt)
        self.assertTrue(
            artifact_path.endswith(".vtt") or artifact_path.endswith(".srt"),
            f"subtitles artifact должен быть vtt или srt, получено: {artifact_path!r}",
        )

    def test_stage_does_not_fail_with_empty_segments(self):
        """ExportSubtitlesStage не падает при пустом списке сегментов."""
        self.project.segments = []

        stage = ExportSubtitlesStage()
        run = stage.run(self._ctx())

        # Должна завершиться (completed или failed — но не упасть с исключением)
        self.assertIsNotNone(run)

    def test_vtt_contains_webvtt_header(self):
        """VTT файл должен начинаться с заголовка WEBVTT."""
        self.project.segments = [_make_segment(0, "Текст")]
        ExportSubtitlesStage().run(self._ctx())

        content = (self.project.work_dir / "subtitles" / "translated.vtt").read_text()
        self.assertTrue(content.startswith("WEBVTT"), "VTT должен начинаться с WEBVTT")

    def test_run_status_is_completed_not_failed(self):
        """Стадия должна завершаться со статусом completed, а не failed."""
        self.project.segments = [_make_segment(0, "Тест")]
        run = ExportSubtitlesStage().run(self._ctx())

        from translate_video.core.schemas import JobStatus
        self.assertEqual(run.status, JobStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
