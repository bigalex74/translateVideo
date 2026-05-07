import tempfile
import socket
import zipfile
import io
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from translate_video.api.main import app
from translate_video.core.schemas import ArtifactKind, Segment, SegmentStatus, Stage
from translate_video.core.store import ProjectStore
from translate_video.api.routes.projects import get_store

class APIProjectsTest(TestCase):
    """Тесты API маршрутов управления проектами."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_root = Path(self.temp_dir.name) / "runs"
        self.store = ProjectStore(self.work_root)
        
        app.dependency_overrides[get_store] = lambda: self.store
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()
        app.dependency_overrides.clear()

    def test_get_store(self):
        """Проверка дефолтной зависимости get_store."""
        store = get_store()
        self.assertIsNotNone(store)

    def test_create_project(self):
        """Проверка создания проекта через API."""
        response = self.client.post("/api/v1/projects", json={
            "input_video": "dummy.mp4",
            "project_id": "api_test",
            "config": {"source_language": "en"}
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["project_id"], "api_test")
        self.assertEqual(data["status"], "created")
        self.assertEqual(data["config"]["source_language"], "en")
        self.assertEqual(data["segments"], [])

    def test_create_project_duplicate_returns_409_and_keeps_original(self):
        """Повторный project_id через API не должен перетирать существующий проект."""

        self.store.create_project("first.mp4", project_id="dup_api")
        response = self.client.post("/api/v1/projects", json={
            "input_video": "second.mp4",
            "project_id": "dup_api",
        })

        self.assertEqual(response.status_code, 409)
        restored = self.store.load_project(self.work_root / "dup_api")
        self.assertEqual(restored.input_video, Path("first.mp4"))

    def test_create_project_rejects_existing_local_file_outside_work_root(self):
        """JSON API не должен копировать произвольные локальные файлы сервера."""

        outside = Path(self.temp_dir.name) / "secret.mp4"
        outside.write_bytes(b"secret")

        response = self.client.post("/api/v1/projects", json={
            "input_video": str(outside),
            "project_id": "local_secret",
        })

        self.assertEqual(response.status_code, 403)

    def test_create_project_rejects_private_url_download(self):
        """URL-загрузка не должна ходить на loopback/private адреса."""

        response = self.client.post("/api/v1/projects", json={
            "input_video": "http://127.0.0.1/video.mp4",
            "project_id": "ssrf_url",
        })

        self.assertEqual(response.status_code, 400)

    def test_create_project_rejects_hostname_resolving_to_private_ip(self):
        """DNS-имя для URL-загрузки проверяется до запуска yt-dlp."""

        private_dns = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
        with patch("translate_video.api.routes.projects.socket.getaddrinfo", return_value=private_dns):
            response = self.client.post("/api/v1/projects", json={
                "input_video": "https://video.example.test/file.mp4",
                "project_id": "ssrf_dns_url",
            })

        self.assertEqual(response.status_code, 400)

    def test_list_projects(self):
        """Список проектов должен возвращать краткие карточки."""

        self.store.create_project("first.mp4", project_id="first")
        self.store.create_project("second.mp4", project_id="second")

        response = self.client.get("/api/v1/projects")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([project["project_id"] for project in data["projects"]], ["second", "first"])
        self.assertEqual(data["projects"][0]["segments"], 0)

    @patch.object(ProjectStore, "create_project")
    def test_create_project_exception(self, mock_create):
        """Проверка 500 при неожиданной ошибке создания."""
        mock_create.side_effect = Exception("Test Error")
        response = self.client.post("/api/v1/projects", json={"input_video": "dummy.mp4"})
        self.assertEqual(response.status_code, 500)

    @patch.object(ProjectStore, "create_project")
    def test_upload_project_exception(self, mock_create):
        """Проверка 500 при неожиданной ошибке загрузки файла."""
        mock_create.side_effect = Exception("Upload Error")
        files = {"file": ("test.mp4", b"data", "video/mp4")}
        response = self.client.post("/api/v1/projects/upload", files=files)
        self.assertEqual(response.status_code, 500)

    def test_get_project_status(self):
        """Проверка получения статуса."""
        project = self.store.create_project("dummy.mp4", project_id="status_test")
        self.store.save_segments(
            project,
            [Segment(id="seg_1", start=0, end=1, source_text="Hello", translated_text="Привет")],
            translated=True,
        )
        response = self.client.get("/api/v1/projects/status_test")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["segments"][0]["translated_text"], "Привет")
        self.assertEqual(data["artifact_records"][0]["kind"], "translated_transcript")

    def test_runs_static_does_not_expose_project_json(self):
        """Рабочая папка runs не должна отдаваться как публичная статика."""

        self.store.create_project("dummy.mp4", project_id="static_secret")

        response = self.client.get("/runs/static_secret/project.json")

        self.assertFalse(
            response.status_code == 200 and response.headers.get("content-type", "").startswith("application/json"),
            "project.json не должен быть доступен через /runs",
        )

    def test_get_project_not_found(self):
        """Проверка 404 для несуществующего проекта."""
        response = self.client.get("/api/v1/projects/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_get_project_rejects_path_traversal_id(self):
        """Получение проекта не должно принимать небезопасный ID."""

        response = self.client.get("/api/v1/projects/%2E%2E")

        self.assertEqual(response.status_code, 400)

    def test_get_artifacts(self):
        """Проверка получения артефактов."""
        project = self.store.create_project("dummy.mp4", project_id="artifacts_test")
        self.store.save_segments(project, [Segment(start=0, end=1, source_text="Hello")])
        response = self.client.get("/api/v1/projects/artifacts_test/artifacts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["artifacts"][0]["kind"], "source_transcript")

    def test_project_doctor_reports_actions(self):
        """Project Doctor должен вернуть безопасные действия для проекта."""
        project = self.store.create_project("dummy.mp4", project_id="doctor_route")
        self.store.save_segments(
            project,
            [Segment(start=0, end=1, source_text="Hello", translated_text="Привет")],
            translated=True,
        )

        response = self.client.get("/api/v1/projects/doctor_route/doctor")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["project_id"], "doctor_route")
        self.assertIn("actions", data)
        self.assertTrue(any(item["id"] == "tts" for item in data["actions"]))

    def test_project_snapshots_lists_metadata_snapshots(self):
        """Снимки проекта должны отображаться через API."""
        project = self.store.create_project("dummy.mp4", project_id="snapshots_route")
        self.store.create_snapshot(project, reason="test")

        response = self.client.get("/api/v1/projects/snapshots_route/snapshots")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["snapshots"]), 1)
        self.assertEqual(data["snapshots"][0]["reason"], "test")

    def test_rebuild_subtitles_from_current_segments(self):
        """Быстрая пересборка субтитров не должна запускать пайплайн."""
        project = self.store.create_project("dummy.mp4", project_id="subtitles_rebuild")
        self.store.save_segments(
            project,
            [Segment(start=0, end=1, source_text="Hello", translated_text="Привет")],
            translated=True,
        )

        response = self.client.post("/api/v1/projects/subtitles_rebuild/rebuild/subtitles")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["subtitles"], "subtitles/translated.srt")
        self.assertTrue((self.work_root / "subtitles_rebuild" / "subtitles" / "translated.srt").exists())

    def test_segment_action_reset_tts(self):
        """Bulk reset-tts должен очищать TTS metadata выбранного сегмента."""
        project = self.store.create_project("dummy.mp4", project_id="seg_reset_tts")
        tts_file = project.work_dir / "tts" / "seg_1.mp3"
        tts_file.parent.mkdir(parents=True, exist_ok=True)
        tts_file.write_bytes(b"mp3")
        seg = Segment(
            id="seg_1",
            start=0,
            end=1,
            source_text="Hello",
            translated_text="Привет",
            tts_path="tts/seg_1.mp3",
            tts_text="Привет",
            qa_flags=["tts_overflow_after_rate", "timing_fit_failed"],
        )
        self.store.save_segments(project, [seg], translated=True)

        response = self.client.post(
            "/api/v1/projects/seg_reset_tts/segments/actions/reset-tts",
            json={"segment_ids": ["seg_1"]},
        )

        self.assertEqual(response.status_code, 200)
        restored = self.store.load_project(self.work_root / "seg_reset_tts")
        self.assertIsNone(restored.segments[0].tts_path)
        self.assertEqual(restored.segments[0].tts_text, "")
        self.assertEqual(restored.segments[0].qa_flags, ["timing_fit_failed"])
        self.assertFalse(tts_file.exists())

    def test_segment_action_mark_reviewed(self):
        """Bulk mark-reviewed должен выставлять reviewed=True."""
        project = self.store.create_project("dummy.mp4", project_id="seg_reviewed")
        seg = Segment(
            id="seg_1",
            start=0,
            end=1,
            source_text="Hello",
            translated_text="Привет",
            qa_flags=["timing_fit_failed"],
        )
        self.store.save_segments(project, [seg], translated=True)

        response = self.client.post(
            "/api/v1/projects/seg_reviewed/segments/actions/mark-reviewed",
            json={"segment_ids": ["seg_1"]},
        )

        self.assertEqual(response.status_code, 200)
        restored = self.store.load_project(self.work_root / "seg_reviewed")
        self.assertTrue(restored.segments[0].reviewed)

    def test_segment_action_tts_uses_provider_and_merges_result(self):
        """Bulk tts должен синтезировать выбранный сегмент и сохранить результат."""

        class FakeProvider:
            def synthesize(self, project, segments):
                for segment in segments:
                    path = project.work_dir / "tts" / f"{segment.id}.mp3"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"mp3")
                    segment.tts_path = path.relative_to(project.work_dir).as_posix()
                    segment.tts_text = segment.translated_text
                return segments

        project = self.store.create_project("dummy.mp4", project_id="seg_tts")
        self.store.save_segments(
            project,
            [Segment(id="seg_1", start=0, end=1, source_text="Hello", translated_text="Привет")],
            translated=True,
        )

        with patch("translate_video.api.routes.projects._build_segment_tts_provider", return_value=FakeProvider()):
            response = self.client.post(
                "/api/v1/projects/seg_tts/segments/actions/tts",
                json={"segment_ids": ["seg_1"]},
            )

        self.assertEqual(response.status_code, 200)
        restored = self.store.load_project(self.work_root / "seg_tts")
        self.assertEqual(restored.segments[0].tts_path, "tts/seg_1.mp3")

    def test_segment_action_tts_skips_if_all_have_tts(self):
        """Bulk tts без force не должен вызывать провайдер если у всех сегментов есть TTS."""
        project = self.store.create_project("dummy.mp4", project_id="seg_tts_skip")
        self.store.save_segments(
            project,
            [Segment(
                id="seg_1", start=0, end=1,
                source_text="Hello", translated_text="Привет",
                tts_path="tts/seg_1.mp3",
            )],
            translated=True,
        )

        with patch("translate_video.api.routes.projects._build_segment_tts_provider") as mock_provider:
            response = self.client.post(
                "/api/v1/projects/seg_tts_skip/segments/actions/tts",
                json={"segment_ids": ["seg_1"]},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["changed"], 0)
        self.assertIn("уже имеют TTS", data["message"])
        mock_provider.assert_not_called()

    def test_segment_action_unknown_returns_422(self):
        """Неизвестное действие должно вернуть 422."""
        project = self.store.create_project("dummy.mp4", project_id="seg_unknown_action")
        self.store.save_segments(
            project,
            [Segment(id="seg_1", start=0, end=1, source_text="Hello")],
        )

        response = self.client.post(
            "/api/v1/projects/seg_unknown_action/segments/actions/explode",
            json={"segment_ids": ["seg_1"]},
        )

        self.assertEqual(response.status_code, 422)

    def test_segment_action_translate_resets_tts_and_reviewed_flag(self):
        """Bulk translate должен обновить перевод и сбросить зависимые TTS данные."""

        def fake_translate(_project, segments):
            for segment in segments:
                segment.translated_text = "Новый перевод"
            return segments

        project = self.store.create_project("dummy.mp4", project_id="seg_translate")
        tts_file = project.work_dir / "tts" / "seg_1.mp3"
        tts_file.parent.mkdir(parents=True, exist_ok=True)
        tts_file.write_bytes(b"mp3")
        self.store.save_segments(
            project,
            [
                Segment(
                    id="seg_1",
                    start=0,
                    end=1,
                    source_text="Hello",
                    translated_text="Старый перевод",
                    status=SegmentStatus.TRANSLATED,
                    tts_path="tts/seg_1.mp3",
                    reviewed=True,
                )
            ],
            translated=True,
        )

        with patch("translate_video.api.routes.projects._translate_selected_segments", side_effect=fake_translate):
            response = self.client.post(
                "/api/v1/projects/seg_translate/segments/actions/translate",
                json={"segment_ids": ["seg_1"], "force": True},
            )

        self.assertEqual(response.status_code, 200)
        restored = self.store.load_project(self.work_root / "seg_translate")
        self.assertEqual(restored.segments[0].translated_text, "Новый перевод")
        self.assertEqual(restored.segments[0].status, SegmentStatus.TRANSLATED)
        self.assertFalse(restored.segments[0].reviewed)
        self.assertIsNone(restored.segments[0].tts_path)
        self.assertFalse(tts_file.exists())

    def test_download_artifact(self):
        """Артефакт должен скачиваться по его типу."""

        project = self.store.create_project("dummy.mp4", project_id="download_test")
        report = project.work_dir / "qa_report.json"
        report.write_text('{"ok": true}', encoding="utf-8")
        self.store.add_artifact(
            project,
            kind=ArtifactKind.QA_REPORT,
            path=report,
            stage=Stage.QA,
            content_type="application/json",
        )

        response = self.client.get("/api/v1/projects/download_test/artifacts/qa_report")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_dubbed_audio_route_is_not_shadowed_by_artifact_kind_route(self):
        """Специфичный /artifacts/audio route должен вызываться раньше /artifacts/{kind}."""

        project = self.store.create_project("dummy.mp4", project_id="audio_route")
        audio_dir = project.work_dir / "artifacts"
        audio_dir.mkdir()
        (audio_dir / "dubbed_audio.wav").write_bytes(b"RIFF")

        response = self.client.get("/api/v1/projects/audio_route/artifacts/audio")

        self.assertEqual(response.status_code, 200)
        self.assertIn("audio/wav", response.headers["content-type"])

    def test_global_stats_route_is_not_shadowed_by_project_id_route(self):
        """GET /projects/stats должен возвращать агрегаты, а не 404 Project not found."""

        self.store.create_project("dummy.mp4", project_id="stats_one")

        response = self.client.get("/api/v1/projects/stats")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_projects"], 1)

    def test_zip_export_includes_relative_artifacts(self):
        """ZIP export должен резолвить artifact.path относительно project.work_dir."""

        project = self.store.create_project("dummy.mp4", project_id="zip_route")
        report = project.work_dir / "qa_report.json"
        report.write_text('{"ok": true}', encoding="utf-8")
        self.store.add_artifact(
            project,
            kind=ArtifactKind.QA_REPORT,
            path=report,
            stage=Stage.QA,
            content_type="application/json",
        )

        response = self.client.get("/api/v1/projects/zip_route/export/zip")

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            self.assertIn("qa_report.json", zf.namelist())

    def test_clone_project_success(self):
        """Clone endpoint не должен падать на несуществующем store.work_root/PENDING."""

        project = self.store.create_project("dummy.mp4", project_id="clone_src")
        self.store.save_segments(
            project,
            [Segment(id="seg_1", start=0, end=1, source_text="Hello")],
        )

        response = self.client.post(
            "/api/v1/projects/clone_src/clone",
            json={"new_project_id": "clone_dst", "copy_segments": True},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "created")
        cloned = self.store.load_project(self.work_root / "clone_dst")
        self.assertEqual(len(cloned.segments), 1)

    def test_download_artifact_rejects_unsafe_record_path(self):
        """Скачивание не должно отдавать файлы вне папки проекта.

        Симулирует tampered project.json: небезопасный путь инжектируется
        напрямую в artifact_records (add_artifact теперь сам отклоняет traversal).
        Endpoint должен вернуть 400.
        """
        from translate_video.core.schemas import ArtifactRecord
        project = self.store.create_project("dummy.mp4", project_id="unsafe_artifact")
        outside = self.work_root / "secret.json"
        outside.write_text("{}", encoding="utf-8")

        # Имитируем tampered/corrupted project.json с небезопасным путём
        unsafe_record = ArtifactRecord(
            kind=ArtifactKind.QA_REPORT,
            path="../secret.json",
            stage=Stage.QA,
            content_type="application/json",
        )
        project.artifact_records = [unsafe_record]
        project.artifacts[ArtifactKind.QA_REPORT.value] = "../secret.json"
        self.store.save_project(project)

        response = self.client.get("/api/v1/projects/unsafe_artifact/artifacts/qa_report")

        self.assertEqual(response.status_code, 400)

    def test_get_artifacts_rejects_path_traversal_id(self):
        """Получение артефактов не должно принимать небезопасный ID."""

        response = self.client.get("/api/v1/projects/%2E%2E/artifacts")

        self.assertEqual(response.status_code, 400)

    def test_upload_project(self):
        """Проверка загрузки файла через multipart/form-data."""
        files = {"file": ("test_vid.mp4", b"fake", "video/mp4")}
        data = {"project_id": "upload_test"}
        response = self.client.post("/api/v1/projects/upload", files=files, data=data)
        self.assertEqual(response.status_code, 200)
        project_dir = self.work_root / "upload_test"
        self.assertTrue((project_dir / "input.mp4").exists())
        self.assertEqual((project_dir / "input.mp4").read_bytes(), b"fake")
        self.assertFalse((self.work_root.parent / "test_vid.mp4").exists())

    def test_upload_rejects_path_traversal_project_id(self):
        """Загрузка должна запрещать project_id с выходом из корня."""

        files = {"file": ("test.mp4", b"fake", "video/mp4")}
        response = self.client.post(
            "/api/v1/projects/upload",
            files=files,
            data={"project_id": "../evil"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse((self.work_root.parent / "evil").exists())

    def test_upload_sanitizes_filename(self):
        """Имя загруженного файла не должно создавать вложенные пути."""

        files = {"file": ("../nested/test.mp4", b"fake", "video/mp4")}
        response = self.client.post("/api/v1/projects/upload", files=files)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["project_id"], "test")
        self.assertTrue((self.work_root / "test" / "input.mp4").exists())

    def test_save_project_segments(self):
        """API должен сохранять отредактированные сегменты перевода."""

        project = self.store.create_project("dummy.mp4", project_id="segments_test")
        self.store.save_segments(
            project,
            [Segment(id="seg_1", start=0, end=1, source_text="Hello")],
        )

        response = self.client.put(
            "/api/v1/projects/segments_test/segments",
            json={
                "translated": True,
                "segments": [
                    {
                        "id": "seg_1",
                        "start": 0,
                        "end": 1,
                        "source_text": "Hello",
                        "translated_text": "Привет",
                        "status": "translated",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["segments"][0]["translated_text"], "Привет")
        self.assertTrue((self.work_root / "segments_test" / "transcript.translated.json").exists())

    def test_patch_project_config(self):
        """Обновление конфигурации проекта через PUT /config."""

        video_path = self.work_root / "_uploads" / "v.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake")

        # создаём проект
        r = self.client.post("/api/v1/projects", json={
            "input_video": str(video_path),
            "project_id": "config_test",
        })
        self.assertEqual(r.status_code, 200)

        # меняем translation_style
        r2 = self.client.put("/api/v1/projects/config_test/config", json={
            "config": {"translation_style": "business"}
        })
        self.assertEqual(r2.status_code, 200)
        data = r2.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["config"]["translation_style"], "business")

    def test_patch_project_config_invalid_style(self):
        """Недопустимое значение translation_style -> 400."""

        video_path = self.work_root / "_uploads" / "v2.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"fake")

        self.client.post("/api/v1/projects", json={
            "input_video": str(video_path),
            "project_id": "config_invalid_test",
        })

        r = self.client.put("/api/v1/projects/config_invalid_test/config", json={
            "config": {"translation_style": "not_a_real_style"}
        })
        self.assertEqual(r.status_code, 400)

    def test_patch_project_config_not_found(self):
        """PUT /config для несуществующего проекта -> 404."""

        r = self.client.put("/api/v1/projects/nonexistent_xyz/config", json={
            "config": {"translation_style": "business"}
        })
        self.assertEqual(r.status_code, 404)
