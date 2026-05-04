"""Webhook уведомления при завершении/ошибке перевода (NM5-06).

## Настройка

Задайте переменные окружения:
- ``WEBHOOK_URL``          — URL для POST-запроса
- ``WEBHOOK_SECRET``       — Секрет для HMAC-SHA256 подписи (опционально)
- ``WEBHOOK_TIMEOUT``      — Таймаут в секундах (default: 10)

## Формат запроса

POST WEBHOOK_URL
Content-Type: application/json
X-Signature-256: sha256=<hmac-sha256-hex> (если WEBHOOK_SECRET задан)

{
  "event": "project.completed" | "project.failed",
  "project_id": "...",
  "status": "completed" | "failed",
  "elapsed_seconds": 123,
  "version": "1.43.0",
  "timestamp": "2026-05-04T20:00:00Z"
}
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import urllib.request
from datetime import datetime, timezone

_log = logging.getLogger(__name__)


def is_enabled() -> bool:
    """Webhook настроен если WEBHOOK_URL задан."""
    return bool(os.getenv("WEBHOOK_URL", "").strip())


def send_project_webhook(
    project_id: str,
    status: str,
    elapsed_seconds: float = 0.0,
    error_message: str = "",
) -> None:
    """Отправить webhook асинхронно (daemon thread).

    Не бросает исключений — все ошибки логируются.
    """
    if not is_enabled():
        return
    t = threading.Thread(
        target=_send_sync,
        args=(project_id, status, elapsed_seconds, error_message),
        daemon=True,
    )
    t.start()


def _send_sync(
    project_id: str,
    status: str,
    elapsed_seconds: float,
    error_message: str,
) -> None:
    """Синхронная отправка webhook."""
    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    if not webhook_url:
        return

    from translate_video import __version__  # noqa: PLC0415

    event = "project.completed" if status == "completed" else "project.failed"
    payload = {
        "event": event,
        "project_id": project_id,
        "status": status,
        "elapsed_seconds": round(elapsed_seconds, 1),
        "version": __version__,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    if error_message:
        payload["error"] = error_message[:500]

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers: dict[str, str] = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": f"AI-Video-Translator/{__version__}",
    }

    # HMAC подпись (NM5-06 security)
    secret = os.getenv("WEBHOOK_SECRET", "").strip()
    if secret:
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Signature-256"] = f"sha256={sig}"

    timeout = int(os.getenv("WEBHOOK_TIMEOUT", "10"))

    try:
        req = urllib.request.Request(
            webhook_url,
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _log.info(
                "webhook.sent project_id=%s status=%s http=%d",
                project_id,
                status,
                resp.status,
            )
    except Exception as exc:  # noqa: BLE001
        _log.warning("webhook.failed project_id=%s error=%s", project_id, str(exc)[:200])
