"""Тесты маршрута стриминга видеофайлов."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient

from translate_video.api.main import app


class VideoStreamTest(TestCase):
    """Проверяет корректность MIME-типов и Range-стриминга."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # Создаём тестовый «видеофайл»
        self.project_dir = Path(self.temp.name) / "test_proj"
        self.project_dir.mkdir()
        self.video_file = self.project_dir / "input.mp4"
        # Записываем ~8 KiB «содержимого»
        self.video_file.write_bytes(b"FAKE_MP4_DATA" * 640)

        import os
        os.environ["WORK_ROOT"] = self.temp.name
        # Перезагружаем роутер чтобы WORK_ROOT обновился
        from translate_video.api.routes import video as vm
        vm._WORK_ROOT = Path(self.temp.name).resolve()   # .resolve() — обязательно
        self.client = TestClient(app)

    def tearDown(self):
        self.temp.cleanup()

    def test_full_response_has_correct_mime(self):
        """Полный запрос должен вернуть Content-Type: video/mp4."""
        r = self.client.get("/api/v1/video/test_proj/input.mp4")
        self.assertEqual(r.status_code, 200)
        self.assertIn("video/mp4", r.headers["content-type"])

    def test_range_request_returns_206(self):
        """Range-запрос должен вернуть 206 Partial Content."""
        r = self.client.get(
            "/api/v1/video/test_proj/input.mp4",
            headers={"Range": "bytes=0-1023"},
        )
        self.assertEqual(r.status_code, 206)
        self.assertIn("content-range", r.headers)
        self.assertEqual(len(r.content), 1024)

    def test_missing_file_returns_404(self):
        """Несуществующий файл → 404."""
        r = self.client.get("/api/v1/video/test_proj/missing.mp4")
        self.assertEqual(r.status_code, 404)

    def test_path_traversal_blocked(self):
        """Попытка path traversal → 400 или 404."""
        r = self.client.get("/api/v1/video/test_proj/../../../etc/passwd")
        self.assertIn(r.status_code, [400, 404, 422])

    def test_disallowed_extension_returns_400(self):
        """Недопустимое расширение → 400."""
        bad_file = self.project_dir / "script.py"
        bad_file.write_bytes(b"print('hi')")
        r = self.client.get("/api/v1/video/test_proj/script.py")
        self.assertEqual(r.status_code, 400)

    def test_range_out_of_bounds_returns_416(self):
        """Range за пределами файла → 416."""
        size = self.video_file.stat().st_size
        r = self.client.get(
            "/api/v1/video/test_proj/input.mp4",
            headers={"Range": f"bytes={size}-{size + 999}"},
        )
        self.assertEqual(r.status_code, 416)

    # ─── TVIDEO-025: видео в подпапке ────────────────────────────────────────

    def test_video_in_subfolder_streams_correctly(self):
        """TVIDEO-025: output/translated.mp4 должен стримиться корректно.

        Регрессия: _resolve_video брал только Path(filename).name и отрезал
        подпапку, из-за чего output/translated.mp4 не находился → MIME ошибка в плеере.
        """
        output_dir = self.project_dir / "output"
        output_dir.mkdir()
        translated = output_dir / "translated.mp4"
        translated.write_bytes(b"TRANSLATED_MP4" * 640)

        r = self.client.get("/api/v1/video/test_proj/output/translated.mp4")
        self.assertEqual(r.status_code, 200)
        self.assertIn("video/mp4", r.headers["content-type"])

    def test_subfolder_range_request_206(self):
        """TVIDEO-025: Range-запрос к файлу в подпапке возвращает 206."""
        output_dir = self.project_dir / "output"
        output_dir.mkdir()
        translated = output_dir / "translated.mp4"
        translated.write_bytes(b"TRANSLATED_MP4" * 640)

        r = self.client.get(
            "/api/v1/video/test_proj/output/translated.mp4",
            headers={"Range": "bytes=0-511"},
        )
        self.assertEqual(r.status_code, 206)
        self.assertEqual(len(r.content), 512)

    def test_subfolder_traversal_blocked(self):
        """TVIDEO-025: path traversal через подпапку → 400."""
        r = self.client.get("/api/v1/video/test_proj/output/../../etc/passwd")
        self.assertIn(r.status_code, [400, 404, 422])
