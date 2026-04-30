"""Предварительные проверки перед реальным запуском пайплайна."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from importlib.util import find_spec
from pathlib import Path
from shutil import which
from typing import Callable


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

    def to_dict(self) -> dict:
        """Вернуть JSON-совместимый отчет."""

        return {
            "input_video": self.input_video,
            "provider": self.provider,
            "ok": self.ok,
            "checks": [check.to_dict() for check in self.checks],
        }


def run_preflight(
    input_video: Path | str,
    provider: str,
    module_finder: Callable[[str], object | None] = find_spec,
    executable_finder: Callable[[str], str | None] = which,
) -> PreflightReport:
    """Проверить готовность файла и окружения к запуску выбранного провайдера."""

    input_path = Path(input_video)
    checks = [_check_input_video(input_path)]
    if provider == "legacy":
        checks.extend(_check_modules(module_finder))
        checks.extend(_check_executables(executable_finder))
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
                message=f"неподдерживаемый провайдер: {provider}",
                details={"provider": provider},
            )
        )
    return PreflightReport(
        input_video=input_path.as_posix(),
        provider=provider,
        ok=all(check.ok for check in checks),
        checks=checks,
    )


def _check_input_video(input_path: Path) -> PreflightCheck:
    """Проверить существование и базовую пригодность входного видео."""

    if not input_path.exists():
        return PreflightCheck(
            name="input_video",
            ok=False,
            message="входной файл не найден",
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
