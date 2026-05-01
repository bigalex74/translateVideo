"""Маршруты для работы с проектами."""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from translate_video.cli import _project_summary
from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import ArtifactKind, Segment, VideoProject
from translate_video.core.store import ProjectStore, sanitize_filename, sanitize_project_id

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
logger = logging.getLogger(__name__)


def get_store() -> ProjectStore:
    """Зависимость для получения хранилища проектов."""
    work_root = Path(os.getenv("WORK_ROOT", "runs")).resolve()
    return ProjectStore(work_root)


class CreateProjectRequest(BaseModel):
    """Схема запроса на создание проекта."""

    input_video: str
    project_id: str | None = None
    config: dict[str, Any] = {}


class SaveSegmentsRequest(BaseModel):
    """Схема запроса на сохранение сегментов проекта."""

    segments: list[dict[str, Any]]
    translated: bool = True


def project_payload(project: VideoProject, include_segments: bool = True) -> dict[str, Any]:
    """Вернуть API-представление проекта для UI и внешних интеграций."""

    payload = _project_summary(project)
    payload["config"] = project.config.to_dict()
    payload["artifact_records"] = [record.to_dict() for record in project.artifact_records]
    payload["stage_runs"] = [run.to_dict() for run in project.stage_runs]
    payload["segments"] = (
        [segment.to_dict() for segment in project.segments]
        if include_segments
        else len(project.segments)
    )
    return payload


@router.post("")
def create_project(req: CreateProjectRequest, store: ProjectStore = Depends(get_store)):
    """Создать новый проект перевода по локальному пути или URL."""
    config = PipelineConfig.from_dict(req.config) if req.config else PipelineConfig()
    try:
        project_id = sanitize_project_id(req.project_id) if req.project_id else None
        project = store.create_project(
            input_video=req.input_video,
            config=config,
            project_id=project_id,
        )
        input_path = Path(req.input_video)
        if input_path.is_file():
            store.attach_input_video(project, input_path)
        return project_payload(project)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Неожиданная ошибка при создании проекта")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/upload")
def create_project_from_file(
    file: UploadFile = File(...),
    project_id: str | None = Form(None),
    config: str = Form("{}"),
    store: ProjectStore = Depends(get_store),
):
    """Создать новый проект загрузив файл видео."""
    try:
        conf_dict = json.loads(config)
        pipeline_config = PipelineConfig.from_dict(conf_dict) if conf_dict else PipelineConfig()

        upload_name = sanitize_filename(file.filename or "video.mp4", fallback="video.mp4")
        base_name = os.path.splitext(upload_name)[0]
        final_project_id = (
            sanitize_project_id(project_id)
            if project_id and project_id.strip()
            else sanitize_project_id(base_name)
        )

        temp_dir = store.root / "_uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / upload_name

        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        project = store.create_project(
            input_video=str(temp_path),
            config=pipeline_config,
            project_id=final_project_id,
        )
        store.attach_input_video(project, temp_path)
        return project_payload(project)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Неожиданная ошибка при загрузке файла")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("")
def list_projects(store: ProjectStore = Depends(get_store)):
    """Вернуть список проектов из рабочего корня."""

    try:
        return {
            "projects": [
                project_payload(project, include_segments=False)
                for project in store.list_projects()
            ]
        }
    except Exception:
        logger.exception("Неожиданная ошибка при получении списка проектов")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/{project_id}")
def get_project_status(project_id: str, store: ProjectStore = Depends(get_store)):
    """Получить статус и данные проекта."""
    try:
        safe_project_id = sanitize_project_id(project_id)
        project = store.load_project(store.root / safe_project_id)
        return project_payload(project)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/artifacts")
def get_project_artifacts(project_id: str, store: ProjectStore = Depends(get_store)):
    """Получить список артефактов проекта."""
    try:
        safe_project_id = sanitize_project_id(project_id)
        project = store.load_project(store.root / safe_project_id)
        return {
            "project_id": project.id,
            "work_dir": project.work_dir.as_posix(),
            "artifacts": [record.to_dict() for record in project.artifact_records],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/artifacts/{kind}")
def download_project_artifact(
    project_id: str,
    kind: str,
    store: ProjectStore = Depends(get_store),
):
    """Скачать последний артефакт указанного типа."""

    try:
        safe_project_id = sanitize_project_id(project_id)
        artifact_kind = ArtifactKind(kind)
        project = store.load_project(store.root / safe_project_id)
        record = store.get_artifact(project, artifact_kind)
        if record is None:
            raise HTTPException(status_code=404, detail="Artifact not found")

        artifact_path = store.resolve_project_file(project, record.path)
        if not artifact_path.is_file():
            raise HTTPException(status_code=404, detail="Artifact file not found")

        return FileResponse(
            artifact_path,
            media_type=record.content_type,
            filename=artifact_path.name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.put("/{project_id}/segments")
def save_project_segments(
    project_id: str,
    req: SaveSegmentsRequest,
    store: ProjectStore = Depends(get_store),
):
    """Сохранить отредактированные сегменты проекта."""

    try:
        safe_project_id = sanitize_project_id(project_id)
        project = store.load_project(store.root / safe_project_id)
        segments = [Segment.from_dict(item) for item in req.segments]
        store.save_segments(project, segments, translated=req.translated)
        restored = store.load_project(project.work_dir)
        return project_payload(restored)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


class PatchConfigRequest(BaseModel):
    """Схема запроса на обновление конфигурации пайплайна."""

    config: dict[str, Any]


@router.put("/{project_id}/config")
def patch_project_config(
    project_id: str,
    req: PatchConfigRequest,
    store: ProjectStore = Depends(get_store),
):
    """Обновить настройки пайплайна проекта (translation_style, voice_strategy и др.)."""

    try:
        safe_project_id = sanitize_project_id(project_id)
        project = store.load_project(store.root / safe_project_id)
        # Сливаем текущую конфигурацию с присланными полями
        current = project.config.to_dict()
        current.update(req.config)
        new_config = PipelineConfig.from_dict(current)
        project.config = new_config
        store.save_project(project)
        return {"ok": True, "config": new_config.to_dict()}
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception:
        logger.exception("Неожиданная ошибка при обновлении конфигурации")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
