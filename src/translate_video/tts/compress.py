"""LLM-сжатие перевода когда TTS-озвучка не умещается в слот (TVIDEO-037).

Алгоритм:
1. _get_audio_duration() — ffprobe для измерения длительности mp3/wav
2. compress_via_llm() — запрос к Ollama (qwen3.5:9b) для сжатия текста
   с сохранением смысла
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Таймаут запроса к Ollama в секундах
_OLLAMA_TIMEOUT = 45

# Промпт для сжатия. {target_sec}, {current_sec}, {text} — подставляются.
_COMPRESS_PROMPT = """\
Ты редактор перевода. Сократи следующий перевод так, чтобы его озвучка \
уместилась примерно в {target_sec:.1f} секунд (сейчас {current_sec:.1f}с). \
Сохрани смысл и естественность речи. Убирай лишние слова, \
не сокращай имена и ключевые термины. \
Верни ТОЛЬКО сокращённый текст без кавычек и пояснений.

Текст: {text}"""


def get_audio_duration(path: Path) -> float | None:
    """Получить длительность аудиофайла через ffprobe.

    Возвращает None если ffprobe недоступен или файл некорректен.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            if line.startswith("duration="):
                return float(line.split("=", 1)[1])
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as e:
        logger.debug("ffprobe error for %s: %s", path, e)
    return None


def compress_via_llm(
    text: str,
    current_sec: float,
    target_sec: float,
    model: str,
    ollama_url: str,
) -> str | None:
    """Запросить Ollama сократить перевод с сохранением смысла.

    Возвращает сжатый текст или None если LLM недоступен / не помог.
    Не вызывает исключений — сбои логируются и возвращается None.
    """
    prompt = _COMPRESS_PROMPT.format(
        target_sec=target_sec,
        current_sec=current_sec,
        text=text,
    )
    try:
        resp = requests.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=_OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json().get("response", "").strip()
        # Удаляем возможные кавычки и пустые строки
        result = result.strip('"\'').strip()
        if not result:
            logger.warning("LLM вернул пустой ответ для: %r", text[:60])
            return None
        if len(result) >= len(text):
            logger.info(
                "LLM не сократил текст (было %d → стало %d символов)",
                len(text), len(result),
            )
            return None
        logger.info(
            "LLM сжал: %d → %d символов (цель %.1fс, сейчас %.1fс)",
            len(text), len(result), target_sec, current_sec,
        )
        return result
    except requests.RequestException as e:
        logger.warning("Ollama недоступен (%s): %s", ollama_url, e)
        return None
    except Exception as e:
        logger.error("compress_via_llm unexpected error: %s", e)
        return None
