"""ADR-001 Фаза 2: Роутер сегментов, конфигурации, dev-лога и статистики.

Вынесено из projects.py (2753 строки) для снижения когнитивной нагрузки.
Endpoints:
  PUT  /{project_id}/segments  — сохранить сегменты
  PUT  /{project_id}/config    — обновить конфигурацию пайплайна
  GET  /{project_id}/devlog    — читать dev-лог
  GET  /{project_id}/stats     — статистика проекта
"""

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import Segment
from translate_video.core.store import ProjectStore, sanitize_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["segments"])


def get_store() -> ProjectStore:
    """Зависимость для получения хранилища проектов."""
    work_root = Path(os.getenv("WORK_ROOT", "runs")).resolve()
    return ProjectStore(work_root)


def _project_payload_light(project) -> dict:
    """Минимальный payload проекта для ответов segments endpoint."""
    from translate_video.api.routes.projects import project_payload
    return project_payload(project)


# ── Schemas ───────────────────────────────────────────────────────────────────

class SaveSegmentsRequest(BaseModel):
    """Схема запроса на сохранение сегментов."""
    segments: list[dict]
    translated: bool = True


class PatchConfigRequest(BaseModel):
    """Схема запроса на обновление конфигурации пайплайна."""
    config: dict[str, Any]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.put("/{project_id}/segments", tags=["segments"])
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
        return _project_payload_light(restored)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.put("/{project_id}/config", tags=["segments"])
def patch_project_config(
    project_id: str,
    req: PatchConfigRequest,
    store: ProjectStore = Depends(get_store),
):
    """Обновить настройки пайплайна проекта (translation_style, voice_strategy и др.)."""
    try:
        safe_project_id = sanitize_project_id(project_id)
        project = store.load_project(store.root / safe_project_id)
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


@router.get("/{project_id}/devlog", tags=["segments"])
def get_project_devlog(
    project_id: str,
    limit: int = 500,
    offset: int = 0,
    stage: str | None = None,
    event_type: str | None = None,
    store: ProjectStore = Depends(get_store),
):
    """Вернуть события dev-лога проекта с опциональной фильтрацией."""
    try:
        safe_project_id = sanitize_project_id(project_id)
        project = store.load_project(store.root / safe_project_id)
        from translate_video.core.devlog import DevLogWriter
        writer = DevLogWriter(project.work_dir, enabled=False)
        writer._path = project.work_dir / "devlog.jsonl"
        writer._enabled = True
        events = writer.read_events(
            limit=limit,
            offset=offset,
            stage=stage or None,
            event_type=event_type or None,
        )
        return {
            "project_id": safe_project_id,
            "dev_mode": getattr(project.config, "dev_mode", False),
            "size_bytes": writer.size_bytes(),
            "event_count": len(events),
            "offset": offset,
            "events": events,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception:
        logger.exception("Ошибка при чтении dev log")
        raise HTTPException(status_code=500, detail="Ошибка чтения dev log")


@router.get("/{project_id}/stats", tags=["segments"])
def get_project_stats(
    project_id: str,
    store: ProjectStore = Depends(get_store),
):
    """Вернуть полную статистику проекта."""
    try:
        safe_project_id = sanitize_project_id(project_id)
        project = store.load_project(store.root / safe_project_id)
        from translate_video.core.stats import compute_project_stats
        return compute_project_stats(project)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception:
        logger.exception("Ошибка при вычислении статистики")
        raise HTTPException(status_code=500, detail="Ошибка вычисления статистики")
