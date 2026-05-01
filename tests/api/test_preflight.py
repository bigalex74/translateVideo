import tempfile
from pathlib import Path
from unittest import TestCase

from fastapi.testclient import TestClient

from translate_video.api.main import app


class APIPreflightTest(TestCase):
    """Тесты API предварительной проверки входного видео."""

    def setUp(self):
        self.client = TestClient(app)

    def test_preflight_fake_provider_success(self):
        """Предпроверка с fake-провайдером должна проходить для существующего файла."""

        with tempfile.TemporaryDirectory() as temp_dir:
            input_video = Path(temp_dir) / "input.mp4"
            input_video.write_bytes(b"video")

            response = self.client.post(
                "/api/v1/preflight",
                json={"input_video": input_video.as_posix(), "provider": "fake"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["provider"], "fake")

    def test_preflight_reports_missing_file(self):
        """Предпроверка должна явно сообщать об отсутствующем файле."""

        response = self.client.post(
            "/api/v1/preflight",
            json={"input_video": "/missing/video.mp4", "provider": "fake"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])
