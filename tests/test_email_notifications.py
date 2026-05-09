"""Тесты email-уведомлений (R12-И3)."""
import os
import unittest
from unittest.mock import patch, MagicMock


class TestEmailNotifications(unittest.TestCase):
    """EMAIL R12-И3: unit-тесты модуля notifications."""

    def test_is_enabled_false_without_env(self):
        """is_enabled() возвращает False если SMTP_HOST не задан."""
        with patch.dict(os.environ, {}, clear=False):
            env = {k: v for k, v in os.environ.items()}
            env.pop("SMTP_HOST", None)
            env.pop("NOTIFY_EMAIL", None)
            with patch.dict(os.environ, env, clear=True):
                from translate_video.notifications import is_enabled
                self.assertFalse(is_enabled())

    def test_is_enabled_true_with_env(self):
        """is_enabled() возвращает True если SMTP_HOST + NOTIFY_EMAIL заданы."""
        with patch.dict(os.environ, {"SMTP_HOST": "smtp.test.com", "NOTIFY_EMAIL": "user@test.com"}):
            from translate_video.notifications import is_enabled
            import importlib
            import translate_video.notifications as notif_mod
            importlib.reload(notif_mod)
            self.assertTrue(notif_mod.is_enabled())

    def test_send_skipped_when_not_enabled(self):
        """send_project_notification ничего не делает если SMTP не настроен."""
        with patch.dict(os.environ, {}, clear=True):
            from translate_video.notifications import send_project_notification
            # Не должно бросить исключение
            send_project_notification("proj-001", "completed")

    def test_send_creates_thread_when_enabled(self):
        """send_project_notification запускает поток когда SMTP настроен."""
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.example.com",
            "NOTIFY_EMAIL": "test@example.com",
            "SMTP_USER": "user",
            "SMTP_PASSWORD": "pass",
        }):
            with patch("threading.Thread") as mock_thread:
                mock_instance = MagicMock()
                mock_thread.return_value = mock_instance
                from translate_video.notifications import send_project_notification
                import importlib, translate_video.notifications as m
                importlib.reload(m)
                m.send_project_notification("proj-002", "completed", elapsed_s=120.0)
                mock_thread.assert_called_once()
                mock_instance.start.assert_called_once()

    def test_failed_status_included(self):
        """failed статус тоже запускает поток."""
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.example.com",
            "NOTIFY_EMAIL": "test@example.com",
        }):
            with patch("threading.Thread") as mock_thread:
                mock_instance = MagicMock()
                mock_thread.return_value = mock_instance
                import importlib, translate_video.notifications as m
                importlib.reload(m)
                m.send_project_notification("proj-003", "failed", error_msg="Pipeline error")
                mock_thread.assert_called_once()


if __name__ == "__main__":
    unittest.main()
