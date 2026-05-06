"""Unit-тесты для translate_video.webhook (NM5-06).

Покрывает: is_enabled, send_project_webhook, _send_sync (success + error + HMAC).
Все сетевые вызовы мокируются — тесты полностью оффлайн.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import translate_video.webhook as wh


class TestIsEnabled(unittest.TestCase):
    """is_enabled() — зависит от WEBHOOK_URL."""

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("WEBHOOK_URL", None)
            self.assertFalse(wh.is_enabled())

    def test_enabled_when_url_set(self):
        with patch.dict(os.environ, {"WEBHOOK_URL": "https://example.com/hook"}):
            self.assertTrue(wh.is_enabled())

    def test_disabled_for_empty_string(self):
        with patch.dict(os.environ, {"WEBHOOK_URL": "   "}):
            self.assertFalse(wh.is_enabled())


class TestSendProjectWebhook(unittest.TestCase):
    """send_project_webhook — запускает daemon-поток."""

    def test_no_thread_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("WEBHOOK_URL", None)
            with patch("threading.Thread") as mock_thread:
                wh.send_project_webhook("proj-1", "completed")
                mock_thread.assert_not_called()

    def test_thread_started_when_enabled(self):
        with patch.dict(os.environ, {"WEBHOOK_URL": "https://hook.test/"}):
            thread_instance = MagicMock()
            with patch("threading.Thread", return_value=thread_instance) as mock_cls:
                wh.send_project_webhook("proj-1", "completed", elapsed_seconds=5.0)
                mock_cls.assert_called_once()
                thread_instance.start.assert_called_once()

    def test_thread_is_daemon(self):
        with patch.dict(os.environ, {"WEBHOOK_URL": "https://hook.test/"}):
            created_kwargs: dict = {}

            def capture_thread(*args, **kwargs):
                created_kwargs.update(kwargs)
                m = MagicMock()
                return m

            with patch("threading.Thread", side_effect=capture_thread):
                wh.send_project_webhook("proj-1", "failed")
            self.assertTrue(created_kwargs.get("daemon", False))


class TestSendSync(unittest.TestCase):
    """_send_sync — формирует payload и отправляет HTTP POST."""

    def _mock_resp(self, status: int = 200):
        resp = MagicMock()
        resp.status = status
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_successful_send_completed(self):
        with patch.dict(os.environ, {
            "WEBHOOK_URL": "https://hook.test/cb",
            "WEBHOOK_TIMEOUT": "5",
        }):
            os.environ.pop("WEBHOOK_SECRET", None)
            with patch("urllib.request.urlopen", return_value=self._mock_resp(200)) as mock_open:
                with patch("urllib.request.Request") as mock_req:
                    wh._send_sync("proj-x", "completed", 10.5, "")
                    mock_req.assert_called_once()
                    call_kwargs = mock_req.call_args
                    body = call_kwargs[1].get("data") or call_kwargs[0][1]
                    payload = json.loads(body.decode("utf-8"))
                    self.assertEqual(payload["event"], "project.completed")
                    self.assertEqual(payload["project_id"], "proj-x")
                    self.assertEqual(payload["status"], "completed")
                    self.assertAlmostEqual(payload["elapsed_seconds"], 10.5, places=1)
                    mock_open.assert_called_once()

    def test_successful_send_failed_event(self):
        with patch.dict(os.environ, {"WEBHOOK_URL": "https://hook.test/cb"}):
            os.environ.pop("WEBHOOK_SECRET", None)
            with patch("urllib.request.urlopen", return_value=self._mock_resp(200)):
                with patch("urllib.request.Request") as mock_req:
                    wh._send_sync("proj-y", "failed", 3.0, "timeout")
                    body = mock_req.call_args[1].get("data") or mock_req.call_args[0][1]
                    payload = json.loads(body.decode("utf-8"))
                    self.assertEqual(payload["event"], "project.failed")
                    self.assertEqual(payload["error"], "timeout")

    def test_error_message_truncated_to_500(self):
        with patch.dict(os.environ, {"WEBHOOK_URL": "https://hook.test/cb"}):
            os.environ.pop("WEBHOOK_SECRET", None)
            long_error = "x" * 1000
            with patch("urllib.request.urlopen", return_value=self._mock_resp(200)):
                with patch("urllib.request.Request") as mock_req:
                    wh._send_sync("proj-z", "failed", 0.0, long_error)
                    body = mock_req.call_args[1].get("data") or mock_req.call_args[0][1]
                    payload = json.loads(body.decode("utf-8"))
                    self.assertLessEqual(len(payload["error"]), 500)

    def test_hmac_signature_added_when_secret_set(self):
        secret = "mysecret"
        with patch.dict(os.environ, {
            "WEBHOOK_URL": "https://hook.test/cb",
            "WEBHOOK_SECRET": secret,
        }):
            with patch("urllib.request.urlopen", return_value=self._mock_resp(200)):
                with patch("urllib.request.Request") as mock_req:
                    wh._send_sync("proj-s", "completed", 1.0, "")
                    call_args = mock_req.call_args
                    body = call_args[1].get("data") or call_args[0][1]
                    headers = call_args[1].get("headers") or call_args[0][2]
                    self.assertIn("X-Signature-256", headers)
                    sig_header = headers["X-Signature-256"]
                    expected_sig = "sha256=" + hmac.new(
                        secret.encode(), body, hashlib.sha256
                    ).hexdigest()
                    self.assertEqual(sig_header, expected_sig)

    def test_no_hmac_when_no_secret(self):
        with patch.dict(os.environ, {"WEBHOOK_URL": "https://hook.test/cb"}):
            os.environ.pop("WEBHOOK_SECRET", None)
            with patch("urllib.request.urlopen", return_value=self._mock_resp(200)):
                with patch("urllib.request.Request") as mock_req:
                    wh._send_sync("proj-ns", "completed", 0.0, "")
                    headers = mock_req.call_args[1].get("headers") or mock_req.call_args[0][2]
                    self.assertNotIn("X-Signature-256", headers)

    def test_network_error_does_not_raise(self):
        with patch.dict(os.environ, {"WEBHOOK_URL": "https://hook.test/cb"}):
            os.environ.pop("WEBHOOK_SECRET", None)
            with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
                with patch("urllib.request.Request"):
                    # Не должно бросать исключение
                    wh._send_sync("proj-err", "failed", 0.0, "")

    def test_skips_when_no_url(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("WEBHOOK_URL", None)
            with patch("urllib.request.urlopen") as mock_open:
                wh._send_sync("proj-skip", "completed", 0.0, "")
                mock_open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
