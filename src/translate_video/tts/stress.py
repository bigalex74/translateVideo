"""Автоматическая расстановка ударений для Yandex SpeechKit.

SpeechKit принимает символ ``+`` перед ударной гласной в plain-text:
  «молоко» → «молок+о»

Для этого используется библиотека **ruaccent** (Den4ikAI/ruaccent),
которая даёт точность 95–98% на общем русском тексте.

Жизненный цикл:
- Модель загружается ОДИН РАЗ при первом вызове ``process()`` (lazy init).
- Если ruaccent не установлен — возвращаем текст без изменений (graceful fallback).
- Тяжёлый синглтон хранится в ``_ACCENTIZER``.

Размер моделей (tiny2 — default):
  tiny2: ~40 MB, быстрая, точность ~96%
  turbo2: ~200 MB, медленная, точность ~98%

Конфиг (PipelineConfig.professional_tts_use_stress — bool, default True).
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from translate_video.core.log import get_logger
from translate_video.tts.normalize import normalize

if TYPE_CHECKING:
    pass

_log = get_logger(__name__)
_lock = threading.Lock()
_ACCENTIZER = None          # lazy singleton
_AVAILABLE: bool | None = None  # кэш флага «ruaccent установлен»


def _check_available() -> bool:
    global _AVAILABLE
    if _AVAILABLE is None:
        try:
            import ruaccent  # noqa: F401
            _AVAILABLE = True
        except ImportError:
            _AVAILABLE = False
            _log.warning("stress.ruaccent_unavailable", hint="pip install ruaccent")
    return _AVAILABLE


def _get_accentizer(model_size: str = "tiny2"):
    """Загрузить/вернуть синглтон RUAccent."""
    global _ACCENTIZER
    if _ACCENTIZER is not None:
        return _ACCENTIZER
    with _lock:
        if _ACCENTIZER is not None:
            return _ACCENTIZER
        _log.info("stress.loading_model", model_size=model_size)
        from ruaccent import RUAccent  # type: ignore[import]
        acc = RUAccent()
        acc.load(
            omograph_model_size=model_size,
            use_dictionary=True,
            tiny_mode=False,
        )
        _ACCENTIZER = acc
        _log.info("stress.model_loaded", model_size=model_size)
    return _ACCENTIZER


def process(text: str, *, model_size: str = "tiny2") -> str:
    """Расставить ударения в русском тексте.

    Возвращает текст с ``+`` перед ударными гласными, пригодный
    для прямой передачи в Yandex SpeechKit v3.

    При ошибке или отсутствии ruaccent — возвращает ``text`` без изменений.

    Args:
        text: Исходный русский текст.
        model_size: Размер модели («tiny2» / «turbo2» / «turbo3.1»).

    Returns:
        Текст с ударениями или исходный текст при ошибке.
    """
    if not text or not text.strip():
        return text

    # Нормализация: 24/7 → «двадцать четыре на семь», % / $ / ИИ и др.
    text = normalize(text)

    if not _check_available():
        return text

    try:
        acc = _get_accentizer(model_size=model_size)
        result = acc.process_all(text)
        return result
    except Exception as exc:  # noqa: BLE001
        _log.warning("stress.process_error", error=str(exc), text_len=len(text))
        return text


def reset() -> None:
    """Сбросить синглтон (для тестов)."""
    global _ACCENTIZER, _AVAILABLE
    _ACCENTIZER = None
    _AVAILABLE = None
