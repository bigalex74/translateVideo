"""API-тесты для новых endpoints Round 3 (v1.44-1.49).

Покрывает: export subtitles (ASS, SBV, ZIP), import subtitles, quality-report,
activity, stage-runs, script export (TXT, TSV), batch create.
"""

import io
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient

from translate_video.api.main import app
from translate_video.api.routes.projects import get_store
from translate_video.core.schemas import Segment, SegmentStatus
from translate_video.core.store import ProjectStore


def _make_segment(i: int, translated: str = "") -> Segment:
    return Segment(
        id=f"seg_{i}",
        start=float(i),
        end=float(i + 1),
        source_text=f"Source {i}",
        translated_text=translated or f"Перевод {i}",
        status=SegmentStatus.TRANSLATED,
    )


class APISubtitleFormatsTest(TestCase):
    """Тесты экспорта субтитров: ASS, SBV."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_root = Path(self.temp_dir.name) / "runs"
        self.store = ProjectStore(self.work_root)
        app.dependency_overrides[get_store] = lambda: self.store
        self.client = TestClient(app)

        # Создаём тестовый проект с сегментами
        self.project = self.store.create_project("dummy.mp4", project_id="subs_test")
        segs = [_make_segment(i) for i in range(3)]
        self.store.save_segments(self.project, segs, translated=True)

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()

    def test_export_srt(self):
        """SRT экспорт возвращает text/plain."""
        resp = self.client.get("/api/v1/projects/subs_test/subtitles?format=srt")
        self.assertEqual(resp.status_code, 200)
        content = resp.text
        self.assertIn("-->", content)
        self.assertIn("Перевод 0", content)

    def test_export_vtt(self):
        """VTT экспорт возвращает WEBVTT заголовок."""
        resp = self.client.get("/api/v1/projects/subs_test/subtitles?format=vtt")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("WEBVTT", resp.text)

    def test_export_ass(self):
        """ASS экспорт содержит [Script Info]."""
        resp = self.client.get("/api/v1/projects/subs_test/subtitles?format=ass")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("[Script Info]", resp.text)
        self.assertIn("Dialogue:", resp.text)

    def test_export_sbv(self):
        """SBV экспорт содержит таймкоды."""
        resp = self.client.get("/api/v1/projects/subs_test/subtitles?format=sbv")
        self.assertEqual(resp.status_code, 200)
        # SBV формат: start,end на первой строке блока
        content = resp.text
        self.assertIn("Перевод 0", content)

    def test_export_unknown_format_422(self):
        """Неизвестный формат → 422 (Unprocessable Entity)."""
        resp = self.client.get("/api/v1/projects/subs_test/subtitles?format=ppt")
        self.assertEqual(resp.status_code, 422)

    def test_export_subtitles_not_found(self):
        """Проект не существует → 404."""
        resp = self.client.get("/api/v1/projects/nope_nope/subtitles?format=srt")
        self.assertEqual(resp.status_code, 404)


class APIBatchSubtitlesZipTest(TestCase):
    """Тест batch export всех субтитров в ZIP (Z1.12)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")
        app.dependency_overrides[get_store] = lambda: self.store
        self.client = TestClient(app)

        self.project = self.store.create_project("dummy.mp4", project_id="zip_test")
        segs = [_make_segment(i) for i in range(2)]
        self.store.save_segments(self.project, segs, translated=True)

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()

    def test_zip_returns_zip_content(self):
        """Endpoint возвращает ZIP файл."""
        resp = self.client.get("/api/v1/projects/zip_test/export/subtitles-all")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/zip")

    def test_zip_contains_all_four_formats(self):
        """ZIP содержит SRT, VTT, ASS, SBV."""
        resp = self.client.get("/api/v1/projects/zip_test/export/subtitles-all")
        buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
        self.assertTrue(any(n.endswith(".srt") for n in names))
        self.assertTrue(any(n.endswith(".vtt") for n in names))
        self.assertTrue(any(n.endswith(".ass") for n in names))
        self.assertTrue(any(n.endswith(".sbv") for n in names))

    def test_zip_no_segments_returns_404(self):
        """Проект без сегментов → 404."""
        self.store.create_project("dummy.mp4", project_id="empty_zip_test")
        resp = self.client.get("/api/v1/projects/empty_zip_test/export/subtitles-all")
        self.assertEqual(resp.status_code, 404)

    def test_zip_not_found(self):
        """Несуществующий проект → 404."""
        resp = self.client.get("/api/v1/projects/nope/export/subtitles-all")
        self.assertEqual(resp.status_code, 404)


class APIImportSubtitlesTest(TestCase):
    """Тесты импорта SRT субтитров как переводов (NC6-01)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")
        app.dependency_overrides[get_store] = lambda: self.store
        self.client = TestClient(app)

        self.project = self.store.create_project("dummy.mp4", project_id="import_test")
        segs = [_make_segment(i) for i in range(3)]
        self.store.save_segments(self.project, segs, translated=True)

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()

    def test_import_srt_success(self):
        """Валидный SRT файл → 200 с количеством совпадений."""
        srt = "1\n00:00:00,000 --> 00:00:01,000\nПеревод из SRT\n\n"
        files = {"file": ("subs.srt", srt.encode(), "text/plain")}
        resp = self.client.post("/api/v1/projects/import_test/import-subtitles", files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("subtitle_blocks_parsed", data)
        self.assertEqual(data["subtitle_blocks_parsed"], 1)

    def test_import_empty_srt_returns_422(self):
        """Пустой файл → 422 (нет блоков субтитров)."""
        files = {"file": ("empty.srt", b"", "text/plain")}
        resp = self.client.post("/api/v1/projects/import_test/import-subtitles", files=files)
        self.assertEqual(resp.status_code, 422)

    def test_import_srt_not_found(self):
        """Несуществующий проект → 404."""
        srt = "1\n00:00:00,000 --> 00:00:01,000\nТекст\n\n"
        files = {"file": ("s.srt", srt.encode(), "text/plain")}
        resp = self.client.post("/api/v1/projects/nope/import-subtitles", files=files)
        self.assertEqual(resp.status_code, 404)

    def test_import_vtt_success(self):
        """VTT файл → 200."""
        vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nТекст VTT\n\n"
        files = {"file": ("subs.vtt", vtt.encode(), "text/plain")}
        resp = self.client.post("/api/v1/projects/import_test/import-subtitles", files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["subtitle_blocks_parsed"], 1)


class APIQualityReportTest(TestCase):
    """Тесты /quality-report endpoint (Z3.10, Z3.11)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")
        app.dependency_overrides[get_store] = lambda: self.store
        self.client = TestClient(app)

        self.project = self.store.create_project("dummy.mp4", project_id="qa_test")
        segs = [_make_segment(i) for i in range(5)]
        self.store.save_segments(self.project, segs, translated=True)

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()

    def test_quality_report_success(self):
        """Endpoint возвращает оценку и рекомендации."""
        resp = self.client.get("/api/v1/projects/qa_test/quality-report")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("grade", data)
        self.assertIn(data["grade"], ["A", "B", "C", "D"])
        self.assertIn("grade_label", data)
        self.assertIn("segments_total", data)
        self.assertIn("recommendations", data)

    def test_quality_report_not_found(self):
        """Несуществующий проект → 404."""
        resp = self.client.get("/api/v1/projects/nope/quality-report")
        self.assertEqual(resp.status_code, 404)

    def test_quality_report_no_segments_returns_grade_a(self):
        """Проект без сегментов → 200 с оценкой A (нет проблем)."""
        self.store.create_project("dummy.mp4", project_id="empty_qa_test")
        resp = self.client.get("/api/v1/projects/empty_qa_test/quality-report")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Без сегментов — нет проблем, оценка A
        self.assertEqual(data["grade"], "A")
        self.assertEqual(data["segments_total"], 0)


class APIActivityTest(TestCase):
    """Тесты /activity endpoint (Z2.3)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")
        app.dependency_overrides[get_store] = lambda: self.store
        self.client = TestClient(app)
        self.project = self.store.create_project("dummy.mp4", project_id="act_test")

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()

    def test_activity_returns_list(self):
        """Endpoint возвращает список событий."""
        resp = self.client.get("/api/v1/projects/act_test/activity")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("events", data)
        self.assertIsInstance(data["events"], list)

    def test_activity_not_found(self):
        """Несуществующий проект → 404."""
        resp = self.client.get("/api/v1/projects/nope/activity")
        self.assertEqual(resp.status_code, 404)


class APIStageRunsTest(TestCase):
    """Тесты /stage-runs endpoint (Z5.8)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")
        app.dependency_overrides[get_store] = lambda: self.store
        self.client = TestClient(app)
        self.project = self.store.create_project("dummy.mp4", project_id="stages_test")

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()

    def test_stage_runs_returns_list(self):
        """Endpoint возвращает список запусков этапов."""
        resp = self.client.get("/api/v1/projects/stages_test/stage-runs")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("stage_runs", data)
        self.assertIsInstance(data["stage_runs"], list)

    def test_stage_runs_not_found(self):
        """Несуществующий проект → 404."""
        resp = self.client.get("/api/v1/projects/nope/stage-runs")
        self.assertEqual(resp.status_code, 404)


class APIScriptExportTest(TestCase):
    """Тесты экспорта финального скрипта (Z3.13, Z3.14)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")
        app.dependency_overrides[get_store] = lambda: self.store
        self.client = TestClient(app)

        self.project = self.store.create_project("dummy.mp4", project_id="script_test")
        segs = [_make_segment(i) for i in range(3)]
        self.store.save_segments(self.project, segs, translated=True)

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()

    def test_txt_export(self):
        """TXT экспорт скрипта работает."""
        resp = self.client.get("/api/v1/projects/script_test/export/script?format=txt")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ПЕРЕВОД:", resp.text)
        self.assertIn("ПЕР:", resp.text)

    def test_tsv_export(self):
        """TSV экспорт скрипта содержит заголовок и данные."""
        resp = self.client.get("/api/v1/projects/script_test/export/script?format=tsv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("start\tend\tsource\ttranslated", resp.text)

    def test_txt_without_timecodes(self):
        """TXT без таймкодов не содержит стрелки →."""
        resp = self.client.get(
            "/api/v1/projects/script_test/export/script?format=txt&include_timecodes=false"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("→", resp.text)

    def test_txt_with_source(self):
        """TXT с include_source=true содержит ОР:."""
        resp = self.client.get(
            "/api/v1/projects/script_test/export/script?format=txt&include_source=true"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ОР:", resp.text)

    def test_script_not_found(self):
        """Несуществующий проект → 404."""
        resp = self.client.get("/api/v1/projects/nope/export/script")
        self.assertEqual(resp.status_code, 404)

    def test_script_no_segments_404(self):
        """Проект без сегментов → 404."""
        self.store.create_project("dummy.mp4", project_id="empty_script_test")
        resp = self.client.get("/api/v1/projects/empty_script_test/export/script")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    import unittest
    unittest.main()
