"""Инициализация FastAPI приложения."""

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

_START_TIME = time.time()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from translate_video import __version__
from translate_video.api.middleware.auth import APIKeyMiddleware
from translate_video.api.routes import admin, metrics, pipeline, preflight, projects, providers, video
from translate_video.core.env import load_env_file
from translate_video.core.log import configure_from_env, get_logger

# Загружаем .env и настраиваем логирование как можно раньше
load_env_file()
configure_from_env()
_log = get_logger(__name__)


def _get_allowed_origins() -> list[str]:
    """Читать разрешённые CORS-origins из переменной окружения.

    По умолчанию разрешены только локальные dev-адреса.
    Установите ``ALLOWED_ORIGINS=*`` для открытого доступа (только локально).
    """
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:8000")
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Инициализировать ресурсы приложения при старте."""
    work_root = Path(os.getenv("WORK_ROOT", "runs")).resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    application.mount("/runs", StaticFiles(directory=str(work_root)), name="runs")
    _log.info("server.start", version=__version__, work_root=str(work_root))

    # ── Cleanup zombie pipelines ──────────────────────────────────────────────
    # При рестарте контейнера все in-memory _running_projects сбрасываются,
    # но статус в FS остаётся 'running'. Сбрасываем такие проекты в 'failed'.
    from translate_video.core.schemas import ProjectStatus
    from translate_video.core.store import ProjectStore
    store = ProjectStore(work_root)
    zombies = 0
    try:
        for project in store.list_projects():
            if project.status == ProjectStatus.RUNNING:
                project.status = ProjectStatus.FAILED
                store.save_project(project)
                zombies += 1
                _log.warning(
                    "server.zombie_cleanup",
                    project=project.id,
                    reason="running_on_startup",
                )
    except Exception as exc:
        _log.error("server.zombie_cleanup_error", error=str(exc)[:200])
    if zombies:
        _log.info("server.zombie_cleanup_done", count=zombies)

    yield
    _log.info("server.stop")


app = FastAPI(
    title="AI Video Translator API",
    description=(
        "REST API для ИИ-перевода видео.\n\n"
        "**Авторизация**: если переменная `API_KEY` задана, все запросы "
        "к `/api/*` требуют заголовок `X-API-Key: <ключ>`.\n\n"
        "Для локального использования `API_KEY` можно не задавать."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(APIKeyMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers (OWASP hardening — предложение Security агента)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Добавить OWASP-рекомендованные security headers к каждому ответу."""
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(projects.router)
app.include_router(pipeline.router)
app.include_router(pipeline.tts_router)
app.include_router(preflight.router)
app.include_router(providers.router)
app.include_router(video.router)
app.include_router(admin.router)
app.include_router(metrics.router)

@app.get("/api/health")
def health_check():
    """Расширенный health-check: статус, версия, uptime, метрики."""
    from translate_video.api.routes.pipeline import _running_projects

    uptime_s = int(time.time() - _START_TIME)
    uptime_human = f"{uptime_s // 3600}h {(uptime_s % 3600) // 60}m {uptime_s % 60}s"

    # Память процесса (опционально — только если psutil доступен)
    memory_mb: float | None = None
    try:
        import psutil, os as _os
        proc = psutil.Process(_os.getpid())
        memory_mb = round(proc.memory_info().rss / 1024 / 1024, 1)
    except ImportError:
        pass

    payload: dict = {
        "status": "ok",
        "version": __version__,
        "uptime_seconds": uptime_s,
        "uptime": uptime_human,
        "running_projects": len(_running_projects),
        # Nm2-12: retry config параметры
        "retry_config": {
            "max_attempts": int(os.getenv("TTS_RETRY_ATTEMPTS", "3")),
            "base_delay_s": float(os.getenv("TTS_RETRY_BASE_DELAY", "1.0")),
            "max_delay_s": float(os.getenv("TTS_RETRY_MAX_DELAY", "30.0")),
            "backoff_factor": float(os.getenv("TTS_RETRY_BACKOFF", "2.0")),
        },
        # auth статус (enabled/disabled)
        "auth_enabled": bool(os.getenv("API_KEY") or os.getenv("API_KEYS")),
    }
    if memory_mb is not None:
        payload["memory_mb"] = memory_mb

    # NM3-08: disk usage для runs/
    try:
        work_root = Path(os.getenv("WORK_ROOT", "runs")).resolve()
        if work_root.exists():
            total_bytes = sum(
                f.stat().st_size
                for f in work_root.rglob("*")
                if f.is_file()
            )
            payload["disk_usage_mb"] = round(total_bytes / 1024 / 1024, 1)
            payload["disk_work_root"] = str(work_root)
    except Exception:  # noqa: BLE001
        pass

    return payload


# Задел для будущей интеграции фронтенда (Статика из React Vite)
ui_dist = Path(__file__).parent.parent.parent.parent / "ui" / "dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
