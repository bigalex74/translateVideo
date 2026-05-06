"""Email-уведомления о завершении перевода (backlog LOW priority).

## Настройка

Задайте переменные окружения:
- ``SMTP_HOST``       — SMTP сервер (напр. smtp.gmail.com)
- ``SMTP_PORT``       — порт (default: 587)
- ``SMTP_USER``       — логин
- ``SMTP_PASSWORD``   — пароль (App Password для Gmail)
- ``SMTP_FROM``       — адрес отправителя (default: SMTP_USER)
- ``NOTIFY_EMAIL``    — получатель (обязательный)
- ``SMTP_TLS``        — "0" чтобы отключить STARTTLS (default: "1")

## Использование

```python
from translate_video.notifications.email import send_project_notification

send_project_notification(project_id="my-project", status="completed")
```

Ошибки отправки логируются, но не прерывают пайплайн.
"""

from __future__ import annotations

import os
import smtplib
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from translate_video.core.log import get_logger

_log = get_logger(__name__)


def is_enabled() -> bool:
    """Вернуть True если email-уведомления настроены."""
    return bool(os.getenv("SMTP_HOST") and os.getenv("NOTIFY_EMAIL"))


def send_project_notification(
    project_id: str,
    status: str,
    *,
    error_msg: str | None = None,
    elapsed_s: float | None = None,
) -> None:
    """Отправить email-уведомление о результате перевода (non-blocking).

    Запускается в отдельном потоке чтобы не блокировать пайплайн.
    """
    if not is_enabled():
        return

    # Запускаем в daemon-потоке — не блокируем пайплайн
    t = threading.Thread(
        target=_send_sync,
        kwargs=dict(
            project_id=project_id,
            status=status,
            error_msg=error_msg,
            elapsed_s=elapsed_s,
        ),
        daemon=True,
    )
    t.start()


def _project_link_html(project_id: str) -> str:
    """Сгенерировать HTML-блок с кнопкой-ссылкой на проект."""
    app_url = os.getenv("APP_URL", "").rstrip("/")
    if not app_url:
        return ""
    url = f"{app_url}/?project={project_id}"
    return f"""
    <div style="margin: 16px 0;">
      <a href="{url}" style="
        display:inline-block; padding:10px 20px;
        background:#6366f1; color:#fff; text-decoration:none;
        border-radius:8px; font-weight:bold; font-size:14px;">
        🚀 Открыть проект
      </a>
    </div>
    """


def _send_sync(
    project_id: str,
    status: str,
    *,
    error_msg: str | None = None,
    elapsed_s: float | None = None,
) -> None:
    """Синхронная отправка (вызывается из потока)."""
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)
    notify_to = os.getenv("NOTIFY_EMAIL", "")
    use_tls = os.getenv("SMTP_TLS", "1") not in ("0", "false", "no")

    if not smtp_host or not notify_to:
        return

    is_ok = status.lower() in ("completed", "done")
    icon = "✅" if is_ok else "❌"
    elapsed_str = f"{elapsed_s:.0f} сек" if elapsed_s else "—"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    subject = f"{icon} AI Video Translator: {project_id} — {status}"

    html_body = f"""
    <html><body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
      <h2 style="color: {'#22c55e' if is_ok else '#ef4444'};">
        {icon} Перевод {'завершён' if is_ok else 'завершился с ошибкой'}
      </h2>
      <table style="border-collapse:collapse; width:100%;">
        <tr><td style="padding:8px; color:#64748b;">Проект:</td>
            <td style="padding:8px;"><b>{project_id}</b></td></tr>
        <tr><td style="padding:8px; color:#64748b;">Статус:</td>
            <td style="padding:8px;">{status}</td></tr>
        <tr><td style="padding:8px; color:#64748b;">Время обработки:</td>
            <td style="padding:8px;">{elapsed_str}</td></tr>
        <tr><td style="padding:8px; color:#64748b;">Дата:</td>
            <td style="padding:8px;">{now}</td></tr>
        {f'<tr><td style="padding:8px; color:#ef4444;">Ошибка:</td><td style="padding:8px; color:#ef4444;">{error_msg[:300]}</td></tr>' if error_msg else ''}
      </table>
      {_project_link_html(project_id)}
      <hr style="border:none; border-top:1px solid #e2e8f0; margin:24px 0;">
      <p style="color:#94a3b8; font-size:12px;">AI Video Translator — автоматическое уведомление</p>
    </body></html>
    """

    text_body = f"""
AI Video Translator — Уведомление
Проект: {project_id}
Статус: {status}
Время: {elapsed_str}
Дата: {now}
{f"Ошибка: {error_msg}" if error_msg else ""}
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = notify_to
    reply_to = os.getenv("SMTP_REPLY_TO", smtp_from)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if use_tls:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, notify_to, msg.as_string())
        else:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, notify_to, msg.as_string())

        _log.info(
            "email.sent",
            project=project_id,
            status=status,
            to=notify_to,
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning(
            "email.error",
            project=project_id,
            error=str(exc)[:200],
        )
