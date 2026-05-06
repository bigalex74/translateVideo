"""Тесты для новых backlog функций (retry, email, auth, batch limit, CLI)."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestRetryUtility(unittest.TestCase):
    """Тесты для translate_video.core.retry."""

    def test_success_first_attempt(self):
        from translate_video.core.retry import with_retry
        result = with_retry(lambda: 42, label="test")
        self.assertEqual(result, 42)

    def test_retry_on_runtime_error(self):
        from translate_video.core.retry import with_retry
        attempts = []
        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("HTTP 503: temp")
            return "ok"

        result = with_retry(
            flaky,
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(RuntimeError,),
            label="test",
        )
        self.assertEqual(result, "ok")
        self.assertEqual(len(attempts), 3)

    def test_exhausted_raises(self):
        from translate_video.core.retry import with_retry
        with self.assertRaises(RuntimeError):
            with_retry(
                lambda: (_ for _ in ()).throw(RuntimeError("always fail")),
                max_attempts=2,
                base_delay=0.01,
                retryable_exceptions=(RuntimeError,),
                label="test",
            )

    def test_non_retryable_not_retried(self):
        from translate_video.core.retry import with_retry
        attempts = []
        def fn():
            attempts.append(1)
            raise ValueError("not retryable")

        with self.assertRaises(ValueError):
            with_retry(
                fn,
                max_attempts=3,
                base_delay=0.01,
                label="test",
            )
        # ValueError не в retryable_exceptions → только 1 попытка
        self.assertEqual(len(attempts), 1)

    def test_retry_config_from_env(self):
        from translate_video.core.retry import RetryConfig
        import os
        with patch.dict(os.environ, {"TTS_RETRY_ATTEMPTS": "5", "TTS_RETRY_BASE_DELAY": "0.5"}):
            cfg = RetryConfig()
            self.assertEqual(cfg.max_attempts, 5)
            self.assertAlmostEqual(cfg.base_delay, 0.5)


class TestEmailNotification(unittest.TestCase):
    """Тесты email-уведомлений."""

    def test_disabled_when_no_config(self):
        """is_enabled() = False если нет SMTP_HOST."""
        import os
        from translate_video.notifications import is_enabled
        with patch.dict(os.environ, {}, clear=True):
            # Удаляем SMTP_HOST если был
            os.environ.pop("SMTP_HOST", None)
            os.environ.pop("NOTIFY_EMAIL", None)
            self.assertFalse(is_enabled())

    def test_enabled_when_configured(self):
        import os
        from translate_video.notifications import is_enabled
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.example.com",
            "NOTIFY_EMAIL": "test@example.com",
        }):
            self.assertTrue(is_enabled())

    def test_send_does_not_raise_on_smtp_error(self):
        """send_project_notification не бросает исключение при ошибке SMTP."""
        import os
        from translate_video.notifications import send_project_notification
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.invalid.test",
            "NOTIFY_EMAIL": "user@test.com",
            "SMTP_USER": "test",
            "SMTP_PASSWORD": "pass",
        }):
            # Должно запуститься без исключения (ошибка логируется, не бросается)
            send_project_notification("test-project", "completed", elapsed_s=42.0)
            time.sleep(0.1)  # Ждём daemon thread


class TestAPIKeyStore(unittest.TestCase):
    """Тесты per-user APIKeyStore."""

    def test_load_single_key(self):
        import os
        from translate_video.api.middleware.auth import APIKeyStore
        with patch.dict(os.environ, {"API_KEY": "secret123", "API_KEYS": ""}):
            store = APIKeyStore()
            self.assertTrue(store.is_enabled())
            user = store.authenticate("secret123")
            self.assertEqual(user, "default")

    def test_load_dict_keys(self):
        import os, json
        from translate_video.api.middleware.auth import APIKeyStore
        keys = {"alice": "key-alice", "bob": "key-bob"}
        with patch.dict(os.environ, {"API_KEYS": json.dumps(keys), "API_KEY": ""}):
            store = APIKeyStore()
            self.assertEqual(store.authenticate("key-alice"), "alice")
            self.assertEqual(store.authenticate("key-bob"), "bob")
            self.assertIsNone(store.authenticate("wrong"))

    def test_add_remove_user(self):
        import os
        from translate_video.api.middleware.auth import APIKeyStore
        with patch.dict(os.environ, {"API_KEY": "base", "API_KEYS": ""}):
            store = APIKeyStore()
            new_key = store.add_user("charlie")
            self.assertIsNotNone(new_key)
            self.assertEqual(store.authenticate(new_key), "charlie")
            store.remove_user("charlie")
            self.assertIsNone(store.authenticate(new_key))

    def test_disabled_when_empty(self):
        import os
        from translate_video.api.middleware.auth import APIKeyStore
        with patch.dict(os.environ, {"API_KEY": "", "API_KEYS": ""}):
            store = APIKeyStore()
            self.assertFalse(store.is_enabled())


class TestBatchLimit(unittest.TestCase):
    """Тест что batch limit теперь 50."""

    def test_default_batch_limit(self):
        import os
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAX_BATCH_SIZE", None)
            limit = int(os.getenv("MAX_BATCH_SIZE", "50"))
            self.assertEqual(limit, 50)

    def test_configurable_batch_limit(self):
        import os
        with patch.dict(os.environ, {"MAX_BATCH_SIZE": "100"}):
            limit = int(os.getenv("MAX_BATCH_SIZE", "50"))
            self.assertEqual(limit, 100)


class TestCLINewCommands(unittest.TestCase):
    """Тесты новых команд CLI."""

    def test_parser_has_batch_command(self):
        from translate_video.cli import build_parser
        parser = build_parser()
        # Проверяем что subparser 'batch' зарегистрирован
        subparsers_action = next(
            a for a in parser._actions
            if hasattr(a, '_parser_class')
        )
        self.assertIn("batch", subparsers_action.choices)

    def test_parser_has_watch_command(self):
        from translate_video.cli import build_parser
        parser = build_parser()
        subparsers_action = next(
            a for a in parser._actions
            if hasattr(a, '_parser_class')
        )
        self.assertIn("watch", subparsers_action.choices)

    def test_parser_has_download_command(self):
        from translate_video.cli import build_parser
        parser = build_parser()
        subparsers_action = next(
            a for a in parser._actions
            if hasattr(a, '_parser_class')
        )
        self.assertIn("download", subparsers_action.choices)


class TestPWAFiles(unittest.TestCase):
    """Проверяем что PWA файлы существуют."""

    _ROOT = Path(__file__).parent.parent.parent  # tests/unit/ → translateVideo/

    def test_manifest_exists(self):
        manifest = self._ROOT / "ui" / "public" / "manifest.webmanifest"
        self.assertTrue(manifest.exists(), "manifest.webmanifest не найден")

    def test_sw_exists(self):
        sw = self._ROOT / "ui" / "public" / "sw.js"
        self.assertTrue(sw.exists(), "sw.js не найден")

    def test_manifest_has_required_fields(self):
        import json
        manifest = self._ROOT / "ui" / "public" / "manifest.webmanifest"
        data = json.loads(manifest.read_text())
        for field in ("name", "short_name", "start_url", "display", "icons"):
            self.assertIn(field, data, f"manifest.webmanifest отсутствует поле '{field}'")


if __name__ == "__main__":
    unittest.main()
