"""Инициализация FastAPI приложения."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from translate_video import __version__
from translate_video.api.middleware.auth import APIKeyMiddleware
from translate_video.api.routes import pipeline, preflight, projects, providers, video
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

app.include_router(projects.router)
app.include_router(pipeline.router)
app.include_router(pipeline.tts_router)
app.include_router(preflight.router)
app.include_router(providers.router)
app.include_router(video.router)


@app.get("/api/health")
def health_check():
    """Проверка доступности сервиса."""
    return {"status": "ok", "version": __version__}


# Задел для будущей интеграции фронтенда (Статика из React Vite)
ui_dist = Path(__file__).parent.parent.parent.parent / "ui" / "dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
