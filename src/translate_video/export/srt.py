"""Генерация SRT-субтитров из списка сегментов перевода."""

from __future__ import annotations

from translate_video.core.schemas import Segment


def _format_srt_time(seconds: float) -> str:
    """Преобразовать секунды в формат таймкода SRT (HH:MM:SS,mmm)."""

    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments: list[Segment]) -> str:
    """
    Сгенерировать строку SRT-субтитров из списка сегментов.

    Источник текста: ``translated_text`` если непустой, иначе ``source_text``.
    Сегменты с пустым итоговым текстом пропускаются.
    """

    lines: list[str] = []
    index = 1
    for segment in segments:
        text = (segment.translated_text or segment.source_text).strip()
        if not text:
            continue
        start = _format_srt_time(segment.start)
        end = _format_srt_time(segment.end)
        lines.append(f"{index}\n{start} --> {end}\n{text}\n")
        index += 1
    return "\n".join(lines)
