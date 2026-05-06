"""Retry с exponential backoff для сетевых вызовов (Backend агент backlog).

Универсальная утилита для всех TTS и API-провайдеров.
Использует jitter чтобы не создавать "thundering herd" при параллельных запросах.
"""

from __future__ import annotations

import time
import random
import logging
from typing import Callable, TypeVar

_log = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)

# Коды HTTP, при которых имеет смысл повторять
_RETRYABLE_CODES = {429, 500, 502, 503, 504, 520, 521, 522, 524}


def with_retry(
    fn: Callable,
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (OSError, ConnectionError, TimeoutError),
    label: str = "call",
    **kwargs,
):
    """Вызвать fn(*args, **kwargs) с retry exponential backoff.

    Args:
        fn: Функция для вызова.
        max_attempts: Максимальное количество попыток (включая первую).
        base_delay: Начальная задержка в секундах.
        max_delay: Максимальная задержка между попытками.
        backoff_factor: Множитель задержки (2.0 = экспоненциальный).
        jitter: Добавить случайный сдвиг до ±25% для равномерного распределения.
        retryable_exceptions: Исключения, при которых повторяем.
        label: Метка для логирования.

    Returns:
        Результат fn при успехе.

    Raises:
        Последнее исключение если все попытки исчерпаны.
    """
    last_exc: Exception | None = None
    delay = base_delay

    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exc = exc
            if attempt == max_attempts:
                _log.error(
                    "retry.exhausted [%s] attempts=%d error=%s",
                    label, attempt, str(exc)[:200],
                )
                raise

            # Проверяем HTTP код из RuntimeError (наш формат "HTTP 429: ...")
            msg = str(exc)
            if "HTTP " in msg:
                try:
                    code = int(msg.split("HTTP ")[1].split(":")[0].strip())
                    if code not in _RETRYABLE_CODES:
                        _log.warning(
                            "retry.non_retryable [%s] http=%d",
                            label, code,
                        )
                        raise
                    # Rate limit: читаем Retry-After если есть (упрощённо)
                    if code == 429:
                        delay = max(delay, 5.0)
                except (ValueError, IndexError):
                    pass

            sleep_time = min(delay, max_delay)
            if jitter:
                sleep_time *= 1.0 + random.uniform(-0.25, 0.25)

            _log.warning(
                "retry.attempt [%s] #%d in %.2fs: %s",
                label, attempt, sleep_time, str(exc)[:120],
            )
            time.sleep(sleep_time)
            delay *= backoff_factor

    # Никогда не достигается, но для mypy
    assert last_exc is not None
    raise last_exc


class RetryConfig:
    """Конфигурация retry из переменных окружения или явных значений."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
    ) -> None:
        import os
        self.max_attempts = int(os.getenv("TTS_RETRY_ATTEMPTS", str(max_attempts)))
        self.base_delay = float(os.getenv("TTS_RETRY_BASE_DELAY", str(base_delay)))
        self.max_delay = float(os.getenv("TTS_RETRY_MAX_DELAY", str(max_delay)))
        self.backoff_factor = float(os.getenv("TTS_RETRY_BACKOFF", str(backoff_factor)))

    def call(self, fn: Callable, *args, label: str = "tts", **kwargs):
        """Применить retry к вызову fn."""
        return with_retry(
            fn, *args,
            max_attempts=self.max_attempts,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            backoff_factor=self.backoff_factor,
            label=label,
            **kwargs,
        )


# Глобальный дефолтный retry для TTS
DEFAULT_TTS_RETRY = RetryConfig()
