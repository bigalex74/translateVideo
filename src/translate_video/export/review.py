"""Генерация артефакта ревью перевода."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from translate_video.core.schemas import Segment


def build_review_artifact(
    segments: list[Segment],
    config_dict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Построить JSON-совместимый артефакт ревью перевода.

    Возвращаемые поля:
    - ``reviewed_at``: ISO-метка времени генерации.
    - ``config``: конфигурация пайплайна (если передана).
    - ``total_segments``: всего сегментов.
    - ``needs_review_count``: сегментов, требующих ручной проверки.
    - ``segments``: детальный список пар исходного и переведенного текста
      с флагом ``needs_review``.

    Сегмент получает флаг ``needs_review=True`` если:
    - ``translated_text`` пустой, или
    - ``translated_text`` совпадает с ``source_text`` (перевод не применён).
    """

    segment_rows = []
    needs_review_count = 0
    qa_flag_counts: dict[str, int] = {}

    for seg in segments:
        translated = seg.translated_text.strip()
        source = seg.source_text.strip()
        # Перевод не применён: пустой или совпадает с исходником
        needs_review = not translated or translated == source
        if needs_review:
            needs_review_count += 1
        for flag in seg.qa_flags:
            qa_flag_counts[flag] = qa_flag_counts.get(flag, 0) + 1
        segment_rows.append(
            {
                "id": seg.id,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "source_text": seg.source_text,
                "translated_text": seg.translated_text,
                "needs_review": needs_review,
                "qa_flags": list(seg.qa_flags),
                "status": seg.status,
            }
        )

    result: dict[str, Any] = {
        "reviewed_at": datetime.now(UTC).isoformat(),
        "total_segments": len(segments),
        "needs_review_count": needs_review_count,
        "qa_flag_counts": qa_flag_counts,
        "quality_warnings_count": sum(qa_flag_counts.values()),
        "segments": segment_rows,
    }
    if config_dict is not None:
        result["config"] = config_dict
    return result
