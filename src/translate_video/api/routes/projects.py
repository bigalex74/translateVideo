"""Маршруты для работы с проектами."""

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from translate_video.cli import _project_summary
from translate_video.core.config import PipelineConfig
from translate_video.core.store import ProjectStore

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def get_store() -> ProjectStore:
    """Зависимость для получения хранилища проектов."""
    work_root = Path(os.getenv("WORK_ROOT", "runs"))
    return ProjectStore(work_root)


class CreateProjectRequest(BaseModel):
    """Схема запроса на создание проекта."""
    input_video: str
    project_id: str | None = None
    config: dict[str, Any] = {}


@router.post("")
def create_project(req: CreateProjectRequest, store: ProjectStore = Depends(get_store)):
    """Создать новый проект перевода."""
    config = PipelineConfig.from_dict(req.config) if req.config else PipelineConfig()
    try:
        project = store.create_project(
            input_video=req.input_video,
            config=config,
            project_id=req.project_id,
        )
        return _project_summary(project)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}")
def get_project_status(project_id: str, store: ProjectStore = Depends(get_store)):
    """Получить статус и данные проекта."""
    try:
        project = store.load_project(store.work_root / project_id)
        summary = _project_summary(project)
        summary["stage_runs"] = [run.to_dict() for run in project.stage_runs]
        return summary
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/artifacts")
def get_project_artifacts(project_id: str, store: ProjectStore = Depends(get_store)):
    """Получить список артефактов проекта."""
    try:
        project = store.load_project(store.work_root / project_id)
        return {
            "project_id": project.id,
            "work_dir": project.work_dir.as_posix(),
            "artifacts": [record.to_dict() for record in project.artifact_records],
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
