import unittest

from translate_video.core.webhooks import WebhookEvent


class WebhookEventTest(unittest.TestCase):
    def test_event_is_json_ready_and_schema_versioned(self):
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
        self.assertEqual(payload["payload"]["segments"], 12)
        self.assertTrue(payload["id"].startswith("evt_"))
        self.assertIn("created_at", payload)


if __name__ == "__main__":
    unittest.main()

