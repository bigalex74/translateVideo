"""Маршруты для запуска пайплайна."""

import asyncio
import ipaddress
import socket
import threading
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel

from translate_video.api.routes.projects import get_store
from translate_video.api.webhooks import notify_webhook
from translate_video.core.log import Timer, get_logger
from translate_video.core.store import ProjectStore, sanitize_project_id
from translate_video.pipeline import build_stages, project_summary
from translate_video.pipeline.context import StageContext
from translate_video.pipeline.runner import PipelineCancelledError, PipelineRunner

_log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["pipeline"])
tts_router = APIRouter(prefix="/api/v1/tts", tags=["tts"])

# Глобальный in-memory реестр запущенных проектов (защита от race condition)
_running_lock = threading.Lock()
_running_projects: set[str] = set()
# Реестр cancel-токенов: project_id → threading.Event
_cancel_tokens: dict[str, threading.Event] = {}

_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}


def _is_forbidden_webhook_address(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Вернуть True для адресов, опасных для webhook-запросов наружу."""

    return any(
        (
            addr.is_private,
            addr.is_loopback,
            addr.is_link_local,
            addr.is_reserved,
            addr.is_multicast,
            addr.is_unspecified,
        )
    )


def _resolve_webhook_addresses(hostname: str, port: int | None) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Разрешить hostname в IP-адреса для SSRF-проверки."""

    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=400,
            detail="X-Webhook-Url: hostname не удалось проверить",
        ) from exc

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for record in records:
        raw_host = record[4][0]
        try:
            addresses.append(ipaddress.ip_address(raw_host))
        except ValueError:
            continue
    return addresses


def _validate_webhook_url(url: str | None) -> None:
    """Проверить webhook URL на SSRF-безопасность.

    Разрешены только http/https URL, не указывающие на внутренние IP.
    """
    if not url:
        return
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="X-Webhook-Url: только http/https схемы")
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise HTTPException(status_code=400, detail="X-Webhook-Url: hostname обязателен")
    if hostname in _BLOCKED_HOSTNAMES or hostname.endswith(".localhost"):
        raise HTTPException(status_code=400, detail="X-Webhook-Url: локальные hostname запрещены")

    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        addresses = _resolve_webhook_addresses(hostname, parsed.port)

    if not addresses:
        raise HTTPException(status_code=400, detail="X-Webhook-Url: hostname не удалось проверить")
    if any(_is_forbidden_webhook_address(addr) for addr in addresses):
        raise HTTPException(status_code=400, detail="X-Webhook-Url: внутренние IP-адреса запрещены")



class RunPipelineRequest(BaseModel):
    """Схема запроса на запуск пайплайна."""
    force: bool = False
    provider: str = "legacy"
    from_stage: str | None = None  # если задан — сбросить этот и последующие этапы, начать с него


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
        runner = PipelineRunner(
            build_stages(req.provider, project_config=loaded_project.config),
            force=req.force,
            from_stage=req.from_stage,
        )

        # Создаём cancel-токен для этого запуска
        cancel_event = threading.Event()
        with _running_lock:
            _cancel_tokens[safe_project_id] = cancel_event

        # Режим разработчика: создаём DevLogWriter если включён в конфиге
        from translate_video.core.devlog import DevLogWriter
        dev_log = DevLogWriter.from_config(loaded_project.config, loaded_project.work_dir)
        if dev_log.exists() or getattr(loaded_project.config, "dev_mode", False):
            # Подключаем DevLog ко всем провайдерам через with_dev_log()
            for pipeline_stage in runner.stages:
                translator = getattr(pipeline_stage, "translator", None)
                if hasattr(translator, "with_dev_log"):
                    translator.with_dev_log(dev_log)
                timing_fitter = getattr(pipeline_stage, "timing_fitter", None)
                if hasattr(timing_fitter, "with_dev_log"):
                    timing_fitter.with_dev_log(dev_log)
                # NaturalVoiceTimingFitter создаёт rewriter лениво — передаём туда
                rewriter = getattr(timing_fitter, "_rewriter", None)
                if hasattr(rewriter, "with_dev_log"):
                    rewriter.with_dev_log(dev_log)

        _log.info(
            "api.pipeline_run",
            project=safe_project_id,
            provider=req.provider,
            force=req.force,
            dev_mode=getattr(loaded_project.config, "dev_mode", False),
        )

        # Запускаем блокирующий пайплайн в отдельном потоке,
        # чтобы не блокировать asyncio event loop
        ctx = StageContext(
            project=loaded_project,
            store=store,
            cancel_event=cancel_event,
        )
        with Timer() as t:
            await asyncio.to_thread(runner.run, ctx)

        restored = store.load_project(loaded_project.work_dir)
        _log.info(
            "api.pipeline_done",
            project=safe_project_id,
            status=restored.status.value,
            total_elapsed_s=t.elapsed,
        )

        if webhook_url:
            summary = project_summary(restored)
            await notify_webhook(webhook_url, summary)

    except PipelineCancelledError:
        # Обновляем статус проекта до FAILED (cancelled) и сохраняем
        try:
            cancelled_project = store.load_project(store.root / safe_project_id)
            from translate_video.core.schemas import ProjectStatus
            cancelled_project.status = ProjectStatus.FAILED
            store.save_project(cancelled_project)
        except Exception:
            pass
        _log.info(
            "api.pipeline_cancelled",
            project=safe_project_id,
            elapsed_s=round(t.elapsed, 2),
        )
        if webhook_url:
            await notify_webhook(
                webhook_url,
                {"project_id": safe_project_id, "status": "cancelled"},
            )
    except Exception as e:
        _log.error("api.pipeline_error", project=project_id, error=str(e)[:200])
        if webhook_url:
            await notify_webhook(
                webhook_url, {"project_id": project_id, "status": "failed", "error": str(e)}
            )
    finally:
        with _running_lock:
            _running_projects.discard(safe_project_id)
            _cancel_tokens.pop(safe_project_id, None)


@router.post("/{project_id}/cancel")
def cancel_pipeline(
    project_id: str,
    store: ProjectStore = Depends(get_store),
):
    """Запросить отмену запущенного пайплайна.

    **Нормальный режим**: устанавливает cancel-флаг — пайплайн завершится после текущего этапа.
    **Zombie-режим**: если пайплайн не зарегистрирован (рестарт контейнера), но проект
    имеет статус 'running' в FS — принудительно сбрасывает статус в 'failed'.
    Возвращает 404 если проект не запущен и статус не 'running'.
    """
    from translate_video.core.schemas import ProjectStatus
    safe_project_id = sanitize_project_id(project_id)

    with _running_lock:
        in_registry = safe_project_id in _running_projects
        event = _cancel_tokens.get(safe_project_id) if in_registry else None

    if in_registry:
        # Нормальный случай — пайплайн активен в этом процессе
        if event:
            event.set()
        _log.info("api.pipeline_cancel_requested", project=safe_project_id, mode="normal")
        return {"status": "cancelling", "project_id": safe_project_id, "zombie": False}

    # Zombie-режим — проверяем статус в FS
    try:
        project = store.load_project(store.root / safe_project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Проект '{safe_project_id}' не найден")

    if project.status != ProjectStatus.RUNNING:
        raise HTTPException(
            status_code=404,
            detail=f"Проект '{safe_project_id}' не запущен (статус: {project.status.value})",
        )

    # Принудительно сбрасываем zombie-статус
    project.status = ProjectStatus.FAILED
    store.save_project(project)
    _log.warning(
        "api.pipeline_zombie_cancel",
        project=safe_project_id,
        reason="not_in_registry_but_running_in_fs",
    )
    return {"status": "cancelled", "project_id": safe_project_id, "zombie": True}


@router.get("/{project_id}/running")
def is_pipeline_running(
    project_id: str,
) -> dict:
    """Проверить, запущен ли пайплайн для данного проекта."""
    safe_project_id = sanitize_project_id(project_id)
    with _running_lock:
        running = safe_project_id in _running_projects
    return {"project_id": safe_project_id, "running": running}


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


# ── TTS endpoints ─────────────────────────────────────────────────────────────

@tts_router.get("/voices")
def get_tts_voices(provider: str = "openai"):
    """Вернуть список доступных TTS-голосов.

    ?provider=openai  → голоса OpenAI-совместимых провайдеров (polza/neuroapi)
    ?provider=yandex  → голоса Yandex SpeechKit с ролями
    """
    if provider == "yandex":
        from translate_video.tts import SPEECHKIT_VOICES
        return {"voices": SPEECHKIT_VOICES, "provider": "yandex"}
    from translate_video.tts import TTS_VOICES
    return {"voices": TTS_VOICES, "provider": "openai"}


@tts_router.get("/models")
def get_tts_models(provider: str = "openai"):
    """Вернуть список доступных TTS-моделей."""
    if provider == "yandex":
        return {
            "models": [
                {"id": "general", "name": "General", "note": "Стандартная модель SpeechKit"},
            ],
            "provider": "yandex",
        }
    return {
        "models": [
            {"id": "tts-1",           "name": "TTS-1",           "note": "Быстрая, стандартное качество"},
            {"id": "tts-1-hd",        "name": "TTS-1 HD",        "note": "Улучшенное качество, медленнее"},
            {"id": "gpt-4o-mini-tts", "name": "GPT-4o Mini TTS", "note": "Высокое качество, поддержка инструкций"},
        ],
        "provider": "openai",
    }
