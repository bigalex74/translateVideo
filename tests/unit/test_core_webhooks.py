"""Модульные тесты webhook-событий."""

import unittest

from translate_video.core.webhooks import WebhookEvent


class WebhookEventTest(unittest.TestCase):
    """Проверяет JSON-контракт webhook-событий."""

    def test_event_is_json_ready_and_schema_versioned(self):
        """Событие должно быть JSON-совместимым и версионированным."""

        event = WebhookEvent(
            event="job.stage.completed",
            project_id="project_1",
            job_id="job_1",
            stage="translation",
            status="completed",
            artifact_path="transcript.translated.json",
            payload={"segments": 12},
        )

        payload = event.to_dict()

        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["event"], "job.stage.completed")
        self.assertEqual(payload["stage"], "translate")
        self.assertEqual(payload["payload"]["segments"], 12)
        self.assertTrue(payload["id"].startswith("evt_"))
        self.assertIn("created_at", payload)
        self.assertIsNotNone(payload["idempotency_key"])

    def test_failure_event_carries_error_shape(self):
        """Событие ошибки должно нести статус и текст ошибки."""

        event = WebhookEvent(
            event="job.stage.failed",
            project_id="project_1",
            stage="render",
            status="failed",
            error="ошибка ffmpeg",
        )

        payload = event.to_dict()

        self.assertEqual(payload["event"], "job.stage.failed")
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["stage"], "render")
        self.assertEqual(payload["error"], "ошибка ffmpeg")


if __name__ == "__main__":
    unittest.main()
