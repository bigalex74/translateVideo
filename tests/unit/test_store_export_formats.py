"""Unit-тесты store.export_subtitles для форматов ASS и SBV (NC5-01, Z3.4).

Проверяет регистрацию артефактов и запись файлов для новых форматов.
"""

import tempfile
import unittest
from pathlib import Path

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import ArtifactKind, Segment, SegmentStatus
from translate_video.core.store import ProjectStore


def _make_segment(i: int) -> Segment:
    return Segment(
        id=f"seg_{i}",
        start=float(i),
        end=float(i + 1),
        source_text=f"Source {i}",
        translated_text=f"Перевод {i}",
        status=SegmentStatus.TRANSLATED,
    )


class StoreExportASSTest(unittest.TestCase):
    """Тесты экспорта субтитров в ASS-формате через ProjectStore."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(root=self._tmpdir.name)
        self.project = self.store.create_project(
            input_video="/dev/null",
            config=PipelineConfig(),
        )
        self.project.segments = [_make_segment(i) for i in range(3)]
        self.store.save_project(self.project)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_ass_file_created(self):
        """ASS файл создаётся на диске."""
        output = self.store.export_subtitles(self.project, fmt="ass")
        self.assertTrue(output.exists())
        self.assertEqual(output.suffix, ".ass")

    def test_ass_content_has_header(self):
        """ASS файл содержит обязательные секции заголовка."""
        output = self.store.export_subtitles(self.project, fmt="ass")
        content = output.read_text(encoding="utf-8")
        self.assertIn("[Script Info]", content)
        self.assertIn("[Events]", content)

    def test_ass_content_has_dialogue(self):
        """ASS файл содержит Dialogue строки для сегментов."""
        output = self.store.export_subtitles(self.project, fmt="ass")
        content = output.read_text(encoding="utf-8")
        self.assertEqual(content.count("Dialogue:"), 3)

    def test_ass_artifact_registered(self):
        """Артефакт регистрируется в проекте после экспорта."""
        self.store.export_subtitles(self.project, fmt="ass")
        art = self.store.get_artifact(self.project, ArtifactKind.SUBTITLES)
        self.assertIsNotNone(art)
        self.assertEqual(art.metadata.get("format"), "ass")

    def test_ass_invalid_format_raises(self):
        """Неизвестный формат вызывает ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.store.export_subtitles(self.project, fmt="ppt")
        self.assertIn("ppt", str(ctx.exception))


class StoreExportSBVTest(unittest.TestCase):
    """Тесты экспорта субтитров в YouTube SBV формате через ProjectStore."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(root=self._tmpdir.name)
        self.project = self.store.create_project(
            input_video="/dev/null",
            config=PipelineConfig(),
        )
        self.project.segments = [_make_segment(i) for i in range(2)]
        self.store.save_project(self.project)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_sbv_file_created(self):
        """SBV файл создаётся на диске."""
        output = self.store.export_subtitles(self.project, fmt="sbv")
        self.assertTrue(output.exists())
        self.assertEqual(output.suffix, ".sbv")

    def test_sbv_content_valid(self):
        """SBV файл содержит таймкоды и тексты."""
        output = self.store.export_subtitles(self.project, fmt="sbv")
        content = output.read_text(encoding="utf-8")
        self.assertIn("Перевод 0", content)
        self.assertIn("Перевод 1", content)

    def test_sbv_artifact_metadata(self):
        """Метаданные артефакта SBV корректны."""
        self.store.export_subtitles(self.project, fmt="sbv")
        art = self.store.get_artifact(self.project, ArtifactKind.SUBTITLES)
        self.assertEqual(art.metadata.get("format"), "sbv")

    def test_sbv_and_srt_coexist(self):
        """Экспорт разных форматов не перезаписывает друг друга на диске."""
        srt_path = self.store.export_subtitles(self.project, fmt="srt")
        sbv_path = self.store.export_subtitles(self.project, fmt="sbv")
        self.assertNotEqual(srt_path, sbv_path)
        self.assertTrue(srt_path.exists())
        self.assertTrue(sbv_path.exists())


class StoreAllFormatsTest(unittest.TestCase):
    """Тесты что все 4 формата экспортируются без ошибок."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(root=self._tmpdir.name)
        self.project = self.store.create_project(
            input_video="/dev/null",
            config=PipelineConfig(),
        )
        self.project.segments = [_make_segment(0)]
        self.store.save_project(self.project)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_all_four_formats_succeed(self):
        """SRT, VTT, ASS, SBV — все экспортируются без исключений."""
        for fmt in ("srt", "vtt", "ass", "sbv"):
            with self.subTest(fmt=fmt):
                path = self.store.export_subtitles(self.project, fmt=fmt)
                self.assertTrue(path.exists(), f"Файл {fmt} не создан")
                self.assertGreater(path.stat().st_size, 0, f"Файл {fmt} пустой")


if __name__ == "__main__":
    unittest.main()
