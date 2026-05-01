"""Маршруты предварительной проверки входного видео."""

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from translate_video.core.preflight import run_preflight

router = APIRouter(prefix="/api/v1/preflight", tags=["preflight"])


class PreflightRequest(BaseModel):
    """Схема запроса предварительной проверки."""

    input_video: str
    provider: str = "fake"


@router.post("")
def preflight(req: PreflightRequest):
    """Проверить файл и окружение без запуска пайплайна."""

    return run_preflight(Path(req.input_video), req.provider).to_dict()
