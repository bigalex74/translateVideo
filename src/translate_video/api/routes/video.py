"""Маршрут для стриминга видеофайлов с правильным Content-Type и Range-поддержкой."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from translate_video.core.store import sanitize_project_id

router = APIRouter(prefix="/api/v1/video", tags=["video"])

_WORK_ROOT = Path(os.getenv("WORK_ROOT", "runs")).resolve()

# Список разрешённых расширений
_ALLOWED_EXTS = {".mp4", ".webm", ".ogg", ".ogv", ".mov", ".mkv", ".avi", ".mp3", ".wav", ".aac"}

# Размер чанка для стриминга
_CHUNK = 1024 * 1024  # 1 MiB


def _resolve_video(project_id: str, rel_path: str) -> Path:
    """Безопасно разрешить путь к видеофайлу внутри папки проекта.

    Поддерживает подпапки (например 'output/translated.mp4').
    Защита от path traversal через resolve() + проверку принадлежности work_dir.
    """
    try:
        safe_id = sanitize_project_id(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный ID проекта")

    ext = Path(rel_path).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Расширение файла не поддерживается: {ext!r}")

    project_dir = (_WORK_ROOT / safe_id).resolve()
    candidate = (project_dir / rel_path).resolve()

    # Защита от path traversal: candidate должен быть внутри project_dir
    if project_dir not in candidate.parents and candidate != project_dir:
        raise HTTPException(status_code=400, detail="Путь выходит за пределы проекта")

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"Видеофайл не найден: {rel_path}")

    return candidate


def _mime(path: Path) -> str:
    """Определить MIME-тип по расширению."""
    mime, _ = mimetypes.guess_type(str(path))
    if mime and mime.startswith(("video/", "audio/")):
        return mime
    ext = path.suffix.lower()
    return {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".ogg": "video/ogg",
        ".ogv": "video/ogg",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".aac": "audio/aac",
    }.get(ext, "application/octet-stream")


def _stream(path: Path, start: int, end: int):
    """Генератор чанков файла для Range-стриминга."""
    with open(path, "rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = f.read(min(_CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/{project_id}/{filepath:path}")
def stream_video(project_id: str, filepath: str, request: Request):
    """Стриминг видео/аудио-файла с поддержкой Range-запросов.

    filepath — путь относительно project_dir, может содержать подпапки
    (например 'output/translated.mp4').
    """
    path = _resolve_video(project_id, filepath)
    file_size = path.stat().st_size
    content_type = _mime(path)

    range_header = request.headers.get("Range")

    if range_header:
        # Парсим "bytes=start-end"
        try:
            range_spec = range_header.replace("bytes=", "")
            range_start, range_end = range_spec.split("-")
            start = int(range_start)
            end = int(range_end) if range_end else file_size - 1
        except (ValueError, AttributeError):
            raise HTTPException(status_code=416, detail="Некорректный Range-заголовок")

        if start >= file_size or end >= file_size or start > end:
            raise HTTPException(status_code=416, detail="Запрошенный диапазон недоступен")

        length = end - start + 1
        return StreamingResponse(
            _stream(path, start, end),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Cache-Control": "public, max-age=3600",
            },
        )

    # Полный файл
    return StreamingResponse(
        _stream(path, 0, file_size - 1),
        status_code=200,
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=3600",
        },
    )
