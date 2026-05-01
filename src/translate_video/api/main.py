"""Инициализация FastAPI приложения."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from translate_video import __version__
from translate_video.api.routes import pipeline, preflight, projects


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
    work_root = Path(os.getenv("WORK_ROOT", "runs"))
    work_root.mkdir(parents=True, exist_ok=True)
    application.mount("/runs", StaticFiles(directory=str(work_root)), name="runs")
    yield


app = FastAPI(
    title="AI Video Translator API",
    description="API для ИИ-перевода видео и управления проектами.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(pipeline.router)
app.include_router(preflight.router)


@app.get("/api/health")
def health_check():
    """Проверка доступности сервиса."""
    return {"status": "ok", "version": __version__}


# Задел для будущей интеграции фронтенда (Статика из React Vite)
ui_dist = Path(__file__).parent.parent.parent.parent / "ui" / "dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
