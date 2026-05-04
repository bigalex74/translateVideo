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
    # C-11: валидация размера файла с понятным сообщением
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_UPLOAD_MB", "2048"))  # 2 ГБ по умолчанию
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    try:
        file.file.seek(0, 2)          # перемотать в конец
        file_size = file.file.tell()  # позиция = размер
        file.file.seek(0)             # вернуть в начало
        if file_size > MAX_FILE_SIZE_BYTES:
            size_gb = file_size / 1024 / 1024 / 1024
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Файл слишком большой: {size_gb:.1f} ГБ. "
                    f"Максимально допустимый размер: {MAX_FILE_SIZE_MB} МБ ({MAX_FILE_SIZE_MB // 1024} ГБ). "
                    "Пожалуйста, сожмите видео или разбейте на части."
                ),
            )
    except HTTPException:
        raise
    except Exception:
        pass  # если не удалось проверить — не блокируем
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


# ── Dev Log ───────────────────────────────────────────────────────────────────

@router.get("/{project_id}/devlog")
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


# ── Statistics ────────────────────────────────────────────────────────────────

@router.get("/{project_id}/stats")
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


# ── AI Log Analysis ───────────────────────────────────────────────────────────

class AnalyzeLogRequest(BaseModel):
    """Режим AI-анализа dev-лога."""
    mode: str = "errors"  # errors | quality | performance | improvements | anomalies | full


_ANALYSIS_PROMPTS = {
    "errors": (
        "Проанализируй этот dev-лог пайплайна перевода видео. "
        "Найди все ошибки, сбои провайдеров, таймауты, отказы fallback. "
        "Перечисли их с указанием времени, провайдера и возможной причины."
    ),
    "quality": (
        "Проанализируй промты и ответы моделей в этом dev-логе. "
        "Оцени качество переводов по текстам промтов и ответов. "
        "Найди сегменты с подозрительными или некачественными переводами."
    ),
    "performance": (
        "Проанализируй времена выполнения (elapsed_s) в этом dev-логе. "
        "Определи узкие места: самые медленные провайдеры, этапы, сегменты. "
        "Дай рекомендации по ускорению."
    ),
    "improvements": (
        "Изучи промты в dev-логе и предложи конкретные улучшения. "
        "Что можно добавить/убрать из промтов? Какие параметры изменить? "
        "Какие паттерны ошибок указывают на системные проблемы?"
    ),
    "anomalies": (
        "Найди аномалии в dev-логе: необычно долгие ответы, "
        "подозрительно короткие переводы, многократные fallback-ы для одного сегмента, "
        "большие расхождения между входным и выходным текстами."
    ),
    "full": (
        "Сделай полный анализ dev-лога пайплайна перевода. "
        "Структурируй отчёт по разделам: Ошибки, Качество переводов, "
        "Производительность, Аномалии, Рекомендации по улучшению."
    ),
}


@router.post("/{project_id}/analyze-log")
def analyze_project_log(
    project_id: str,
    req: AnalyzeLogRequest,
    store: ProjectStore = Depends(get_store),
):
    """Проанализировать dev-лог проекта с помощью LLM."""
    try:
        safe_project_id = sanitize_project_id(project_id)
        project = store.load_project(store.root / safe_project_id)

        from translate_video.core.devlog import DevLogWriter
        writer = DevLogWriter(project.work_dir, enabled=False)
        writer._path = project.work_dir / "devlog.jsonl"
        writer._enabled = True
        if not writer.path().exists():
            raise HTTPException(
                status_code=404,
                detail="Dev log not found. Enable dev_mode and run the pipeline first.",
            )

        # Читаем последние 200 событий для анализа (контекстный лимит)
        events = writer.read_events(limit=200)
        if not events:
            return {"analysis": "Dev log пуст.", "model_used": "none", "mode": req.mode}

        # Формируем компактный лог для LLM
        log_lines: list[str] = []
        for evt in events:
            ts = evt.get("ts", "")
            event = evt.get("event", "?")
            stage = evt.get("stage", "")
            # Включаем ключевые поля, исключаем длинные промты (кратко)
            summary_fields = {
                k: v for k, v in evt.items()
                if k not in ("ts", "event", "stage", "prompt", "response")
                and not isinstance(v, str)
                or (k in ("prompt", "response") and isinstance(v, str) and len(v) < 200)
            }
            log_lines.append(f"[{ts}] {event} stage={stage} {json.dumps(summary_fields, ensure_ascii=False)[:300]}")

        log_text = "\n".join(log_lines)
        system_prompt = _ANALYSIS_PROMPTS.get(req.mode, _ANALYSIS_PROMPTS["full"])
        full_prompt = (
            f"{system_prompt}\n\n"
            f"=== DEV LOG (последние {len(events)} событий) ===\n"
            f"{log_text}\n\n"
            f"Ответ структурируй с заголовками и маркерами. Используй русский язык."
        )

        # Выбираем провайдер для анализа (Gemini bridge или rewriter-провайдер)
        analysis_text, model_used = _call_analysis_llm(full_prompt, project.config)
        return {
            "mode": req.mode,
            "events_analyzed": len(events),
            "model_used": model_used,
            "analysis": analysis_text,
        }
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    except Exception as exc:
        logger.exception("Ошибка при AI-анализе лога")
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {exc}")


def _call_analysis_llm(prompt: str, config: PipelineConfig) -> tuple[str, str]:
    """Вызвать LLM для анализа лога. Возвращает (текст, имя_модели)."""
    import os, urllib.request, json as _json

    # Приоритет: Gemini bridge → Polza → NeuroAPI → ошибка
    bridge_url = os.getenv("GEMINI_BRIDGE_URL")
    if bridge_url:
        # OpenAI-compatible bridge
        model = os.getenv("GEMINI_REWRITE_MODEL", "gemini-2.5-flash")
        api_key = os.getenv("GEMINI_API_KEY", "bridge")
        base_url = bridge_url.rstrip("/")
        provider_name = f"gemini-bridge/{model}"
    else:
        polza_key = os.getenv("POLZA_API_KEY")
        neuro_key = os.getenv("NEUROAPI_API_KEY")
        if polza_key:
            api_key = polza_key
            base_url = os.getenv("POLZA_BASE_URL", "https://api.polza.ai/api/v1")
            model = os.getenv("POLZA_REWRITE_MODEL", "google/gemini-2.5-flash-lite-preview-09-2025")
            provider_name = f"polza/{model}"
        elif neuro_key:
            api_key = neuro_key
            base_url = os.getenv("NEUROAPI_BASE_URL", "https://neuroapi.host/v1")
            model = os.getenv("NEUROAPI_REWRITE_MODEL", "gpt-5-mini")
            provider_name = f"neuroapi/{model}"
        else:
            return "Нет доступного LLM-провайдера для анализа. Настройте GEMINI_BRIDGE_URL, POLZA_API_KEY или NEUROAPI_API_KEY.", "none"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2048,
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=_json.dumps(payload, ensure_ascii=False).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    proxy_url = os.getenv("REWRITER_PROXY")
    if proxy_url:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
        open_fn = opener.open
    else:
        open_fn = urllib.request.urlopen
    try:
        with open_fn(req, timeout=60) as resp:
            data = _json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"], provider_name
    except Exception as exc:
        return f"Ошибка вызова LLM: {exc}", provider_name
