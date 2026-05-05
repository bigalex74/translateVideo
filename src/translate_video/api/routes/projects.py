"""Маршруты для работы с проектами."""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Body
from fastapi import Path as FastAPIPath
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from translate_video.cli import _project_summary
from translate_video.core.config import PipelineConfig
from translate_video.core.schemas import ArtifactKind, Segment, SegmentStatus, VideoProject
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


# ─── Z5.5/Z1.3/Z3.1: Прогресс и ETA ──────────────────────────────────────────

# Веса этапов (относительное время выполнения).
# Если этап пропущен или нет данных — используем 1.
_STAGE_WEIGHTS: dict[str, float] = {
    "extract_audio": 0.05,
    "transcribe": 0.30,
    "translate": 0.20,
    "tts": 0.35,
    "merge": 0.10,
}
_TOTAL_WEIGHT: float = sum(_STAGE_WEIGHTS.values())


def _compute_progress(project: "VideoProject") -> dict[str, Any]:
    """Вычислить progress_percent и eta_seconds из stage_runs.

    Алгоритм:
    - Суммируем веса завершённых этапов → базовый прогресс
    - Для running этапа — интерполируем по elapsed времени vs avg времени предыдущих запусков
    - ETA = оставшийся вес / средний вес в секунду
    """
    import time as _time  # noqa: PLC0415
    from translate_video.core.schemas import JobStatus  # noqa: PLC0415

    stage_runs = project.stage_runs

    completed_weight = 0.0
    running_elapsed = 0.0
    running_weight = 0.0
    started_at: float | None = None

    for run in stage_runs:
        stage_key = run.stage.value if hasattr(run.stage, "value") else str(run.stage)
        weight = _STAGE_WEIGHTS.get(stage_key, 1.0 / max(len(_STAGE_WEIGHTS), 1))

        if run.status == JobStatus.COMPLETED:
            completed_weight += weight
        elif run.status == JobStatus.RUNNING:
            running_weight = weight
            # Пробуем получить время старта из run.started_at если есть
            if hasattr(run, "started_at") and run.started_at:
                try:
                    import datetime as _dt  # noqa: PLC0415
                    if isinstance(run.started_at, str):
                        started_at = _dt.datetime.fromisoformat(run.started_at).timestamp()
                    else:
                        started_at = float(run.started_at)
                    running_elapsed = max(0.0, _time.time() - started_at)
                except Exception:  # noqa: BLE001
                    running_elapsed = 0.0

    # Базовый прогресс из завершённых + частичный вклад текущего этапа
    partial = min(0.5, running_elapsed / 120.0) * running_weight  # 50% за 2 минуты
    progress_raw = (completed_weight + partial) / _TOTAL_WEIGHT
    progress_pct = round(min(99.0, max(0.0, progress_raw * 100.0)), 1)

    # ETA: оставшийся вес / скорость выполнения
    eta_seconds: float | None = None
    if project.status.value == "running" and completed_weight > 0:
        # Суммируем реальное время завершённых этапов
        total_elapsed = sum(
            getattr(run, "elapsed", 0.0) or 0.0
            for run in stage_runs
            if run.status == JobStatus.COMPLETED
        )
        if total_elapsed > 0:
            speed = completed_weight / total_elapsed  # weight per second
            remaining_weight = _TOTAL_WEIGHT - completed_weight - partial
            eta_seconds = round(max(0.0, remaining_weight / speed), 0)

    return {
        "progress_percent": progress_pct,
        "eta_seconds": eta_seconds,
    }


def project_payload(project: "VideoProject", include_segments: bool = True) -> dict[str, Any]:
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
    # Nm3-12: created_at из mtime work_dir/project.json
    try:
        from datetime import datetime, timezone  # noqa: PLC0415
        project_json = project.work_dir / "project.json"
        mtime = project_json.stat().st_mtime if project_json.exists() else project.work_dir.stat().st_mtime
        payload["created_at"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        payload["created_at"] = None
    # Z5.5/Z1.3: progress + ETA
    payload.update(_compute_progress(project))
    return payload


@router.post("")
def create_project(req: CreateProjectRequest, store: ProjectStore = Depends(get_store)):
    """Создать новый проект перевода по локальному пути или URL.

    Если input_video начинается с http:// или https://, файл автоматически
    скачивается через yt-dlp (поддерживает YouTube, Vimeo, VK и 1000+ сайтов).
    """
    config = PipelineConfig.from_dict(req.config) if req.config else PipelineConfig()
    try:
        project_id = sanitize_project_id(req.project_id) if req.project_id else None
        input_video = req.input_video

        # C-06 / backlog: URL-загрузка через yt-dlp
        if input_video.startswith(("http://", "https://")):
            input_video = _download_url_video(input_video, store.root)

        project = store.create_project(
            input_video=input_video,
            config=config,
            project_id=project_id,
        )
        input_path = Path(input_video)
        if input_path.is_file():
            store.attach_input_video(project, input_path)
        return project_payload(project)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Неожиданная ошибка при создании проекта")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


def _download_url_video(url: str, work_root: Path) -> str:
    """Скачать видео по URL через yt-dlp и вернуть локальный путь.

    Поддерживает YouTube, Vimeo, VK, Twitch и 1000+ сайтов.
    Таймаут: 10 мин. Максимум: 2 ГБ (MAX_UPLOAD_MB).
    """
    try:
        import yt_dlp  # noqa: PLC0415
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="yt-dlp не установлен. Добавьте в зависимости: pip install yt-dlp",
        ) from exc

    MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "2048"))
    download_dir = work_root / "_url_downloads"
    download_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": str(download_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_MB * 1024 * 1024,
        "socket_timeout": 30,
        "retries": 3,
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Получаем путь к скачанному файлу
            filename = ydl.prepare_filename(info)
            # yt-dlp может изменить расширение
            if not Path(filename).exists():
                filename = filename.rsplit(".", 1)[0] + ".mp4"
            if not Path(filename).exists():
                # Ищем последний скачанный файл
                files = sorted(download_dir.glob("*"), key=lambda p: p.stat().st_mtime)
                if files:
                    filename = str(files[-1])
                else:
                    raise HTTPException(status_code=422, detail="yt-dlp: не удалось найти скачанный файл")
        logger.info("url_download.done", url=url[:80], path=filename)
        return filename
    except HTTPException:
        raise
    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc)
        if "File is larger than max" in msg or "filesize" in msg.lower():
            raise HTTPException(status_code=413, detail=f"Видео слишком большое. Максимум: {MAX_MB} МБ")
        if "Private video" in msg or "Sign in" in msg or "unavailable" in msg:
            raise HTTPException(status_code=403, detail="Видео недоступно (приватное или заблокированное).")
        raise HTTPException(status_code=422, detail=f"Ошибка загрузки видео: {msg[:200]}")
    except Exception as exc:
        logger.exception("url_download.error", url=url[:80])
        raise HTTPException(status_code=500, detail=f"Не удалось скачать видео: {exc}") from exc


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
def list_projects(
    store: ProjectStore = Depends(get_store),
    page: int = 1,
    page_size: int = 50,
    archived: bool | None = None,
    tag: str | None = None,
):
    """Вернуть список проектов из рабочего корня (Z3.18 pagination, NC10-01 tag filter, NC10-02 archived filter)."""

    try:
        all_projects = list(store.list_projects())

        # Фильтр по archived
        if archived is not None:
            all_projects = [p for p in all_projects if p.archived == archived]
        else:
            # По умолчанию скрываем архивные
            all_projects = [p for p in all_projects if not p.archived]

        # Фильтр по тегу
        if tag:
            all_projects = [p for p in all_projects if tag in (p.tags or [])]

        total = len(all_projects)
        page = max(1, page)
        page_size = max(1, min(200, page_size))
        offset = (page - 1) * page_size
        paged = all_projects[offset: offset + page_size]

        return {
            "projects": [
                project_payload(project, include_segments=False)
                for project in paged
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": max(1, (total + page_size - 1) // page_size),
            },
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


@router.get(
    "/{project_id}/artifacts/audio",
    summary="Скачать аудиодорожку дубляжа (WAV/MP3) (Z2.6)",
)
def download_dubbed_audio(
    project_id: str = FastAPIPath(...),
    format: str = "wav",  # noqa: A002
    store: ProjectStore = Depends(get_store),
):
    """Вернуть смешанную аудиодорожку дубляжа для импорта в DaVinci Resolve / Premiere.

    Ищет файлы в порядке приоритета:
    1. artifacts/dubbed_audio.wav (после render/mix)
    2. artifacts/mixed_audio.wav
    3. Первый .wav из work_dir

    ?format=wav (default) или ?format=mp3 — конвертация через ffmpeg.
    """
    import subprocess  # noqa: PLC0415

    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    work_dir = project.work_dir

    # Ищем аудиофайл
    candidates = [
        work_dir / "artifacts" / "dubbed_audio.wav",
        work_dir / "artifacts" / "mixed_audio.wav",
        work_dir / "dubbed_audio.wav",
        work_dir / "mixed_audio.wav",
    ]
    # Ищем любой WAV в work_dir/artifacts
    artifacts_dir = work_dir / "artifacts"
    if artifacts_dir.is_dir():
        for wav in sorted(artifacts_dir.glob("*.wav")):
            candidates.append(wav)

    audio_file: Path | None = next((p for p in candidates if p.is_file()), None)

    if audio_file is None:
        raise HTTPException(
            status_code=404,
            detail="Аудиодорожка дубляжа ещё не создана. Запустите пайплайн до этапа 'render'.",
        )

    if format == "mp3":
        # Конвертируем в MP3 через ffmpeg
        mp3_path = audio_file.with_suffix(".exported.mp3")
        if not mp3_path.exists():
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(audio_file), "-b:a", "192k", str(mp3_path)],
                    capture_output=True, check=True, timeout=60,
                )
            except subprocess.CalledProcessError as e:
                raise HTTPException(status_code=500, detail=f"ffmpeg: {e.stderr.decode()[:200]}")
        return FileResponse(mp3_path, media_type="audio/mpeg", filename=f"{safe_id}_dubbed.mp3")

    return FileResponse(audio_file, media_type="audio/wav", filename=f"{safe_id}_dubbed.wav")


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


# ─── NC3-02: Clone project endpoint ──────────────────────────────────────────

class _CloneRequest(BaseModel):
    new_project_id: str | None = None
    copy_segments: bool = True


@router.post("/{project_id}/clone", summary="Дублировать проект (NC3-02)")
def clone_project(
    project_id: str = FastAPIPath(...),
    body: _CloneRequest = Body(default=_CloneRequest()),
    store: ProjectStore = Depends(get_store),
):
    """Создать клон проекта с теми же настройками и (опционально) сегментами.

    Статус сбрасывается в PENDING, stage_runs очищаются.
    """
    from translate_video.core.schemas import ProjectStatus  # lazy
    import uuid as _uuid

    safe_id = _safe_project_id(project_id)
    project = _get_project_or_404(store, safe_id)

    new_id = body.new_project_id or f"{safe_id}-clone-{_uuid.uuid4().hex[:6]}"
    new_id = _safe_project_id(new_id)

    new_dir = store.work_root / new_id
    if new_dir.exists():
        raise HTTPException(status_code=409, detail=f"Проект '{new_id}' уже существует.")

    # Создаём клон
    cloned = store.create_project(
        input_video=project.input_video,
        config=project.config,
        project_id=new_id,
    )
    # Копируем сегменты если нужно
    if body.copy_segments and project.segments:
        cloned.segments = list(project.segments)
    cloned.status = ProjectStatus.PENDING
    cloned.stage_runs = []
    store.save_project(cloned)

    return {
        "cloned_from": project_id,
        "project_id": cloned.id,
        "work_dir": str(cloned.work_dir),
        "status": cloned.status.value,
    }


# ─── NC4-01: ZIP Export endpoint ──────────────────────────────────────────────

@router.get("/{project_id}/export/zip", summary="Скачать все артефакты проекта ZIP (NC4-01)")
def export_project_zip(
    project_id: str,
    store: ProjectStore = Depends(get_store),
):
    """Создать ZIP архив всех артефактов проекта и вернуть для скачивания."""
    import io as _io, zipfile as _zip, shutil as _shutil  # noqa: PLC0415

    safe_id = _safe_project_id(project_id)
    project = _get_project_or_404(store, safe_id)

    buf = _io.BytesIO()
    with _zip.ZipFile(buf, mode="w", compression=_zip.ZIP_DEFLATED) as zf:
        # Добавляем все артефакты
        for record in project.artifact_records:
            art_path = Path(record.path) if not Path(record.path).is_absolute() \
                else Path(record.path)
            if art_path.exists():
                zf.write(art_path, arcname=art_path.name)
        # project.json
        pj = project.work_dir / "project.json"
        if pj.exists():
            zf.write(pj, arcname="project.json")
    buf.seek(0)

    from fastapi.responses import StreamingResponse  # noqa: PLC0415
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_id}.zip"',
        },
    )


# ─── Nm4-12: Stats endpoint ───────────────────────────────────────────────────

@router.get("/stats", summary="Агрегированная статистика по всем проектам (Nm4-12)")
def get_global_stats(store: ProjectStore = Depends(get_store)):
    """Вернуть сводную статистику по всем проектам в work_root."""
    from translate_video.core.schemas import ProjectStatus  # noqa: PLC0415
    projects = store.list_projects()
    by_status: dict[str, int] = {}
    for p in projects:
        key = p.status.value if hasattr(p.status, "value") else str(p.status)
        by_status[key] = by_status.get(key, 0) + 1

    total_segments = sum(len(p.segments) for p in projects)
    return {
        "total_projects": len(projects),
        "by_status": by_status,
        "total_segments": total_segments,
    }

# ─── Z5.8: stage-runs детальный эндпоинт ──────────────────────────────────

@router.get(
    "/{project_id}/stage-runs",
    summary="Детальная информация об этапах выполнения (Z5.8)",
)
def get_stage_runs(
    project_id: str = FastAPIPath(..., description="ID проекта"),
    store: ProjectStore = Depends(get_store),
):
    """Вернуть список stage_runs с деталями: duration, elapsed, cost_usd per stage.

    Используется для финансовой отчётности и мониторинга.
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Проект '{project_id}' не найден")

    runs = []
    for run in project.stage_runs:
        run_dict = run.to_dict()
        # Добавляем duration из metadata если есть
        metadata = run_dict.get("metadata") or {}
        cost_usd = metadata.get("cost_usd") or metadata.get("translation_cost_usd")
        run_dict["cost_usd"] = round(float(cost_usd), 6) if cost_usd is not None else None
        runs.append(run_dict)

    return {
        "project_id": project_id,
        "stage_runs": runs,
        "total_stages": len(runs),
        "completed_stages": sum(1 for r in runs if r.get("status") == "completed"),
        "total_elapsed_s": round(
            sum(r.get("elapsed", 0) or 0 for r in runs), 2
        ),
    }


# ─── Z5.9: retry from_stage API ───────────────────────────────────────────

class RetryFromStageRequest(BaseModel):
    """Запрос на повторный запуск с указанного этапа."""
    from_stage: str = "tts"
    force: bool = False


@router.post(
    "/{project_id}/retry",
    summary="Повторный запуск пайплайна с указанного этапа (Z5.9)",
)
def retry_from_stage(
    project_id: str = FastAPIPath(..., description="ID проекта"),
    body: RetryFromStageRequest = Body(default_factory=RetryFromStageRequest),
    store: ProjectStore = Depends(get_store),
):
    """Запустить пайплайн повторно начиная с ``from_stage``.

    Используется для автоматического retry в n8n и CI/CD.
    Эквивалентно POST /pipeline/{id}/run?from_stage=...
    """
    project = store.load_project(sanitize_project_id(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Проект '{project_id}' не найден")

    from translate_video.api.routes.pipeline import _running_projects  # noqa: PLC0415
    if project_id in _running_projects:
        raise HTTPException(status_code=409, detail="Проект уже выполняется")

    valid_stages = [
        "extract_audio", "transcribe", "regroup", "translate",
        "timing_fit", "tts", "render", "export",
    ]
    if body.from_stage not in valid_stages:
        raise HTTPException(
            status_code=422,
            detail=f"Неизвестный этап '{body.from_stage}'. Допустимые: {valid_stages}",
        )

    # Делегируем существующему роутеру пайплайна
    from translate_video.api.routes import pipeline as pipeline_module  # noqa: PLC0415
    # Формируем запрос через RunRequest
    from translate_video.api.routes.pipeline import RunRequest as _RunRequest  # noqa: PLC0415
    run_req = _RunRequest(
        from_stage=body.from_stage,
        force=body.force,
    )
    return pipeline_module.run_pipeline(
        project_id=project_id,
        req=run_req,
        store=store,
    )

# ─── Z3.10: Итоговое резюме качества ──────────────────────────────────────

@router.get(
    "/{project_id}/quality-report",
    summary="Итоговое резюме качества перевода (Z3.10)",
)
def get_quality_report(
    project_id: str = FastAPIPath(...),
    store: ProjectStore = Depends(get_store),
):
    """Вернуть human-readable резюме качества перевода проекта.

    Включает:
    - Оценку качества (A/B/C/D) на основе QA-флагов
    - Топ-проблемы с объяснением
    - Процент сегментов с проблемами
    - Рекомендации по улучшению
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    from translate_video.core.stats import compute_project_stats  # noqa: PLC0415

    stats = compute_project_stats(project)
    segs = project.segments or []
    quality = stats["quality"]
    seg_stats = stats["segments"]

    # Оценка качества
    issues_rate = (
        quality["segments_with_issues"] / len(segs)
        if segs else 0
    )
    critical_flags = {"translation_empty", "tts_invalid_slot", "timing_fit_invalid_slot"}
    critical_count = sum(
        quality["qa_flags_distribution"].get(f, 0)
        for f in critical_flags
    )

    if critical_count > 0 or issues_rate > 0.5:
        grade = "D"
        grade_label = "Требует серьёзной доработки"
    elif issues_rate > 0.3:
        grade = "C"
        grade_label = "Удовлетворительно"
    elif issues_rate > 0.1:
        grade = "B"
        grade_label = "Хорошо"
    else:
        grade = "A"
        grade_label = "Отлично"

    # Топ проблем
    FLAG_LABELS = {
        "translation_empty": "Пустые переводы",
        "timing_fit_failed": "Текст не помещается в тайминг",
        "render_audio_trimmed": "Аудио обрезано",
        "tts_overflow_after_rate": "TTS не помещается на макс. скорости",
        "translation_fallback_source": "Перевод = оригинал",
        "translation_rewritten_for_timing": "Перевод сокращён для тайминга",
        "tts_rate_adapted": "TTS ускорен",
    }
    top_problems = [
        {
            "flag": flag,
            "label": FLAG_LABELS.get(flag, flag),
            "count": count,
            "percent": round(count / len(segs) * 100, 1) if segs else 0,
        }
        for flag, count in sorted(
            quality["qa_flags_distribution"].items(),
            key=lambda x: -x[1],
        )
        if flag not in ("translation_provider_used", "translation_llm")
    ][:5]

    # Рекомендации
    recommendations = []
    if quality["qa_flags_distribution"].get("translation_empty", 0):
        recommendations.append("Проверьте сегменты с пустым переводом в редакторе.")
    if quality["qa_flags_distribution"].get("timing_fit_failed", 0):
        recommendations.append("Сократите переводы в длинных сегментах или включите ускорение аудио.")
    if quality["qa_flags_distribution"].get("render_audio_trimmed", 0) > 5:
        recommendations.append("Много обрезок аудио — попробуйте повысить скорость TTS или сократить текст.")
    if quality.get("google_fallback_count", 0) > 0:
        recommendations.append("Часть сегментов переведена через Google Translate — качество может быть ниже.")
    if not recommendations:
        recommendations.append("Перевод выполнен успешно. Рекомендуется проверка выборочных сегментов.")

    return {
        "project_id": project_id,
        "grade": grade,
        "grade_label": grade_label,
        "issues_rate": round(issues_rate, 3),
        "segments_total": len(segs),
        "segments_with_issues": quality["segments_with_issues"],
        "critical_count": critical_count,
        "top_problems": top_problems,
        "recommendations": recommendations,
        "avg_confidence": quality.get("avg_confidence"),
        "compression_ratio": seg_stats.get("compression_ratio"),
        "segments_rewritten": seg_stats.get("segments_rewritten", 0),
    }

# ─── Z2.3: Журнал действий проекта ────────────────────────────────────────

@router.get(
    "/{project_id}/activity",
    summary="Журнал действий с проектом (Z2.3)",
)
def get_project_activity(
    project_id: str = FastAPIPath(...),
    limit: int = 50,
    store: ProjectStore = Depends(get_store),
):
    """Вернуть хронологический журнал действий с проектом.

    Восстанавливает историю из stage_runs + billing_snapshots.
    Каждая запись: type (start/complete/fail/cancel), stage, timestamp, detail.
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    events = []

    for run in project.stage_runs:
        stage_str = run.stage.value if hasattr(run.stage, "value") else str(run.stage)
        status_str = run.status.value if hasattr(run.status, "value") else str(run.status)

        if run.started_at:
            events.append({
                "type": "stage_start",
                "stage": stage_str,
                "timestamp": run.started_at,
                "detail": f"Начало этапа {stage_str}",
                "attempt": run.attempt,
            })
        if run.finished_at:
            ev_type = (
                "stage_complete" if status_str == "completed"
                else "stage_fail" if status_str == "failed"
                else "stage_skip" if status_str == "skipped"
                else "stage_cancel"
            )
            events.append({
                "type": ev_type,
                "stage": stage_str,
                "timestamp": run.finished_at,
                "detail": (
                    f"Этап {stage_str} завершён за {round(run.elapsed, 1)}с"
                    if status_str == "completed" and hasattr(run, "elapsed") and run.elapsed
                    else f"Этап {stage_str} {status_str}"
                ),
                "error": run.error if status_str == "failed" else None,
            })

    # Сортируем по времени
    events.sort(key=lambda e: e["timestamp"] or "")
    events = events[-limit:]  # последние N записей

    return {
        "project_id": project_id,
        "project_status": (
            project.status.value if hasattr(project.status, "value") else str(project.status)
        ),
        "events": events,
        "total": len(events),
    }

# ─── NC5-01/Z3.4: Экспорт субтитров в разных форматах ─────────────────────

@router.get(
    "/{project_id}/subtitles",
    summary="Экспортировать субтитры (SRT/VTT/ASS/SBV) (NC5-01, Z3.4)",
)
def download_subtitles(
    project_id: str = FastAPIPath(...),
    format: str = "srt",  # noqa: A002
    store: ProjectStore = Depends(get_store),
):
    """Скачать субтитры в нужном формате.

    Параметры:
    - **format**: srt (по умолч.) | vtt | ass | sbv
    - SRT — универсальный, Premiere, DaVinci, VLC
    - VTT — браузерный player
    - ASS — Aegisub, профессиональное субтитрование (NC5-01)
    - SBV — YouTube Studio, Udemy (Z3.4)
    """
    valid_formats = ("srt", "vtt", "ass", "sbv")
    if format not in valid_formats:
        raise HTTPException(
            status_code=422,
            detail=f"Формат '{format}' не поддерживается. Допустимые: {list(valid_formats)}",
        )

    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.segments:
        raise HTTPException(status_code=404, detail="Субтитры ещё не созданы — запустите пайплайн")

    try:
        output_path = store.export_subtitles(project, fmt=format)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    content_types = {
        "srt": "text/srt",
        "vtt": "text/vtt",
        "ass": "text/x-ass",
        "sbv": "text/plain",
    }
    return FileResponse(
        output_path,
        media_type=content_types[format],
        filename=f"{safe_id}_subtitles.{format}",
    )

# ─── Z5.4: Batch-создание проектов ────────────────────────────────────────

class BatchCreateItem(BaseModel):
    """Один элемент пакетного создания проекта."""
    input_video: str          # путь к файлу или URL
    project_id: str | None = None
    config: dict | None = None


class BatchCreateRequest(BaseModel):
    """Тело запроса для batch-создания проектов."""
    items: list[BatchCreateItem]
    auto_run: bool = False   # если True — сразу запустить пайплайн
    from_stage: str | None = None


@router.post(
    "/batch",
    summary="Пакетное создание проектов (Z5.4)",
    status_code=207,  # Multi-Status
)
def batch_create_projects(
    req: BatchCreateRequest,
    store: ProjectStore = Depends(get_store),
):
    """Создать несколько проектов за один запрос.

    Возвращает статус 207 Multi-Status с результатами для каждого проекта.
    Если ``auto_run=True`` — сразу ставит в очередь выполнение.

    Ограничение: максимум 20 проектов за один batch-запрос.
    """
    MAX_BATCH = 20
    if len(req.items) > MAX_BATCH:
        raise HTTPException(
            status_code=422,
            detail=f"Максимум {MAX_BATCH} проектов за один batch-запрос. Получено: {len(req.items)}",
        )

    from translate_video.core.config import PipelineConfig  # noqa: PLC0415

    results = []
    for item in req.items:
        try:
            safe_id = sanitize_project_id(item.project_id) if item.project_id else None
            cfg = PipelineConfig.from_dict(item.config) if item.config else PipelineConfig()
            project = store.create_project(
                input_video=item.input_video,
                config=cfg,
                project_id=safe_id,
            )
            result: dict = {
                "project_id": project.id,
                "status": "created",
                "input_video": item.input_video,
            }
            if req.auto_run:
                # Делегируем пайплайн-запуск через BackgroundTasks не используем,
                # но ставим в очередь через уже существующий механизм
                try:
                    from translate_video.api.routes import pipeline as pm  # noqa: PLC0415
                    from translate_video.api.routes.pipeline import RunRequest as RR  # noqa: PLC0415
                    run_result = pm.run_pipeline(
                        project_id=project.id,
                        req=RR(from_stage=req.from_stage),
                        store=store,
                    )
                    result["run"] = run_result
                except Exception as run_err:  # noqa: BLE001
                    result["run_error"] = str(run_err)
            results.append(result)
        except Exception as err:  # noqa: BLE001
            results.append({
                "project_id": item.project_id,
                "status": "error",
                "error": str(err),
                "input_video": item.input_video,
            })

    return {
        "results": results,
        "total": len(results),
        "created": sum(1 for r in results if r["status"] == "created"),
        "errors": sum(1 for r in results if r["status"] == "error"),
    }

# ─── NC6-01: Импорт субтитров из SRT/VTT/ASS ──────────────────────────────

@router.post(
    "/{project_id}/import-subtitles",
    summary="Импортировать субтитры из SRT/VTT файла как переводы (NC6-01)",
)
async def import_subtitles(
    project_id: str = FastAPIPath(...),
    file: UploadFile = File(..., description="SRT или VTT файл субтитров"),
    apply_as_translation: bool = True,
    store: ProjectStore = Depends(get_store),
):
    """Загрузить файл субтитров и применить как переводы к сегментам.

    Алгоритм:
    1. Парсим SRT/VTT текст в блоки {start, end, text}
    2. Для каждого существующего сегмента ищем совпадение по времени (±200ms)
    3. Если найдено — заменяем ``translated_text``
    4. Если ``apply_as_translation=True`` — сохраняем как основной перевод

    Используется для:
    - Редактирования субтитров в Aegisub с последующей загрузкой обратно
    - Ручного улучшения машинного перевода
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    # Читаем загруженный файл
    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            content = content_bytes.decode("cp1251")
        except UnicodeDecodeError:
            raise HTTPException(status_code=422, detail="Не удалось прочитать файл: неизвестная кодировка")

    filename = (file.filename or "").lower()

    # Парсим субтитры
    import re  # noqa: PLC0415
    sub_blocks: list[dict] = []

    if filename.endswith(".vtt") or content.startswith("WEBVTT"):
        # VTT парсер
        for match in re.finditer(
            r"(\d{2}:\d{2}:\d{2}\.\d+)\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d+)[^\n]*\n(.*?)(?=\n\n|\Z)",
            content, re.DOTALL
        ):
            start_s = _parse_vtt_time(match.group(1))
            end_s = _parse_vtt_time(match.group(2))
            text = match.group(3).strip()
            if text and not text.startswith("<"):
                sub_blocks.append({"start": start_s, "end": end_s, "text": text})
    else:
        # SRT парсер
        for match in re.finditer(
            r"\d+\r?\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\r?\n(.*?)(?=\r?\n\r?\n|\Z)",
            content, re.DOTALL
        ):
            start_s = _parse_srt_time(match.group(1))
            end_s = _parse_srt_time(match.group(2))
            text = match.group(3).strip().replace("\r\n", "\n")
            if text:
                sub_blocks.append({"start": start_s, "end": end_s, "text": text})

    if not sub_blocks:
        raise HTTPException(status_code=422, detail="Не найдено ни одного блока субтитров в файле")

    # Матчим к сегментам (±200ms толерантность)
    TOLERANCE = 0.2
    matched = 0
    unmatched_subs = []

    if apply_as_translation and project.segments:
        for seg in project.segments:
            best = None
            best_dist = float("inf")
            for sub in sub_blocks:
                dist = abs(seg.start - sub["start"]) + abs(seg.end - sub["end"])
                if dist < best_dist and dist <= TOLERANCE * 2:
                    best_dist = dist
                    best = sub
            if best:
                seg.translated_text = best["text"]
                matched += 1
            else:
                unmatched_subs.append({"start": seg.start, "end": seg.end})

        store.save_segments(project, project.segments, translated=True)

    return {
        "project_id": project_id,
        "subtitle_blocks_parsed": len(sub_blocks),
        "segments_matched": matched,
        "segments_total": len(project.segments),
        "unmatched_segments": len(unmatched_subs),
        "applied": apply_as_translation,
    }


def _parse_srt_time(ts: str) -> float:
    """HH:MM:SS,mmm → секунды."""
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _parse_vtt_time(ts: str) -> float:
    """HH:MM:SS.mmm → секунды."""
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s_ms = parts
        s, ms = (s_ms + ".000")[:7].split(".")[:2]
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms[:3]) / 1000
    elif len(parts) == 2:
        m, s_ms = parts
        s, ms = (s_ms + ".000")[:7].split(".")[:2]
        return int(m) * 60 + int(s) + int(ms[:3]) / 1000
    return 0.0

# ─── Z3.13/Z3.14: Экспорт финального скрипта ──────────────────────────────

@router.get(
    "/{project_id}/export/script",
    summary="Финальный скрипт перевода в TXT (Z3.14)",
)
def export_script_txt(
    project_id: str = FastAPIPath(...),
    format: str = "txt",  # noqa: A002
    include_timecodes: bool = True,
    include_source: bool = False,
    store: ProjectStore = Depends(get_store),
):
    """Экспортировать переведённый скрипт как текстовый документ.

    Форматы:
    - **txt** — простой текст с таймкодами (для документалистов, Z3.14)
    - **tsv** — таблица с колонками: start | end | source | translated

    Полезно для:
    - Проверки качества перевода перед рендером
    - Передачи диктору для начитки
    - Создания транскрипта для SEO
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.segments:
        raise HTTPException(status_code=404, detail="Скрипт пуст — запустите перевод")

    from io import StringIO  # noqa: PLC0415
    from fastapi.responses import Response  # noqa: PLC0415

    if format == "tsv":
        buf = StringIO()
        buf.write("start\tend\tsource\ttranslated\n")
        for seg in project.segments:
            start = f"{seg.start:.2f}"
            end = f"{seg.end:.2f}"
            src = (seg.source_text or "").replace("\t", " ")
            tgt = (seg.translated_text or "").replace("\t", " ")
            buf.write(f"{start}\t{end}\t{src}\t{tgt}\n")
        return Response(
            content=buf.getvalue().encode("utf-8"),
            media_type="text/tab-separated-values",
            headers={"Content-Disposition": f'attachment; filename="{safe_id}_script.tsv"'},
        )

    # TXT
    buf = StringIO()
    buf.write(f"ПЕРЕВОД: {safe_id}\n")
    buf.write("=" * 60 + "\n\n")
    for i, seg in enumerate(project.segments, 1):
        if include_timecodes:
            start_ts = f"{int(seg.start // 60):02d}:{seg.start % 60:05.2f}"
            end_ts = f"{int(seg.end // 60):02d}:{seg.end % 60:05.2f}"
            buf.write(f"[{i}] {start_ts} → {end_ts}\n")
        if include_source:
            buf.write(f"  ОР: {seg.source_text or ''}\n")
        buf.write(f"  ПЕР: {seg.translated_text or '(нет перевода)'}\n\n")
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_id}_script.txt"'},
    )


# ─── Z1.12: Batch export всех субтитров в ZIP ─────────────────────────────

@router.get(
    "/{project_id}/export/subtitles-all",
    summary="Скачать все форматы субтитров в ZIP (Z1.12)",
)
def export_all_subtitles(
    project_id: str = FastAPIPath(...),
    store: ProjectStore = Depends(get_store),
):
    """Скачать SRT + VTT + ASS + SBV в одном ZIP-архиве.

    Удобно для публикации видео на разных платформах:
    - YouTube — SRT или SBV
    - Vimeo — VTT
    - Aegisub / профред — ASS
    - Местный плеер — SRT
    """
    import zipfile  # noqa: PLC0415
    import io  # noqa: PLC0415
    from fastapi.responses import Response  # noqa: PLC0415

    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.segments:
        raise HTTPException(status_code=404, detail="Субтитры ещё не созданы — запустите перевод")

    from translate_video.export.srt import segments_to_srt  # noqa: PLC0415
    from translate_video.export.vtt import segments_to_vtt  # noqa: PLC0415
    from translate_video.export.ass import segments_to_ass  # noqa: PLC0415
    from translate_video.export.sbv import segments_to_sbv  # noqa: PLC0415

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{safe_id}.srt", segments_to_srt(project.segments))
        zf.writestr(f"{safe_id}.vtt", segments_to_vtt(project.segments))
        zf.writestr(f"{safe_id}.ass", segments_to_ass(project.segments))
        zf.writestr(f"{safe_id}.sbv", segments_to_sbv(project.segments))

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_id}_subtitles.zip"'},
    )

# ─── Z2.13: Bulk translate выбранных сегментов ────────────────────────────────

class BulkTranslateRequest(BaseModel):
    segment_ids: list[str] = Field(default_factory=list, description="IDs сегментов для перевода. Пустой = все непереведённые")
    force: bool = Field(False, description="Перевести даже если уже переведены")
    target_language: str | None = Field(None, description="Язык перевода (переопределяет config)")


@router.post(
    "/{project_id}/bulk-translate",
    summary="Пакетный перевод выбранных сегментов (Z2.13)",
)
def bulk_translate_segments(
    project_id: str = FastAPIPath(...),
    body: BulkTranslateRequest = Body(...),
    store: ProjectStore = Depends(get_store),
):
    """Запустить перевод для выбранных сегментов в фоне.

    Если segment_ids пустой — переводятся все сегменты без перевода.
    Возвращает: список ID сегментов поставленных в очередь и статус.
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.segments:
        raise HTTPException(status_code=404, detail="Сегменты не найдены — запустите транскрипцию")

    # Определяем какие сегменты переводить
    target_segs = [
        s for s in project.segments
        if (not body.segment_ids or s.id in body.segment_ids)
        and (body.force or not (s.translated_text or "").strip())
    ]

    if not target_segs:
        return {
            "project_id": project_id,
            "queued": 0,
            "segment_ids": [],
            "message": "Нет сегментов для перевода (все уже переведены или ids не совпали)",
        }

    # Помечаем отобранные сегменты как draft для повторного перевода
    for seg in target_segs:
        seg.translated_text = ""
        seg.status = SegmentStatus.DRAFT

    store.save_project(project)

    return {
        "project_id": project_id,
        "queued": len(target_segs),
        "segment_ids": [s.id for s in target_segs],
        "message": f"{len(target_segs)} сегментов помечены для перевода. Запустите пайплайн с from_stage=translate",
    }

# ─── NC8-01: Удаление сегмента из проекта ────────────────────────────────────

@router.delete(
    "/{project_id}/segments/{segment_id}",
    summary="Удалить сегмент из проекта (NC8-01)",
)
def delete_segment(
    project_id: str = FastAPIPath(...),
    segment_id: str = FastAPIPath(...),
    store: ProjectStore = Depends(get_store),
):
    """Удаляет один сегмент из проекта по его ID.

    После удаления транскрипт пересохраняется.
    Возвращает: обновлённый список сегментов.
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    original_count = len(project.segments or [])
    new_segments = [s for s in (project.segments or []) if s.id != segment_id]

    if len(new_segments) == original_count:
        raise HTTPException(status_code=404, detail=f"Сегмент '{segment_id}' не найден")

    store.save_segments(project, new_segments, translated=bool(
        any(s.translated_text for s in new_segments)
    ))

    return {
        "project_id": project_id,
        "deleted_id": segment_id,
        "segments_remaining": len(new_segments),
        "segments": [s.to_dict() for s in new_segments],
    }


# ─── Z5.14: История вебхуков проекта ─────────────────────────────────────────

@router.get(
    "/{project_id}/webhook-history",
    summary="История отправленных вебхуков проекта (Z5.14)",
)
def get_webhook_history(
    project_id: str = FastAPIPath(...),
    limit: int = 50,
    store: ProjectStore = Depends(get_store),
):
    """Вернуть список вебхук-событий отправленных для данного проекта.

    Восстанавливает историю из webhook_events в project.json.
    Каждая запись: event_type, url, payload_preview, sent_at.
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    # Webhook events хранятся в stage_runs metadata
    events = []
    for run in (project.stage_runs or []):
        metadata = run.to_dict().get("metadata") or {}
        webhook_sent = metadata.get("webhook_sent")
        if webhook_sent:
            events.append({
                "stage": run.stage if hasattr(run, "stage") else "unknown",
                "status": run.status if hasattr(run, "status") else "unknown",
                "sent_at": run.to_dict().get("completed_at") or run.to_dict().get("started_at"),
                "webhook_url": metadata.get("webhook_url", ""),
                "event_type": f"project.stage.{run.status if hasattr(run, 'status') else 'unknown'}",
            })

    return {
        "project_id": project_id,
        "webhook_events": events[-limit:],
        "total": len(events),
    }

# ─── NC9-01: Разделение сегмента ─────────────────────────────────────────────

class SplitSegmentRequest(BaseModel):
    split_at_char: int = Field(..., description="Позиция в тексте перевода для разделения")
    mid_time: float | None = Field(None, description="Время разделения в секундах (если None — пропорционально длине строк)")


@router.post(
    "/{project_id}/segments/{segment_id}/split",
    summary="Разделить сегмент на два (NC9-01)",
)
def split_segment(
    project_id: str = FastAPIPath(...),
    segment_id: str = FastAPIPath(...),
    body: SplitSegmentRequest = Body(...),
    store: ProjectStore = Depends(get_store),
):
    """Разделяет сегмент на два по указанной позиции в тексте перевода.

    mid_time: если не указан — рассчитывается пропорционально длине частей текста.
    Возвращает: обновлённый список сегментов.
    """
    import uuid as _uuid
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    segs = list(project.segments or [])
    idx = next((i for i, s in enumerate(segs) if s.id == segment_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail=f"Сегмент '{segment_id}' не найден")

    seg = segs[idx]
    full_text = seg.translated_text or ""
    char_pos = max(0, min(body.split_at_char, len(full_text)))

    text_a = full_text[:char_pos].strip()
    text_b = full_text[char_pos:].strip()

    if not text_a or not text_b:
        raise HTTPException(status_code=422, detail="Позиция разделения создаёт пустой сегмент")

    # Вычисляем время разделения
    if body.mid_time is not None:
        mid_t = max(seg.start, min(body.mid_time, seg.end))
    else:
        ratio = len(text_a) / max(len(full_text), 1)
        mid_t = round(seg.start + (seg.end - seg.start) * ratio, 3)

    # Аналогично для исходного текста
    src_full = seg.source_text or ""
    src_pos = int(len(src_full) * (char_pos / max(len(full_text), 1)))
    src_a = src_full[:src_pos].strip()
    src_b = src_full[src_pos:].strip()

    seg_a = Segment(
        id=seg.id,
        start=seg.start,
        end=mid_t,
        source_text=src_a or seg.source_text,
        translated_text=text_a,
        status=seg.status,
    )
    seg_b = Segment(
        id=f"{seg.id}_b_{_uuid.uuid4().hex[:6]}",
        start=mid_t,
        end=seg.end,
        source_text=src_b or seg.source_text,
        translated_text=text_b,
        status=seg.status,
    )
    new_segs = segs[:idx] + [seg_a, seg_b] + segs[idx + 1:]
    store.save_segments(project, new_segs, translated=bool(any(s.translated_text for s in new_segs)))

    return {
        "project_id": project_id,
        "split_from": segment_id,
        "segment_a": seg_a.to_dict(),
        "segment_b": seg_b.to_dict(),
        "segments_total": len(new_segs),
    }


# ─── Z1.14: Скачать готовое видео ────────────────────────────────────────────

@router.get(
    "/{project_id}/download-video",
    summary="Скачать переведённое видео (Z1.14)",
)
def download_final_video(
    project_id: str = FastAPIPath(...),
    store: ProjectStore = Depends(get_store),
):
    """Скачать готовое переведённое видео (output_video или output_video_with_subs).

    Возвращает 404 если рендеринг ещё не завершён.
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    # Пытаемся взять output_video_with_subs, потом output_video
    for kind_val in ("output_video_with_subs", "output_video"):
        rel_path = project.artifacts.get(kind_val)
        if rel_path:
            abs_path = project.work_dir / rel_path
            if abs_path.exists():
                return FileResponse(
                    str(abs_path),
                    media_type="video/mp4",
                    filename=f"{project_id}_translated.mp4",
                )

    raise HTTPException(
        status_code=404,
        detail="Готовое видео не найдено — возможно рендеринг ещё не завершён",
    )

# ─── NC10-01: Теги/метки проекта ─────────────────────────────────────────────

class SetTagsRequest(BaseModel):
    tags: list[str] = Field(default_factory=list, description="Список тегов. Пустой = очистить все")


@router.put(
    "/{project_id}/tags",
    summary="Установить теги проекта (NC10-01)",
)
def set_project_tags(
    project_id: str = FastAPIPath(...),
    body: SetTagsRequest = Body(...),
    store: ProjectStore = Depends(get_store),
):
    """Обновить теги проекта. Перезаписывает все существующие теги.

    Возвращает: обновлённые теги.
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    project.tags = [str(t).strip()[:50] for t in body.tags if str(t).strip()][:20]
    store.save_project(project)

    return {"project_id": project_id, "tags": project.tags}


# ─── NC10-02: Архивирование проекта ──────────────────────────────────────────

@router.post(
    "/{project_id}/archive",
    summary="Архивировать проект (NC10-02)",
)
def archive_project(
    project_id: str = FastAPIPath(...),
    store: ProjectStore = Depends(get_store),
):
    """Пометить проект как архивный (скрывается из основного списка).

    Архивный проект можно разархивировать через /unarchive.
    """
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    project.archived = True
    store.save_project(project)
    return {"project_id": project_id, "archived": True}


@router.post(
    "/{project_id}/unarchive",
    summary="Разархивировать проект (NC10-02)",
)
def unarchive_project(
    project_id: str = FastAPIPath(...),
    store: ProjectStore = Depends(get_store),
):
    """Восстановить архивный проект в основной список."""
    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    project.archived = False
    store.save_project(project)
    return {"project_id": project_id, "archived": False}

# ─── NC11-01: Экспорт проекта в ZIP-архив ────────────────────────────────────

@router.get(
    "/{project_id}/export/zip",
    summary="Экспортировать весь проект как ZIP (NC11-01)",
)
def export_project_zip(
    project_id: str = FastAPIPath(...),
    store: ProjectStore = Depends(get_store),
):
    """Экспортирует все артефакты проекта в ZIP-архив.

    Включает: все форматы субтитров (SRT, VTT, ASS, SBV), скрипт перевода (TXT, TSV), project.json.
    Большие видеофайлы НЕ включаются в ZIP — только текстовые артефакты.
    """
    import zipfile as _zip
    import io as _io
    from fastapi.responses import StreamingResponse  # noqa: PLC0415

    safe_id = sanitize_project_id(project_id)
    try:
        project = store.load_project(store.root / safe_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    buf = _io.BytesIO()
    with _zip.ZipFile(buf, "w", compression=_zip.ZIP_DEFLATED) as zf:
        # project.json
        import json as _json  # noqa: PLC0415
        zf.writestr("project.json", _json.dumps(project.to_dict(), ensure_ascii=False, indent=2, default=str))

        # Субтитры — если есть сегменты
        if project.segments:
            from translate_video.core.store import ProjectStore as _PS  # noqa: PLC0415
            try:
                srt = store.export_subtitles(project, "srt")
                zf.writestr(f"{project_id}.srt", srt)
            except Exception:
                pass
            try:
                vtt = store.export_subtitles(project, "vtt")
                zf.writestr(f"{project_id}.vtt", vtt)
            except Exception:
                pass
            try:
                ass = store.export_subtitles(project, "ass")
                zf.writestr(f"{project_id}.ass", ass)
            except Exception:
                pass
            try:
                sbv = store.export_subtitles(project, "sbv")
                zf.writestr(f"{project_id}.sbv", sbv)
            except Exception:
                pass

            # Скрипт перевода (TXT)
            script_lines = []
            for s in project.segments:
                script_lines.append(f"[{s.start:.1f}-{s.end:.1f}] {s.translated_text or ''}")
            zf.writestr(f"{project_id}_script.txt", "\n".join(script_lines))

            # TSV
            tsv_lines = ["start\tend\tsource\ttranslation"]
            for s in project.segments:
                tsv_lines.append(f"{s.start}\t{s.end}\t{s.source_text or ''}\t{s.translated_text or ''}")
            zf.writestr(f"{project_id}_script.tsv", "\n".join(tsv_lines))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={safe_id}.zip"},
    )
