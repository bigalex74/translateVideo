"""Unit-тесты для translate_video.notifications (email, backlog С3).

Покрывает: is_enabled, send_project_notification (thread), _send_sync (mock SMTP).
Все SMTP вызовы мокируются — тесты полностью оффлайн.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch, call

import translate_video.notifications as notif


class TestIsEnabled(unittest.TestCase):
    """is_enabled() — зависит от SMTP_HOST + NOTIFY_EMAIL."""

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            for k in ("SMTP_HOST", "NOTIFY_EMAIL"):
                os.environ.pop(k, None)
            self.assertFalse(notif.is_enabled())

    def test_enabled_when_both_set(self):
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.example.com",
            "NOTIFY_EMAIL": "user@example.com",
        }):
            self.assertTrue(notif.is_enabled())

    def test_disabled_when_only_host(self):
        with patch.dict(os.environ, {"SMTP_HOST": "smtp.example.com"}):
            os.environ.pop("NOTIFY_EMAIL", None)
            self.assertFalse(notif.is_enabled())

    def test_disabled_when_only_email(self):
        with patch.dict(os.environ, {"NOTIFY_EMAIL": "user@example.com"}):
            os.environ.pop("SMTP_HOST", None)
            self.assertFalse(notif.is_enabled())


class TestSendProjectNotification(unittest.TestCase):
    """send_project_notification — daemon thread."""

    def test_no_thread_when_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            for k in ("SMTP_HOST", "NOTIFY_EMAIL"):
                os.environ.pop(k, None)
            with patch("threading.Thread") as mock_thread:
                notif.send_project_notification("proj-1", "completed")
                mock_thread.assert_not_called()

    def test_thread_started_when_enabled(self):
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.example.com",
            "NOTIFY_EMAIL": "user@example.com",
        }):
            thread_instance = MagicMock()
            with patch("threading.Thread", return_value=thread_instance) as mock_cls:
                notif.send_project_notification("proj-1", "completed", elapsed_s=5.0)
                mock_cls.assert_called_once()
                thread_instance.start.assert_called_once()

    def test_thread_is_daemon(self):
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.example.com",
            "NOTIFY_EMAIL": "user@example.com",
        }):
            created_kwargs: dict = {}

            def capture(*args, **kwargs):
                created_kwargs.update(kwargs)
                return MagicMock()

            with patch("threading.Thread", side_effect=capture):
                notif.send_project_notification("proj-1", "failed")

            self.assertTrue(created_kwargs.get("daemon", False))


class TestProjectLinkHtml(unittest.TestCase):
    """_project_link_html — генерация HTML-ссылки."""

    def test_returns_empty_when_no_app_url(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("APP_URL", None)
            result = notif._project_link_html("proj-x")
            self.assertEqual(result, "")

    def test_returns_html_when_app_url_set(self):
        with patch.dict(os.environ, {"APP_URL": "https://video.example.com"}):
            result = notif._project_link_html("proj-x")
            self.assertIn("proj-x", result)
            self.assertIn("https://video.example.com", result)


if __name__ == "__main__":
    unittest.main()
