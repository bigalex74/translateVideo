"""Маршруты для запуска пайплайна."""

import asyncio
import ipaddress
import threading
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel

from translate_video.api.routes.projects import get_store
from translate_video.api.webhooks import notify_webhook
from translate_video.core.store import ProjectStore, sanitize_project_id
from translate_video.pipeline import build_stages, project_summary
from translate_video.pipeline.context import StageContext
from translate_video.pipeline.runner import PipelineRunner

router = APIRouter(prefix="/api/v1/projects", tags=["pipeline"])

# Глобальный in-memory реестр запущенных проектов (защита от race condition)
_running_lock = threading.Lock()
_running_projects: set[str] = set()

# CIDR-блоки приватных адресов (SSRF-защита)
_PRIVATE_NETWORKS = [
    ipaddress.ip_network(cidr)
    for cidr in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "::1/128",
        "fc00::/7",
    )
]


def _validate_webhook_url(url: str | None) -> None:
    """Проверить webhook URL на SSRF-безопасность.

    Разрешены только http/https URL, не указывающие на приватные IP.
    """
    if not url:
        return
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="X-Webhook-Url: только http/https схемы")
    hostname = parsed.hostname or ""
    try:
        addr = ipaddress.ip_address(hostname)
        if any(addr in net for net in _PRIVATE_NETWORKS):
            raise HTTPException(status_code=400, detail="X-Webhook-Url: приватные IP-адреса запрещены")
    except ValueError:
        pass  # hostname — не IP, проверка пройдена



class RunPipelineRequest(BaseModel):
    """Схема запроса на запуск пайплайна."""
    force: bool = False
    provider: str = "legacy"


async def run_pipeline_task(
    project_id: str,
    store: ProjectStore,
    req: RunPipelineRequest,
    webhook_url: str | None,
):
    """Фоновая задача выполнения пайплайна с отправкой вебхука."""
    try:
        safe_project_id = sanitize_project_id(project_id)
        loaded_project = store.load_project(store.root / safe_project_id)
        runner = PipelineRunner(build_stages(req.provider), force=req.force)

        # Запускаем блокирующий пайплайн в отдельном потоке,
        # чтобы не блокировать asyncio event loop
        await asyncio.to_thread(runner.run, StageContext(project=loaded_project, store=store))

        if webhook_url:
            restored = store.load_project(loaded_project.work_dir)
            summary = project_summary(restored)
            await notify_webhook(webhook_url, summary)

    except Exception as e:
        if webhook_url:
            await notify_webhook(
                webhook_url, {"project_id": project_id, "status": "failed", "error": str(e)}
            )
    finally:
        with _running_lock:
            _running_projects.discard(project_id)


@router.post("/{project_id}/run")
def run_pipeline(
    project_id: str,
    req: RunPipelineRequest,
    background_tasks: BackgroundTasks,
    x_webhook_url: Annotated[str | None, Header()] = None,
    store: ProjectStore = Depends(get_store),
):
    """Запустить пайплайн для проекта в фоновом режиме."""
    try:
        safe_project_id = sanitize_project_id(project_id)
        _validate_webhook_url(x_webhook_url)
        store.load_project(store.root / safe_project_id)  # проверяем существование

        with _running_lock:
            if safe_project_id in _running_projects:
                raise HTTPException(
                    status_code=409,
                    detail=f"Пайплайн для проекта '{safe_project_id}' уже запущен",
                )
            _running_projects.add(safe_project_id)

        background_tasks.add_task(run_pipeline_task, safe_project_id, store, req, x_webhook_url)
        return {
            "status": "accepted",
            "project_id": safe_project_id,
            "message": "Pipeline started in background",
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
