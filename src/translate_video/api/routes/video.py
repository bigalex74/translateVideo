"""Маршрут для стриминга видеофайлов с правильным Content-Type и Range-поддержкой."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/v1/video", tags=["video"])

_WORK_ROOT = Path(os.getenv("WORK_ROOT", "runs"))

# Список разрешённых расширений
_ALLOWED_EXTS = {".mp4", ".webm", ".ogg", ".ogv", ".mov", ".mkv", ".avi", ".mp3", ".wav", ".aac"}

# Размер чанка для стриминга
_CHUNK = 1024 * 1024  # 1 MiB


def _resolve_video(project_id: str, filename: str) -> Path:
    """Безопасно разрешить путь к видеофайлу внутри папки проекта."""
    # Защита от path traversal
    safe_id = Path(project_id).name
    safe_file = Path(filename).name
    if not safe_id or not safe_file:
        raise HTTPException(status_code=400, detail="Некорректный путь")
    ext = Path(safe_file).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Расширение файла не поддерживается: {ext}")
    path = _WORK_ROOT / safe_id / safe_file
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Видеофайл не найден")
    return path


def _mime(path: Path) -> str:
    """Определить MIME-тип по расширению."""
    mime, _ = mimetypes.guess_type(str(path))
    if mime and mime.startswith("video/"):
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


@router.get("/{project_id}/{filename}")
def stream_video(project_id: str, filename: str, request: Request):
    """Стриминг видео/аудио-файла с поддержкой Range-запросов (необходима для перемотки)."""
    path = _resolve_video(project_id, filename)
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
