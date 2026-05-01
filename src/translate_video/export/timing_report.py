"""Генерация отчёта по таймингам сегментов перевода."""

from __future__ import annotations

from typing import Any

from translate_video.core.schemas import Segment


def build_timing_report(segments: list[Segment]) -> dict[str, Any]:
    """
    Построить JSON-совместимый отчёт по таймингам сегментов.

    Возвращаемые поля верхнего уровня:
    - ``total_segments``: общее количество сегментов.
    - ``translated_count``: сегменты с непустым переведенным текстом.
    - ``empty_count``: сегменты с пустым переводом.
    - ``total_duration``: суммарная длительность всех сегментов (с).
    - ``avg_duration``: средняя длительность сегмента (с).
    - ``min_duration``: минимальная длительность сегмента (с).
    - ``max_duration``: максимальная длительность сегмента (с).
    - ``segments``: детальная таблица по каждому сегменту.
    """

    if not segments:
        return {
            "total_segments": 0,
            "translated_count": 0,
            "empty_count": 0,
            "total_duration": 0.0,
            "avg_duration": 0.0,
            "min_duration": 0.0,
            "max_duration": 0.0,
            "segments": [],
        }

    durations = [s.duration for s in segments]
    translated_count = sum(1 for s in segments if s.translated_text.strip())
    empty_count = len(segments) - translated_count

    detail_rows = []
    for seg in segments:
        chars_source = len(seg.source_text)
        chars_translated = len(seg.translated_text)
        # Символов в секунду по переведенному тексту (0 если нет перевода)
        chars_per_sec = round(chars_translated / seg.duration, 2) if seg.duration > 0 else 0.0
        detail_rows.append(
            {
                "id": seg.id,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "duration": round(seg.duration, 3),
                "chars_source": chars_source,
                "chars_translated": chars_translated,
                "chars_per_sec": chars_per_sec,
                "status": seg.status,
            }
        )

    return {
        "total_segments": len(segments),
        "translated_count": translated_count,
        "empty_count": empty_count,
        "total_duration": round(sum(durations), 3),
        "avg_duration": round(sum(durations) / len(durations), 3),
        "min_duration": round(min(durations), 3),
        "max_duration": round(max(durations), 3),
        "segments": detail_rows,
    }
