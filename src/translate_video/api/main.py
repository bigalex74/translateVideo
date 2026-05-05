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


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Добавить X-Trace-ID к каждому ответу (Z5.7).

    Если клиент прислал X-Request-ID — отражаем его.
    Иначе — генерируем новый UUID4.
    Используется для корреляции логов с запросами.
    """
    async def dispatch(self, request: StarletteRequest, call_next):
        import uuid as _uuid  # noqa: PLC0415
        trace_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Trace-ID")
            or _uuid.uuid4().hex
        )
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response


app.add_middleware(TraceIDMiddleware)

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

    # Память и CPU процесса (опционально — только если psutil доступен)
    memory_mb: float | None = None
    cpu_percent: float | None = None
    cpu_count: int | None = None
    try:
        import psutil, os as _os  # noqa: E401
        proc = psutil.Process(_os.getpid())
        memory_mb = round(proc.memory_info().rss / 1024 / 1024, 1)
        # Z5.12: CPU метрики
        cpu_percent = round(psutil.cpu_percent(interval=0.1), 1)
        cpu_count = psutil.cpu_count(logical=True)
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
        # Z5.1: ссылки на API документацию
        "docs": {"swagger": "/docs", "redoc": "/redoc", "openapi_json": "/openapi.json"},
    }
    if memory_mb is not None:
        payload["memory_mb"] = memory_mb
    if cpu_percent is not None:
        payload["cpu_percent"] = cpu_percent
    if cpu_count is not None:
        payload["cpu_count"] = cpu_count

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


@app.get("/api/version", summary="В10: Версия приложения (быстрый endpoint)")
def api_version():
    """В10: Возвращает только версию и статус.

    Более лёгкий аналог /api/health — только версия.
    Полезен для CI/CD и внешних мониторингов.
    """
    return {
        "version": __version__,
        "status": "ok",
        "app": "AI Video Translator",
    }


@app.get("/api/health/providers")
async def health_providers():
    """S6: Проверить доступность внешних провайдеров (TTS, перевод).

    Возвращает статус каждого провайдера: ok | unreachable | not_configured.
    Не раскрывает API-ключи, только состояние доступности.
    """
    import asyncio  # noqa: PLC0415
    import httpx     # noqa: PLC0415

    providers_status: dict[str, str] = {}

    # Проверка OpenAI TTS
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get("https://api.openai.com/v1/models",
                                     headers={"Authorization": f"Bearer {openai_key}"})
                providers_status["openai"] = "ok" if r.status_code in (200, 401) else "unreachable"
        except Exception:
            providers_status["openai"] = "unreachable"
    else:
        providers_status["openai"] = "not_configured"

    # Проверка Yandex SpeechKit
    yandex_key = os.getenv("YANDEX_API_KEY") or os.getenv("YANDEX_SPEECHKIT_KEY")
    providers_status["yandex"] = "not_configured" if not yandex_key else "configured"

    # Проверка Polza / NeuroAPI (через переменную)
    polza_key = os.getenv("POLZA_API_KEY") or os.getenv("NEUROAPI_KEY")
    providers_status["polza"] = "not_configured" if not polza_key else "configured"

    all_ok = all(v in ("ok", "configured", "not_configured") for v in providers_status.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "providers": providers_status,
        "auth_enabled": bool(os.getenv("API_KEY") or os.getenv("API_KEYS")),
    }


# Задел для будущей интеграции фронтенда (Статика из React Vite)
ui_dist = Path(__file__).parent.parent.parent.parent / "ui" / "dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
