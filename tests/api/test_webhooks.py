import asyncio
import unittest
from unittest.mock import patch, AsyncMock
from translate_video.api.webhooks import notify_webhook

class WebhooksTest(unittest.TestCase):
    """Тесты отправки вебхуков."""

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    def test_notify_webhook_success(self, mock_post):
        asyncio.run(notify_webhook("http://example.com", {"data": "test"}))
        mock_post.assert_called_once()

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    def test_notify_webhook_error(self, mock_post):
        mock_post.side_effect = Exception("Network Error")
        asyncio.run(notify_webhook("http://example.com", {"data": "test"}))
        mock_post.assert_called_once()

    def test_notify_empty_url(self):
        asyncio.run(notify_webhook("", {"data": "test"}))

if __name__ == "__main__":
    unittest.main()
