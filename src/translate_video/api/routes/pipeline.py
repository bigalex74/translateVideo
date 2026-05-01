"""Маршруты для запуска пайплайна."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel

from translate_video.api.routes.projects import get_store
from translate_video.api.webhooks import notify_webhook
from translate_video.cli import _build_stages, _project_summary
from translate_video.core.store import ProjectStore, sanitize_project_id
from translate_video.pipeline.context import StageContext
from translate_video.pipeline.runner import PipelineRunner

router = APIRouter(prefix="/api/v1/projects", tags=["pipeline"])


class RunPipelineRequest(BaseModel):
    """Схема запроса на запуск пайплайна."""
    force: bool = False
    provider: str = "fake"


async def run_pipeline_task(
    project_id: str,
    store: ProjectStore,
    req: RunPipelineRequest,
    webhook_url: str | None,
):
    """Фоновая задача выполнения пайплайна с отправкой вебхука."""
    try:
        safe_project_id = sanitize_project_id(project_id)
        project = store.load_project(store.root / safe_project_id)
        runner = PipelineRunner(_build_stages(req.provider), force=req.force)
        
        # Запускаем блокирующий пайплайн в отдельном потоке, 
        # чтобы не блокировать asyncio event loop (так как этапы могут быть долгими синхронными)
        await asyncio.to_thread(runner.run, StageContext(project=project, store=store))

        if webhook_url:
            restored = store.load_project(project.work_dir)
            summary = _project_summary(restored)
            await notify_webhook(webhook_url, summary)

    except Exception as e:
        if webhook_url:
            await notify_webhook(
                webhook_url, {"project_id": project_id, "status": "failed", "error": str(e)}
            )


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
        # Проверяем, существует ли проект
        safe_project_id = sanitize_project_id(project_id)
        store.load_project(store.root / safe_project_id)
        background_tasks.add_task(run_pipeline_task, safe_project_id, store, req, x_webhook_url)
        return {
            "status": "accepted",
            "project_id": safe_project_id,
            "message": "Pipeline started in background",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
