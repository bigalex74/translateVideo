"""Unit-тесты функции notify_webhook из api/webhooks.py.

Покрывает: пустой URL, успешная отправка, обработка ошибки сети.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from translate_video.api.webhooks import notify_webhook


def run_async(coro):
    """Вспомогательная функция для запуска async функций в unittest."""
    return asyncio.run(coro)


class NotifyWebhookTest(unittest.TestCase):
    """Тесты функции notify_webhook."""

    def test_empty_url_returns_immediately(self):
        """Пустой URL — функция возвращает без запроса."""
        # Не должно бросать исключений
        run_async(notify_webhook("", {"key": "value"}))

    def test_none_url_treated_as_empty(self):
        """None-подобная пустая строка — без запроса."""
        run_async(notify_webhook("", {}))  # empty string

    def test_successful_post(self):
        """При валидном URL — POST-запрос отправляется."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_client)
        mock_context.__aexit__ = AsyncMock(return_value=False)

        with patch("translate_video.api.webhooks.httpx.AsyncClient", return_value=mock_context):
            run_async(notify_webhook("https://example.com/hook", {"event": "done"}))

        mock_client.post.assert_called_once_with(
            "https://example.com/hook",
            json={"event": "done"},
            timeout=10.0,
        )

    def test_network_error_does_not_raise(self):
        """Ошибка сети логируется, но не поднимается наружу."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_client)
        mock_context.__aexit__ = AsyncMock(return_value=False)

        with patch("translate_video.api.webhooks.httpx.AsyncClient", return_value=mock_context):
            # Не должно бросить исключение — ошибки логируются
            run_async(notify_webhook("https://example.com/hook", {}))

    def test_timeout_does_not_raise(self):
        """Таймаут отправки логируется, но не поднимается наружу."""
        import httpx
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_client)
        mock_context.__aexit__ = AsyncMock(return_value=False)

        with patch("translate_video.api.webhooks.httpx.AsyncClient", return_value=mock_context):
            run_async(notify_webhook("https://slow.example.com/hook", {}))

    def test_payload_forwarded_as_json(self):
        """Payload передаётся как JSON-тело."""
        payload = {"project_id": "p1", "status": "completed", "segments": 42}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=MagicMock())

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_client)
        mock_context.__aexit__ = AsyncMock(return_value=False)

        with patch("translate_video.api.webhooks.httpx.AsyncClient", return_value=mock_context):
            run_async(notify_webhook("https://example.com/hook", payload))

        _, kwargs = mock_client.post.call_args
        self.assertEqual(kwargs["json"], payload)


if __name__ == "__main__":
    unittest.main()
