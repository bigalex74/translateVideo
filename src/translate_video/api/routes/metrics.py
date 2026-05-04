"""Prometheus-совместимый /metrics endpoint (NM4-07).

Формат: text/plain (OpenMetrics-compatible).
Метрики:
- translate_video_info (gauge) — версия
- translate_video_running_projects (gauge) — в процессе
- translate_video_disk_usage_mb (gauge) — размер runs/
- translate_video_uptime_seconds (counter) — uptime

Безопасность: если API_KEY настроен — требует X-API-Key.
Если METRICS_ALLOW_LOCALHOST=1 — доступен с 127.0.0.1 без ключа.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from translate_video import __version__

router = APIRouter(tags=["metrics"])

_START_TIME = time.time()

# Thread-safe счётчик запросов к /metrics (NC5-02)
import threading as _threading
_REQUEST_COUNTER: dict[str, int] = {"total": 0, "errors": 0}
_COUNTER_LOCK = _threading.Lock()


def increment_request(error: bool = False) -> None:
    """Увеличить счётчик запросов."""
    with _COUNTER_LOCK:
        _REQUEST_COUNTER["total"] += 1
        if error:
            _REQUEST_COUNTER["errors"] += 1


def _text_gauge(name: str, value: float, help_text: str = "", labels: dict | None = None) -> str:
    """Сгенерировать Prometheus gauge строку."""
    label_str = ""
    if labels:
        parts = [f'{k}="{v}"' for k, v in labels.items()]
        label_str = "{" + ",".join(parts) + "}"
    lines = []
    if help_text:
        lines.append(f"# HELP {name} {help_text}")
    lines.append(f"# TYPE {name} gauge")
    lines.append(f"{name}{label_str} {value}")
    return "\n".join(lines)


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def prometheus_metrics(request: Request) -> str:
    """Prometheus-совместимые метрики приложения."""
    from translate_video.api.routes.pipeline import _running_projects  # lazy

    # Проверка доступа
    client_ip = request.client.host if request.client else ""
    allow_localhost = os.getenv("METRICS_ALLOW_LOCALHOST", "1") == "1"
    api_key = os.getenv("API_KEY", "").strip()

    # Если ключ настроен и запрос не с localhost → требуем ключ
    if api_key and not (allow_localhost and client_ip in ("127.0.0.1", "::1")):
        provided = request.headers.get("X-API-Key", "")
        if provided != api_key:
            from fastapi.responses import Response  # noqa: PLC0415
            return Response(status_code=401, content="Unauthorized")

    # Вычисляем disk usage
    disk_mb = 0.0
    try:
        work_root = Path(os.getenv("WORK_ROOT", "runs")).resolve()
        if work_root.exists():
            disk_mb = round(
                sum(f.stat().st_size for f in work_root.rglob("*") if f.is_file()) / 1024 / 1024,
                1,
            )
    except Exception:  # noqa: BLE001
        pass

    uptime_s = time.time() - _START_TIME

    # NC5-02: инкрементируем счётчик
    increment_request()

    with _COUNTER_LOCK:
        req_total = _REQUEST_COUNTER["total"]

    lines = [
        _text_gauge(
            "translate_video_info",
            1,
            "Application info",
            {"version": __version__},
        ),
        _text_gauge(
            "translate_video_running_projects",
            len(_running_projects),
            "Number of currently running translation projects",
        ),
        _text_gauge(
            "translate_video_disk_usage_mb",
            disk_mb,
            "Disk usage of runs directory in megabytes",
        ),
        _text_gauge(
            "translate_video_uptime_seconds",
            round(uptime_s, 1),
            "Application uptime in seconds",
        ),
        _text_gauge(
            "translate_video_metrics_requests_total",
            req_total,
            "Total /metrics endpoint requests (NC5-02)",
        ),
    ]

    return "\n\n".join(lines) + "\n"
