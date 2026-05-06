"""Предварительные проверки перед реальным запуском пайплайна."""

from __future__ import annotations

import subprocess
import os
from dataclasses import asdict, dataclass, field
from importlib.util import find_spec
from pathlib import Path
from shutil import which
from typing import Callable

from translate_video.core.env import load_env_file


LEGACY_MODULES = {
    "moviepy": "MoviePy для чтения и рендера видео",
    "faster_whisper": "faster-whisper для распознавания речи",
    "deep_translator": "deep-translator для перевода текста",
    "edge_tts": "edge-tts для синтеза речи",
    "pydub": "pydub для аудио-операций",
}

LEGACY_EXECUTABLES = {
    "ffmpeg": "FFmpeg для обработки медиа",
    "ffprobe": "FFprobe для анализа медиа",
}

TIMING_REWRITE_ENV = {
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "aihubmix": "AIHUBMIX_API_KEY",
    "polza": "POLZA_API_KEY",
}


@dataclass(slots=True)
class PreflightCheck:
    """Одна атомарная проверка окружения или входного файла."""

    name: str
    ok: bool
    message: str
    details: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Вернуть JSON-совместимое представление проверки."""

        return asdict(self)


@dataclass(slots=True)
class PreflightReport:
    """Итоговый отчет предварительной проверки запуска."""

    input_video: str
    provider: str
    ok: bool
    checks: list[PreflightCheck]
    duration_seconds: float | None = None
    cost_estimate: dict | None = None           # {"translation_usd": float, "tts_usd": float, "total_usd": float}
    duration_estimate_seconds: float | None = None  # ETA всего пайплайна

    def to_dict(self) -> dict:
        """Вернуть JSON-совместимый отчет."""

        return {
            "input_video": self.input_video,
            "provider": self.provider,
            "ok": self.ok,
            "duration_seconds": self.duration_seconds,
            "cost_estimate": self.cost_estimate,
            "duration_estimate_seconds": self.duration_estimate_seconds,
            "checks": [check.to_dict() for check in self.checks],
        }


# ── Таблицы оценки стоимости и времени ───────────────────────────────────────

# Приблизительная стоимость перевода: $ за 1000 символов
_TRANSLATION_USD_PER_1K: dict[str, float] = {
    "deepseek":  0.0007,
    "neuroapi":  0.002,
    "polza":     0.002,
    "legacy":    0.0,   # локальный / бесплатный
    "fake":      0.0,
}

# Приблизительная стоимость TTS: $ за минуту аудио
_TTS_USD_PER_MIN: dict[str, float] = {
    "polza":     0.012,   # OpenAI через Polza
    "neuroapi":  0.010,
    "yandex":    0.005,
    "legacy":    0.0,     # Edge TTS — бесплатно
    "fake":      0.0,
}

# Коэффициент длительности пайплайна (реальное время / длина видео)
_PIPELINE_TIME_FACTOR: dict[str, float] = {
    "deepseek":  0.45,
    "neuroapi":  0.60,
    "polza":     0.55,
    "legacy":    1.20,
    "fake":      0.05,
}


def _estimate_cost_and_duration(
    duration_sec: float,
    provider: str,
) -> tuple[dict, float]:
    """Оценить примерную стоимость и время обработки.

    Расчёт очень грубый — используется только для UX-подсказки пользователю.
    Точность ±50% в зависимости от плотности речи и длины предложений.

    Возвращает:
        (cost_dict, eta_seconds)
    """
    # ~125 слов/мин × ~6 символов = ~750 символов/мин речи
    chars_per_sec = 12.5
    total_chars = duration_sec * chars_per_sec

    t_price = _TRANSLATION_USD_PER_1K.get(provider, 0.0)
    tts_price = _TTS_USD_PER_MIN.get(provider, 0.0)

    translation_usd = (total_chars / 1000.0) * t_price
    tts_usd = (duration_sec / 60.0) * tts_price
    total_usd = translation_usd + tts_usd

    cost = {
        "translation_usd": round(translation_usd, 4),
        "tts_usd": round(tts_usd, 4),
        "total_usd": round(total_usd, 4),
        "currency": "USD",
        "note": "Приблизительная оценка ±50%",
    }

    factor = _PIPELINE_TIME_FACTOR.get(provider, 0.8)
    eta = duration_sec * factor + 30.0  # +30 сек накладные расходы
    return cost, round(eta)



def _probe_duration(
    input_path: Path,
    executable_finder: Callable[[str], str | None] = which,
) -> float | None:
    """Определить длительность видеофайла через ffprobe.

    Возвращает длительность в секундах или None, если ffprobe недоступен
    или файл не является медиафайлом.
    """

    if executable_finder("ffprobe") is None:
        return None
    if not input_path.is_file():
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        raw = result.stdout.strip()
        return float(raw) if raw else None
    except (ValueError, subprocess.SubprocessError, OSError):
        return None


def run_preflight(
    input_video: Path | str,
    provider: str,
    module_finder: Callable[[str], object | None] = find_spec,
    executable_finder: Callable[[str], str | None] = which,
) -> PreflightReport:
    """Проверить готовность файла и окружения к запуску выбранного провайдера."""

    load_env_file()
    input_path = Path(input_video)
    checks = [_check_input_video(input_path)]
    if provider == "legacy":
        checks.extend(_check_modules(module_finder))
        checks.extend(_check_executables(executable_finder))
        checks.extend(_check_timing_rewrite_env())
    elif provider == "fake":
        checks.append(
            PreflightCheck(
                name="provider",
                ok=True,
                message="имитационный провайдер не требует внешних зависимостей",
                details={"provider": provider},
            )
        )
    else:
        checks.append(
            PreflightCheck(
                name="provider",
                ok=False,
                message=f"неизвестный провайдер: {provider!r}",
                details={"provider": provider},
            )
        )
    overall_ok = all(c.ok for c in checks)
    duration = _probe_duration(input_path, executable_finder)
    cost_estimate = None
    eta = None
    if duration is not None:
        cost_estimate, eta = _estimate_cost_and_duration(duration, provider)
    return PreflightReport(
        input_video=str(input_path),
        provider=provider,
        ok=overall_ok,
        checks=checks,
        duration_seconds=duration,
        cost_estimate=cost_estimate,
        duration_estimate_seconds=eta,
    )


def _check_input_video(input_path: Path) -> PreflightCheck:
    """Проверить доступность и непустоту входного файла."""

    if not input_path.exists():
        return PreflightCheck(
            name="input_video",
            ok=False,
            message="файл не найден",
            details={"path": input_path.as_posix()},
        )
    if not input_path.is_file():
        return PreflightCheck(
            name="input_video",
            ok=False,
            message="путь не является файлом",
            details={"path": input_path.as_posix()},
        )
    size = input_path.stat().st_size
    if size <= 0:
        return PreflightCheck(
            name="input_video",
            ok=False,
            message="входной файл пустой",
            details={"path": input_path.as_posix(), "size_bytes": str(size)},
        )
    return PreflightCheck(
        name="input_video",
        ok=True,
        message="входной файл найден",
        details={"path": input_path.as_posix(), "size_bytes": str(size)},
    )


def _check_modules(module_finder: Callable[[str], object | None]) -> list[PreflightCheck]:
    """Проверить Python-модули, нужные провайдерам устаревшего скрипта."""

    checks: list[PreflightCheck] = []
    for module_name, description in LEGACY_MODULES.items():
        installed = module_finder(module_name) is not None
        checks.append(
            PreflightCheck(
                name=f"python_module:{module_name}",
                ok=installed,
                message="модуль доступен" if installed else "модуль не установлен",
                details={"module": module_name, "description": description},
            )
        )
    return checks


def _check_executables(executable_finder: Callable[[str], str | None]) -> list[PreflightCheck]:
    """Проверить системные исполняемые файлы, нужные для медиа-обработки."""

    checks: list[PreflightCheck] = []
    for executable, description in LEGACY_EXECUTABLES.items():
        path = executable_finder(executable)
        checks.append(
            PreflightCheck(
                name=f"executable:{executable}",
                ok=path is not None,
                message="команда доступна" if path else "команда не найдена",
                details={
                    "executable": executable,
                    "description": description,
                    "path": path or "",
                },
            )
        )
    return checks


def _check_timing_rewrite_env() -> list[PreflightCheck]:
    """Показать доступность облачных rewrite-провайдеров для timing_fit."""

    checks: list[PreflightCheck] = []
    for provider, env_name in TIMING_REWRITE_ENV.items():
        present = bool(os.getenv(env_name))
        checks.append(
            PreflightCheck(
                name=f"timing_rewriter:{provider}",
                ok=True,
                message=(
                    "ключ найден"
                    if present
                    else "ключ не задан, провайдер будет пропущен"
                ),
                details={
                    "provider": provider,
                    "env": env_name,
                    "required": "false",
                },
            )
        )
    checks.append(
        PreflightCheck(
            name="timing_rewriter:rule_based",
            ok=True,
            message="локальный безопасный fallback всегда доступен",
            details={"provider": "rule_based"},
        )
    )
    return checks
