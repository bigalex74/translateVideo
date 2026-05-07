"""Тесты для translate_video.core.retry — exponential backoff (TVIDEO-222)."""

import time
import unittest
from unittest.mock import MagicMock, call, patch

from translate_video.core.retry import RetryConfig, with_retry


class TestWithRetrySuccess(unittest.TestCase):
    """with_retry возвращает результат при успехе с первой попытки."""

    def test_returns_value_on_first_attempt(self):
        fn = MagicMock(return_value=42)
        result = with_retry(fn, max_attempts=3, base_delay=0.0)
        self.assertEqual(result, 42)
        self.assertEqual(fn.call_count, 1)

    def test_passes_args_and_kwargs(self):
        fn = MagicMock(return_value="ok")
        result = with_retry(fn, "a", "b", max_attempts=2, base_delay=0.0, key="v")
        fn.assert_called_once_with("a", "b", key="v")
        self.assertEqual(result, "ok")


class TestWithRetryRetries(unittest.TestCase):
    """with_retry повторяет при retryable_exceptions."""

    def test_retries_until_success(self):
        fn = MagicMock(side_effect=[OSError("tmp"), OSError("tmp"), "success"])
        with patch("time.sleep"):
            result = with_retry(fn, max_attempts=3, base_delay=0.01, jitter=False,
                                retryable_exceptions=(OSError,))
        self.assertEqual(result, "success")
        self.assertEqual(fn.call_count, 3)

    def test_raises_after_max_attempts(self):
        fn = MagicMock(side_effect=ConnectionError("net"))
        with patch("time.sleep"):
            with self.assertRaises(ConnectionError):
                with_retry(fn, max_attempts=3, base_delay=0.01, jitter=False,
                            retryable_exceptions=(ConnectionError,))
        self.assertEqual(fn.call_count, 3)

    def test_does_not_retry_non_retryable_exception(self):
        fn = MagicMock(side_effect=ValueError("bad input"))
        with self.assertRaises(ValueError):
            with_retry(fn, max_attempts=3, base_delay=0.01,
                        retryable_exceptions=(OSError,))
        self.assertEqual(fn.call_count, 1)


class TestWithRetryDelays(unittest.TestCase):
    """with_retry применяет exponential backoff с ограничением max_delay."""

    def test_delay_capped_at_max_delay(self):
        fn = MagicMock(side_effect=[OSError(), OSError(), OSError()])
        sleeps = []
        with patch("time.sleep", side_effect=lambda s: sleeps.append(s)):
            with self.assertRaises(OSError):
                with_retry(fn, max_attempts=3, base_delay=100.0, max_delay=5.0,
                            jitter=False, retryable_exceptions=(OSError,))
        # Оба sleep должны быть ≤ max_delay
        self.assertTrue(all(s <= 5.0 for s in sleeps))

    def test_backoff_factor_applied(self):
        fn = MagicMock(side_effect=[OSError(), OSError(), "ok"])
        sleeps = []
        with patch("time.sleep", side_effect=lambda s: sleeps.append(s)):
            with_retry(fn, max_attempts=3, base_delay=1.0, backoff_factor=3.0,
                        jitter=False, max_delay=999.0, retryable_exceptions=(OSError,))
        self.assertEqual(len(sleeps), 2)
        # Первый sleep ≈ 1.0, второй ≈ 3.0
        self.assertAlmostEqual(sleeps[0], 1.0, places=3)
        self.assertAlmostEqual(sleeps[1], 3.0, places=3)


class TestWithRetryHTTPCode(unittest.TestCase):
    """with_retry не повторяет при 4xx (кроме 429)."""

    def test_http_429_waits_minimum_5s(self):
        fn = MagicMock(side_effect=[OSError("HTTP 429: too many"), OSError("HTTP 429: too many"), "ok"])
        sleeps = []
        with patch("time.sleep", side_effect=lambda s: sleeps.append(s)):
            result = with_retry(fn, max_attempts=3, base_delay=0.01, jitter=False,
                                max_delay=60.0, retryable_exceptions=(OSError,))
        self.assertEqual(result, "ok")
        # При 429 delay должен быть не менее 5.0
        self.assertTrue(all(s >= 5.0 for s in sleeps))

    def test_http_400_not_retried(self):
        fn = MagicMock(side_effect=OSError("HTTP 400: bad request"))
        with self.assertRaises(OSError):
            with_retry(fn, max_attempts=3, base_delay=0.01,
                        retryable_exceptions=(OSError,))
        self.assertEqual(fn.call_count, 1)


class TestRetryConfig(unittest.TestCase):
    """RetryConfig читает из env-переменных."""

    def test_default_config(self):
        cfg = RetryConfig()
        self.assertEqual(cfg.max_attempts, 3)
        self.assertEqual(cfg.base_delay, 1.0)
        self.assertGreater(cfg.max_delay, 0)

    def test_call_delegates_to_with_retry(self):
        cfg = RetryConfig(max_attempts=2, base_delay=0.01, max_delay=1.0)
        fn = MagicMock(return_value="done")
        result = cfg.call(fn, "arg", label="test")
        self.assertEqual(result, "done")
        fn.assert_called_once_with("arg")


class TestWebhookRetryIntegration(unittest.TestCase):
    """Webhook _send_sync повторяет при сетевых ошибках."""

    def test_webhook_retries_on_os_error(self):
        """При временной OSError webhook делает retry."""
        import os
        with patch.dict(os.environ, {"WEBHOOK_URL": "http://test.local/hook"}):
            with patch("urllib.request.urlopen",
                       side_effect=[OSError("conn"), OSError("conn"), MagicMock(status=200)]):
                with patch("time.sleep"):
                    from translate_video import webhook
                    # Не должно бросить исключение
                    try:
                        webhook._send_sync("proj1", "completed", 5.0, "")
                    except Exception as e:
                        self.fail(f"Webhook не должен бросать: {e}")


if __name__ == "__main__":
    unittest.main()
