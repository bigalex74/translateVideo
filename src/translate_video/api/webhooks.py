"""Механизм отправки вебхуков."""

import logging
import httpx

logger = logging.getLogger(__name__)

async def notify_webhook(url: str, payload: dict) -> None:
    """Асинхронно отправляет POST-запрос с JSON payload на указанный URL."""
    if not url:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, timeout=10.0)
            logger.info(f"Webhook sent successfully to {url}")
    except Exception as e:
        logger.error(f"Failed to send webhook to {url}: {e}")
