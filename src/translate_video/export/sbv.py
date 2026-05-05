"""Генерация YouTube SBV субтитров (Z3.4).

SBV (SubViewer) — нативный формат субтитров YouTube.
Поддерживается также Udemy и некоторыми MOOC-платформами.
Альтернатива: SRT тоже принимает YouTube, но SBV нативен для YouTube Studio.
"""

from __future__ import annotations

from translate_video.core.schemas import Segment


def _sbv_time(seconds: float) -> str:
    """Преобразовать секунды в формат H:MM:SS.mmm (YouTube SBV)."""
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{ms:03d}"


def segments_to_sbv(segments: list[Segment]) -> str:
    """Сгенерировать YouTube SBV субтитры из сегментов.

    Формат:
        H:MM:SS.mmm,H:MM:SS.mmm
        Текст субтитра

        (пустая строка между блоками)

    Args:
        segments: список сегментов с переводом

    Returns:
        str: готовый SBV-контент для загрузки в YouTube Studio
    """
    blocks: list[str] = []
    for seg in segments:
        text = (seg.translated_text or seg.source_text or "").strip()
        if not text:
            continue
        start = _sbv_time(seg.start)
        end = _sbv_time(seg.end)
        blocks.append(f"{start},{end}\n{text}")
    return "\n\n".join(blocks) + "\n"
