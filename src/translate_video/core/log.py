"""Единый модуль логирования translateVideo.

Использование:
    from translate_video.core.log import get_logger
    log = get_logger(__name__)
    log.info("stage.done", stage="transcribe", elapsed_s=12.3, segments=42)

Конфигурация через переменные окружения (или .env):
    LOG_LEVEL  = DEBUG | INFO | WARNING | ERROR  (default: INFO)
    LOG_FORMAT = json | text                     (default: json)
    LOG_FILE   = /app/logs/app.log               (default: пусто = только stdout)
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import time
from typing import Any


# ── Кастомный JSON-форматтер ─────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    """Форматирует записи как однострочный JSON-объект с ключами extras."""

    # Стандартные атрибуты LogRecord, которые НЕ включаем в extras
    _SKIP = frozenset({
        "name", "msg", "args", "created", "relativeCreated",
        "thread", "threadName", "processName", "process",
        "levelno", "pathname", "filename", "module", "lineno",
        "funcName", "stack_info", "msecs", "exc_info", "exc_text",
        "levelname", "message",
    })

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        obj: dict[str, Any] = {
            "ts":    self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg":   record.message,
        }
        # Добавляем все extra-поля, переданные через log.info(..., key=value)
        for k, v in record.__dict__.items():
            if k not in self._SKIP and not k.startswith("_"):
                obj[k] = v
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(obj, ensure_ascii=False, default=str)


class _TextFormatter(logging.Formatter):
    """Human-readable форматтер для разработки."""

    _FMT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self._FMT, datefmt="%H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in _JsonFormatter._SKIP and not k.startswith("_")
        }
        if extras:
            kv = "  ".join(f"{k}={v}" for k, v in extras.items())
            return f"{base}  {kv}"
        return base


# ── Публичный API ─────────────────────────────────────────────────────────────

def configure_logging(
    level: str = "INFO",
    fmt: str = "json",
    log_file: str | None = None,
) -> None:
    """Настроить корневой логгер translateVideo. Вызывать один раз при старте.

    Args:
        level:    Уровень логирования (DEBUG/INFO/WARNING/ERROR).
        fmt:      Формат вывода: 'json' или 'text'.
        log_file: Путь к файлу логов. None или '' = только stdout.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter: logging.Formatter = (
        _TextFormatter() if fmt.lower() == "text" else _JsonFormatter()
    )

    # Stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    handlers: list[logging.Handler] = [stdout_handler]

    # Файловый handler с ротацией
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Настраиваем корневой логгер пакета
    root = logging.getLogger("translate_video")
    root.setLevel(numeric_level)
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)
    root.propagate = False  # не дублируем в uvicorn/root logger

    # Минимизируем шум от сторонних библиотек
    for noisy in ("httpx", "httpcore", "urllib3", "faster_whisper", "moviepy"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def configure_from_env() -> None:
    """Настроить логирование из переменных окружения (вызывать при старте)."""
    configure_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        fmt=os.getenv("LOG_FORMAT", "json"),
        log_file=os.getenv("LOG_FILE") or None,
    )


def get_logger(name: str) -> "StructLogger":
    """Получить структурированный logger для модуля. name обычно = __name__."""
    inner_name = name if name.startswith("translate_video") else f"translate_video.{name}"
    return StructLogger(logging.getLogger(inner_name))


class StructLogger:
    """Обёртка над logging.Logger с поддержкой log.info("msg", key=value, ...).

    Стандартный logging.Logger не принимает **kwargs — только args и extra.
    Этот класс передаёт все kwargs через extra={} и строит итоговый JSON.

    Пример:
        log.info("stage.done", stage="transcribe", elapsed_s=12.3)
        log.warning("rewriter.fallback", from_provider="gemini", to_provider="openrouter")
        log.error("stage.fail", stage="tts", error=str(exc))
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        """Передать событие в logging, отделив служебные kwargs от extra-полей."""

        if self._logger.isEnabledFor(level):
            exc_info = kwargs.pop("exc_info", None)
            stack_info = kwargs.pop("stack_info", False)
            stacklevel = int(kwargs.pop("stacklevel", 1))
            extra = kwargs.pop("extra", {})
            if kwargs:
                extra = {**extra, **kwargs}
            self._logger.log(
                level,
                msg,
                *args,
                exc_info=exc_info,
                stack_info=stack_info,
                stacklevel=stacklevel + 1,
                extra=extra or None,
            )

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Логировать DEBUG-событие."""

        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Логировать INFO-событие."""

        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Логировать WARNING-событие."""

        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Логировать ERROR-событие."""

        self._log(logging.ERROR, msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Логировать ERROR с текущим traceback (аналог logger.exception)."""

        kwargs["exc_info"] = True
        self._log(logging.ERROR, msg, *args, **kwargs)


# ── Контекстный таймер ────────────────────────────────────────────────────────

class Timer:
    """Простой контекстный таймер для измерения elapsed_s.

    Пример:
        with Timer() as t:
            do_work()
        log.info("done", elapsed_s=t.elapsed)
    """

    def __init__(self) -> None:
        self._start: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.monotonic()
        return self

    def __exit__(self, *_: object) -> None:
        self.elapsed = round(time.monotonic() - self._start, 3)
