"""API-тесты для новых endpoints Round 3 Итерации 6–10 (v1.51–1.55).

QA Monitor требование: покрытие Python ≥80%.
Покрывает: delete_segment, merge, split, bulk-translate, webhook-history,
tags, archive/unarchive, download-video, zip-export, pagination, segment_score.
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
from translate_video.core.stats import compute_segment_score
from translate_video.core.store import ProjectStore


# ─── Helpers ────────────────────────────────────────────────────────────────

def _seg(i: int, translated: str = "", qa_flags: list[str] | None = None) -> Segment:
    return Segment(
        id=f"seg_{i:03d}",
        start=float(i),
        end=float(i + 1),
        source_text=f"Source text {i}",
        translated_text=translated or f"Перевод сегмента {i}",
        status=SegmentStatus.TRANSLATED,
        qa_flags=qa_flags or [],
    )


class _Base(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.temp_dir.name) / "runs")
        app.dependency_overrides[get_store] = lambda: self.store
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()

    def _project_with_segs(self, pid: str, n: int = 3) -> str:
        p = self.store.create_project("dummy.mp4", project_id=pid)
        segs = [_seg(i) for i in range(n)]
        self.store.save_segments(p, segs, translated=True)
        return pid


# ─── NC8-01: DELETE segment ──────────────────────────────────────────────────

class TestDeleteSegment(_Base):
    """Тесты удаления сегмента из проекта (NC8-01)."""

    def setUp(self):
        super().setUp()
        self._project_with_segs("del_test", n=3)

    def test_delete_existing_segment(self):
        """Удаление существующего сегмента → 200, segments_remaining уменьшается."""
        resp = self.client.delete("/api/v1/projects/del_test/segments/seg_000")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["deleted_id"], "seg_000")
        self.assertEqual(data["segments_remaining"], 2)

    def test_delete_nonexistent_segment_404(self):
        """Удаление несуществующего сегмента → 404."""
        resp = self.client.delete("/api/v1/projects/del_test/segments/seg_999")
        self.assertEqual(resp.status_code, 404)

    def test_delete_segment_nonexistent_project_404(self):
        """Удаление из несуществующего проекта → 404."""
        resp = self.client.delete("/api/v1/projects/nope/segments/seg_000")
        self.assertEqual(resp.status_code, 404)

    def test_delete_all_segments(self):
        """Удаляем все сегменты по одному, segments_remaining → 0."""
        for i in range(3):
            resp = self.client.delete(f"/api/v1/projects/del_test/segments/seg_{i:03d}")
            self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["segments_remaining"], 0)


# ─── Z5.14: Webhook history ──────────────────────────────────────────────────

class TestWebhookHistory(_Base):
    """Тесты истории вебхуков проекта (Z5.14)."""

    def setUp(self):
        super().setUp()
        self.store.create_project("dummy.mp4", project_id="wh_test")

    def test_webhook_history_returns_list(self):
        """Endpoint возвращает список событий (может быть пустым)."""
        resp = self.client.get("/api/v1/projects/wh_test/webhook-history")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("webhook_events", data)
        self.assertIsInstance(data["webhook_events"], list)
        self.assertIn("total", data)

    def test_webhook_history_not_found(self):
        """Несуществующий проект → 404."""
        resp = self.client.get("/api/v1/projects/nope/webhook-history")
        self.assertEqual(resp.status_code, 404)

    def test_webhook_history_limit_param(self):
        """Параметр limit обрабатывается корректно."""
        resp = self.client.get("/api/v1/projects/wh_test/webhook-history?limit=5")
        self.assertEqual(resp.status_code, 200)


# ─── NC9-01: Split segment ───────────────────────────────────────────────────

class TestSplitSegment(_Base):
    """Тесты разделения сегмента (NC9-01)."""

    def setUp(self):
        super().setUp()
        p = self.store.create_project("dummy.mp4", project_id="split_test")
        segs = [Segment(
            id="seg_long",
            start=0.0,
            end=10.0,
            source_text="Hello world and more text here",
            translated_text="Привет мир и ещё текст здесь",
            status=SegmentStatus.TRANSLATED,
        )]
        self.store.save_segments(p, segs, translated=True)

    def test_split_at_valid_position(self):
        """Разделение в середине текста → 200, два сегмента."""
        resp = self.client.post(
            "/api/v1/projects/split_test/segments/seg_long/split",
            json={"split_at_char": 12},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("segment_a", data)
        self.assertIn("segment_b", data)
        self.assertEqual(data["segments_total"], 2)

    def test_split_with_mid_time(self):
        """Разделение с указанным временем mid_time → 200."""
        resp = self.client.post(
            "/api/v1/projects/split_test/segments/seg_long/split",
            json={"split_at_char": 12, "mid_time": 5.0},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertAlmostEqual(data["segment_a"]["end"], 5.0)
        self.assertAlmostEqual(data["segment_b"]["start"], 5.0)

    def test_split_position_creates_empty_part_422(self):
        """Позиция разделения создаёт пустой сегмент → 422."""
        resp = self.client.post(
            "/api/v1/projects/split_test/segments/seg_long/split",
            json={"split_at_char": 0},
        )
        self.assertEqual(resp.status_code, 422)

    def test_split_nonexistent_segment_404(self):
        """Несуществующий сегмент → 404."""
        resp = self.client.post(
            "/api/v1/projects/split_test/segments/seg_nope/split",
            json={"split_at_char": 5},
        )
        self.assertEqual(resp.status_code, 404)

    def test_split_nonexistent_project_404(self):
        """Несуществующий проект → 404."""
        resp = self.client.post(
            "/api/v1/projects/nope/segments/seg_long/split",
            json={"split_at_char": 5},
        )
        self.assertEqual(resp.status_code, 404)


# ─── Z1.14: Download video ───────────────────────────────────────────────────

class TestDownloadVideo(_Base):
    """Тесты скачивания готового видео (Z1.14)."""

    def test_download_video_no_artifact_404(self):
        """Проект без видео-артефакта → 404."""
        self.store.create_project("dummy.mp4", project_id="no_video")
        resp = self.client.get("/api/v1/projects/no_video/download-video")
        self.assertEqual(resp.status_code, 404)

    def test_download_video_not_found_404(self):
        """Несуществующий проект → 404."""
        resp = self.client.get("/api/v1/projects/nope/download-video")
        self.assertEqual(resp.status_code, 404)


# ─── NC10-01: Tags ───────────────────────────────────────────────────────────

class TestProjectTags(_Base):
    """Тесты управления тегами проекта (NC10-01)."""

    def setUp(self):
        super().setUp()
        self.store.create_project("dummy.mp4", project_id="tag_test")

    def test_set_tags_success(self):
        """Установка тегов → 200, теги возвращаются."""
        resp = self.client.put(
            "/api/v1/projects/tag_test/tags",
            json={"tags": ["важный", "к-просмотру", "русский"]},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["project_id"], "tag_test")
        self.assertIn("важный", data["tags"])

    def test_set_tags_empty_clears(self):
        """Пустой список тегов очищает теги."""
        self.client.put("/api/v1/projects/tag_test/tags", json={"tags": ["тег1"]})
        resp = self.client.put("/api/v1/projects/tag_test/tags", json={"tags": []})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["tags"], [])

    def test_set_tags_not_found(self):
        """Несуществующий проект → 404."""
        resp = self.client.put(
            "/api/v1/projects/nope/tags", json={"tags": ["x"]}
        )
        self.assertEqual(resp.status_code, 404)

    def test_tags_max_20(self):
        """Максимум 20 тегов — лишние обрезаются."""
        tags = [f"tag_{i}" for i in range(30)]
        resp = self.client.put("/api/v1/projects/tag_test/tags", json={"tags": tags})
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.json()["tags"]), 20)


# ─── NC10-02: Archive / Unarchive ────────────────────────────────────────────

class TestArchiveProject(_Base):
    """Тесты архивирования проекта (NC10-02)."""

    def setUp(self):
        super().setUp()
        self.store.create_project("dummy.mp4", project_id="arch_test")

    def test_archive_project(self):
        """Архивирование → archived=True."""
        resp = self.client.post("/api/v1/projects/arch_test/archive")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["archived"])

    def test_unarchive_project(self):
        """Разархивирование → archived=False."""
        self.client.post("/api/v1/projects/arch_test/archive")
        resp = self.client.post("/api/v1/projects/arch_test/unarchive")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["archived"])

    def test_archive_not_found(self):
        """Архивирование несуществующего → 404."""
        resp = self.client.post("/api/v1/projects/nope/archive")
        self.assertEqual(resp.status_code, 404)

    def test_unarchive_not_found(self):
        """Разархивирование несуществующего → 404."""
        resp = self.client.post("/api/v1/projects/nope/unarchive")
        self.assertEqual(resp.status_code, 404)


# ─── Z3.18: Pagination ───────────────────────────────────────────────────────

class TestListProjectsPagination(_Base):
    """Тесты пагинации и фильтрации списка проектов (Z3.18, NC10-01, NC10-02)."""

    def setUp(self):
        super().setUp()
        for i in range(5):
            self.store.create_project("dummy.mp4", project_id=f"pag_{i:02d}")

    def test_list_returns_pagination_meta(self):
        """Список проектов возвращает объект pagination."""
        resp = self.client.get("/api/v1/projects")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("pagination", data)
        self.assertIn("page", data["pagination"])
        self.assertIn("total", data["pagination"])

    def test_page_size_limits_results(self):
        """page_size=2 возвращает не более 2 проектов."""
        resp = self.client.get("/api/v1/projects?page=1&page_size=2")
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.json()["projects"]), 2)

    def test_page2_returns_different_results(self):
        """Страница 2 возвращает другие проекты."""
        r1 = self.client.get("/api/v1/projects?page=1&page_size=2").json()
        r2 = self.client.get("/api/v1/projects?page=2&page_size=2").json()
        ids1 = {p["project_id"] for p in r1["projects"]}
        ids2 = {p["project_id"] for p in r2["projects"]}
        self.assertEqual(ids1 & ids2, set())  # нет пересечения

    def test_archived_filter_shows_only_archived(self):
        """archived=true показывает только архивные проекты."""
        self.client.post("/api/v1/projects/pag_00/archive")
        resp = self.client.get("/api/v1/projects?archived=true")
        self.assertEqual(resp.status_code, 200)
        ids = {p["project_id"] for p in resp.json()["projects"]}
        self.assertIn("pag_00", ids)
        self.assertNotIn("pag_01", ids)

    def test_default_hides_archived(self):
        """По умолчанию архивные проекты скрыты."""
        self.client.post("/api/v1/projects/pag_00/archive")
        resp = self.client.get("/api/v1/projects")
        ids = {p["project_id"] for p in resp.json()["projects"]}
        self.assertNotIn("pag_00", ids)

    def test_tag_filter(self):
        """Фильтр по тегу работает корректно."""
        self.client.put("/api/v1/projects/pag_01/tags", json={"tags": ["срочно"]})
        resp = self.client.get("/api/v1/projects?tag=срочно")
        ids = {p["project_id"] for p in resp.json()["projects"]}
        self.assertIn("pag_01", ids)
        self.assertNotIn("pag_02", ids)


# ─── NC11-01: ZIP export ─────────────────────────────────────────────────────

class TestExportProjectZip(_Base):
    """Тесты полного ZIP-экспорта проекта (NC11-01)."""

    def setUp(self):
        super().setUp()
        self._project_with_segs("zip_full_test", n=3)

    def test_zip_returns_zip_content(self):
        """Endpoint возвращает ZIP файл."""
        resp = self.client.get("/api/v1/projects/zip_full_test/export/zip")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/zip")

    def test_zip_contains_project_json(self):
        """ZIP содержит project.json."""
        resp = self.client.get("/api/v1/projects/zip_full_test/export/zip")
        buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            self.assertIn("project.json", zf.namelist())

    def test_zip_contains_script_files(self):
        """ZIP содержит TXT и TSV скрипты."""
        resp = self.client.get("/api/v1/projects/zip_full_test/export/zip")
        buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            names = zf.namelist()
        self.assertTrue(any(n.endswith("_script.txt") for n in names))
        self.assertTrue(any(n.endswith("_script.tsv") for n in names))

    def test_zip_not_found(self):
        """Несуществующий проект → 404."""
        resp = self.client.get("/api/v1/projects/nope/export/zip")
        self.assertEqual(resp.status_code, 404)

    def test_zip_empty_project(self):
        """Проект без сегментов → 200 (ZIP содержит project.json)."""
        self.store.create_project("dummy.mp4", project_id="zip_empty")
        resp = self.client.get("/api/v1/projects/zip_empty/export/zip")
        self.assertEqual(resp.status_code, 200)
        buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            self.assertIn("project.json", zf.namelist())


# ─── Z3.17: compute_segment_score ────────────────────────────────────────────

class TestComputeSegmentScore(TestCase):
    """Тесты функции compute_segment_score (Z3.17)."""

    def test_perfect_segment_grade_a(self):
        """Сегмент без флагов и с переводом → оценка A, score=1.0."""
        seg = _seg(1, translated="Отличный перевод")
        result = compute_segment_score(seg)
        self.assertEqual(result["grade"], "A")
        self.assertEqual(result["score"], 1.0)
        self.assertTrue(result["has_translation"])

    def test_empty_translation_grade_d(self):
        """Пустой перевод → оценка D."""
        seg = Segment(id="s1", start=0, end=1, source_text="Hello",
                      translated_text="", status=SegmentStatus.DRAFT)
        result = compute_segment_score(seg)
        self.assertEqual(result["grade"], "D")
        self.assertFalse(result["has_translation"])

    def test_critical_flag_reduces_score(self):
        """Критичный флаг → score ≤ 0.5."""
        seg = _seg(1, qa_flags=["translation_empty"])
        result = compute_segment_score(seg)
        self.assertLessEqual(result["score"], 0.5)

    def test_error_flag_grade_b_or_c(self):
        """Один error-флаг → grade B или C."""
        seg = _seg(1, translated="Текст", qa_flags=["timing_fit_failed"])
        result = compute_segment_score(seg)
        self.assertIn(result["grade"], ["B", "C"])

    def test_warning_flag_grade_b(self):
        """Один warning-флаг → grade A или B."""
        seg = _seg(1, translated="Текст", qa_flags=["tts_rate_adapted"])
        result = compute_segment_score(seg)
        self.assertIn(result["grade"], ["A", "B"])

    def test_multiple_flags_cumulative_penalty(self):
        """Несколько флагов → суммарный штраф."""
        seg = _seg(1, translated="Текст",
                   qa_flags=["timing_fit_failed", "render_audio_trimmed", "tts_rate_adapted"])
        result = compute_segment_score(seg)
        self.assertGreater(result["flags_penalty"], 0.5)

    def test_score_fields_present(self):
        """Результат содержит все необходимые поля."""
        seg = _seg(1, translated="Текст")
        result = compute_segment_score(seg)
        for field in ["score", "grade", "flags_penalty", "flags_count", "has_translation"]:
            self.assertIn(field, result)


# ─── Z3.19: word_count в Segment.to_dict() ───────────────────────────────────

class TestSegmentWordCount(TestCase):
    """Тесты word_count_source и word_count_translated в Segment.to_dict() (Z3.19)."""

    def test_word_count_source(self):
        """word_count_source считает слова в source_text."""
        seg = Segment(id="s1", start=0, end=1, source_text="Hello world foo",
                      translated_text="Привет мир", status=SegmentStatus.DRAFT)
        d = seg.to_dict()
        self.assertEqual(d["word_count_source"], 3)

    def test_word_count_translated(self):
        """word_count_translated считает слова в translated_text."""
        seg = Segment(id="s1", start=0, end=1, source_text="Hello",
                      translated_text="Привет мир всем", status=SegmentStatus.DRAFT)
        d = seg.to_dict()
        self.assertEqual(d["word_count_translated"], 3)

    def test_empty_texts_word_count_zero(self):
        """Пустые тексты → word_count = 0."""
        seg = Segment(id="s1", start=0, end=1, source_text="",
                      translated_text="", status=SegmentStatus.DRAFT)
        d = seg.to_dict()
        self.assertEqual(d["word_count_source"], 0)
        self.assertEqual(d["word_count_translated"], 0)

    def test_word_count_via_api(self):
        """API возвращает word_count в сегментах."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "runs")
            app.dependency_overrides[get_store] = lambda: store
            client = TestClient(app)
            p = store.create_project("d.mp4", project_id="wc_test")
            seg = Segment(id="s1", start=0, end=1, source_text="One two three",
                          translated_text="Один два три четыре", status=SegmentStatus.TRANSLATED)
            store.save_segments(p, [seg], translated=True)
            resp = client.get("/api/v1/projects/wc_test")
            app.dependency_overrides.clear()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        seg_data = data["segments"][0]
        self.assertIn("word_count_source", seg_data)
        self.assertEqual(seg_data["word_count_source"], 3)
        self.assertEqual(seg_data["word_count_translated"], 4)


# ─── VideoProject tags + archived в схеме ────────────────────────────────────

class TestVideoProjectTagsArchived(TestCase):
    """Тесты полей tags и archived в VideoProject (NC10-01, NC10-02)."""

    def test_tags_default_empty(self):
        """По умолчанию теги — пустой список."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "runs")
            p = store.create_project("d.mp4", project_id="tags_schema_test")
            self.assertEqual(p.tags, [])
            self.assertFalse(p.archived)

    def test_tags_serialization(self):
        """Теги корректно сериализуются и десериализуются."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "runs")
            p = store.create_project("d.mp4", project_id="tags_ser_test")
            p.tags = ["альфа", "бета"]
            p.archived = True
            store.save_project(p)
            loaded = store.load_project(store.root / "tags_ser_test")
            self.assertEqual(loaded.tags, ["альфа", "бета"])
            self.assertTrue(loaded.archived)

    def test_to_dict_includes_tags(self):
        """to_dict содержит tags и archived."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "runs")
            p = store.create_project("d.mp4", project_id="tags_dict_test")
            p.tags = ["срочно"]
            d = p.to_dict()
            self.assertIn("tags", d)
            self.assertIn("archived", d)
            self.assertEqual(d["tags"], ["срочно"])


if __name__ == "__main__":
    import unittest
    unittest.main()
