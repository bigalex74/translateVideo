"""DevLogWriter — подробное логирование для режима разработчика.

Пишет события в {work_dir}/devlog.jsonl (одна JSON-запись на строку).
Активируется только при PipelineConfig.dev_mode == True.
Предназначен для отладки промтов, анализа качества и профилирования.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from translate_video.core.log import get_logger

_log = get_logger(__name__)

# Максимальный размер prompt/response в одной записи (5000 символов)
_MAX_TEXT_CHARS = 5000
# Максимальный размер файла devlog (5 MB)
_MAX_FILE_BYTES = 5 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _truncate(text: str | None, limit: int = _MAX_TEXT_CHARS) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"…[обрезано, всего {len(text)} симв.]"


class DevLogWriter:
    """Записывает dev-события в JSONL-файл проекта.

    Thread-safe: использует Lock для записи.
    Автоматически останавливает запись при превышении лимита файла.
    """

    def __init__(self, work_dir: Path, *, enabled: bool = True) -> None:
        self._path = work_dir / "devlog.jsonl"
        self._enabled = enabled
        self._lock = threading.Lock()
        self._stopped = False
        if enabled:
            # Создаём файл (или открываем для дозаписи если прогон продолжается)
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._write({"event": "devlog.start", "path": str(self._path)})
            except OSError as exc:
                _log.warning("devlog.init_failed", error=str(exc))
                self._enabled = False

    @classmethod
    def from_config(cls, config: Any, work_dir: Path) -> "DevLogWriter":
        """Создать writer из PipelineConfig. Выключен если dev_mode=False."""
        enabled = getattr(config, "dev_mode", False)
        return cls(work_dir, enabled=enabled)

    # ── Публичные методы событий ──────────────────────────────────────────────

    def log_stage_start(self, stage: str, **kwargs: Any) -> None:
        """Начало этапа пайплайна."""
        self._write({"event": "stage.start", "stage": stage, **kwargs})

    def log_stage_end(
        self,
        stage: str,
        *,
        elapsed_s: float,
        status: str = "done",
        **kwargs: Any,
    ) -> None:
        """Конец этапа с временем выполнения."""
        self._write({
            "event": "stage.end",
            "stage": stage,
            "status": status,
            "elapsed_s": round(elapsed_s, 3),
            **kwargs,
        })

    def log_stage_io(
        self,
        stage: str,
        *,
        direction: str,  # "input" | "output"
        **kwargs: Any,
    ) -> None:
        """Входные или выходные данные этапа."""
        self._write({
            "event": "stage.io",
            "stage": stage,
            "direction": direction,
            **kwargs,
        })

    def log_transcription(
        self,
        *,
        segments_count: int,
        language: str,
        model: str,
        elapsed_s: float,
        audio_duration_s: float | None = None,
        avg_confidence: float | None = None,
    ) -> None:
        """Результат транскрипции."""
        self._write({
            "event": "transcribe.result",
            "stage": "transcribe",
            "segments": segments_count,
            "language": language,
            "model": model,
            "elapsed_s": round(elapsed_s, 3),
            "audio_duration_s": round(audio_duration_s, 2) if audio_duration_s else None,
            "avg_confidence": round(avg_confidence, 4) if avg_confidence else None,
        })

    def log_translate_prompt(
        self,
        *,
        segment_index: int,
        segment_id: str,
        provider: str,
        model: str,
        source_text: str,
        prompt: str,
        response: str,
        elapsed_s: float,
    ) -> None:
        """Полный промт и ответ для перевода одного сегмента."""
        self._write({
            "event": "translate.prompt",
            "stage": "translate",
            "segment_index": segment_index,
            "segment_id": segment_id,
            "provider": provider,
            "model": model,
            "elapsed_s": round(elapsed_s, 3),
            "source_chars": len(source_text),
            "prompt_chars": len(prompt),
            "response_chars": len(response),
            "source_text": _truncate(source_text, 500),
            "prompt": _truncate(prompt),
            "response": _truncate(response, 1000),
        })

    def log_translate_fallback(
        self,
        *,
        segment_index: int,
        segment_id: str,
        reason: str,
        fallback: str = "google",
    ) -> None:
        """Fallback на резервный переводчик."""
        self._write({
            "event": "translate.fallback",
            "stage": "translate",
            "segment_index": segment_index,
            "segment_id": segment_id,
            "fallback": fallback,
            "reason": _truncate(reason, 300),
        })

    def log_rewrite_attempt(
        self,
        *,
        segment_id: str,
        attempt: int,
        provider: str,
        model: str,
        original_text: str,
        source_text: str,
        prompt: str,
        response: str,
        max_chars: int,
        result_chars: int,
        fits: bool,
        elapsed_s: float,
    ) -> None:
        """Одна попытка сокращения текста под тайминг."""
        self._write({
            "event": "rewrite.attempt",
            "stage": "timing_fit",
            "segment_id": segment_id,
            "attempt": attempt,
            "provider": provider,
            "model": model,
            "elapsed_s": round(elapsed_s, 3),
            "original_chars": len(original_text),
            "max_chars": max_chars,
            "result_chars": result_chars,
            "fits": fits,
            "compression": round(result_chars / len(original_text), 3) if original_text else None,
            "source_text": _truncate(source_text, 300),
            "original_text": _truncate(original_text, 500),
            "prompt": _truncate(prompt),
            "response": _truncate(response, 500),
        })

    def log_tts_segment(
        self,
        *,
        segment_id: str,
        text: str,
        duration_s: float,
        slot_s: float,
        overflow: bool,
        adapted: bool = False,
        voice: str | None = None,
    ) -> None:
        """TTS синтез одного сегмента."""
        self._write({
            "event": "tts.segment",
            "stage": "tts",
            "segment_id": segment_id,
            "text_chars": len(text),
            "duration_s": round(duration_s, 3),
            "slot_s": round(slot_s, 3),
            "overflow": overflow,
            "adapted": adapted,
            "voice": voice,
            "utilization": round(duration_s / slot_s, 3) if slot_s > 0 else None,
        })

    def log_error(self, stage: str, *, error: str, **kwargs: Any) -> None:
        """Ошибка в этапе или провайдере."""
        self._write({
            "event": "error",
            "stage": stage,
            "error": _truncate(error, 500),
            **kwargs,
        })

    # ── Служебные методы ─────────────────────────────────────────────────────

    def _write(self, payload: dict[str, Any]) -> None:
        """Записать JSON-событие в файл (thread-safe)."""
        if not self._enabled or self._stopped:
            return
        payload.setdefault("ts", _now())
        line = json.dumps(payload, ensure_ascii=False, default=str)
        with self._lock:
            try:
                # Проверяем лимит размера файла
                if self._path.exists() and self._path.stat().st_size >= _MAX_FILE_BYTES:
                    if not self._stopped:
                        self._stopped = True
                        _log.warning(
                            "devlog.size_limit_reached",
                            path=str(self._path),
                            limit_mb=_MAX_FILE_BYTES // 1024 // 1024,
                        )
                    return
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError as exc:
                _log.warning("devlog.write_failed", error=str(exc))

    def path(self) -> Path:
        """Вернуть путь к файлу devlog."""
        return self._path

    def exists(self) -> bool:
        """Проверить, существует ли файл devlog."""
        return self._path.exists()

    def read_events(
        self,
        *,
        limit: int = 1000,
        offset: int = 0,
        stage: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Прочитать события из файла с опциональной фильтрацией."""
        if not self._path.exists():
            return []
        events: list[dict[str, Any]] = []
        try:
            with self._path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if stage and evt.get("stage") != stage:
                        continue
                    if event_type and not evt.get("event", "").startswith(event_type):
                        continue
                    events.append(evt)
        except OSError:
            return []
        return events[offset:offset + limit]

    def size_bytes(self) -> int:
        """Вернуть размер файла в байтах."""
        try:
            return self._path.stat().st_size if self._path.exists() else 0
        except OSError:
            return 0


class NullDevLogWriter(DevLogWriter):
    """No-op writer для выключенного dev mode (не создаёт файл, не пишет)."""

    def __init__(self) -> None:  # noqa: D107
        self._enabled = False
        self._stopped = False
        self._path = Path("/dev/null")
        self._lock = threading.Lock()

    def _write(self, payload: dict[str, Any]) -> None:
        pass

    def exists(self) -> bool:
        return False

    def size_bytes(self) -> int:
        return 0
