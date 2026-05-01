"""Перегруппировка Whisper-сегментов по границам предложений (TVIDEO-039).

Whisper режет аудио произвольно — часто посередине предложения.
regroup_by_sentences() объединяет фрагменты в полные предложения:
  - Граница = текущий сегмент заканчивается на .!?…
  - MAX_SLOT = принудительный сброс буфера если слот слишком длинный
"""

from __future__ import annotations

import re

from translate_video.core.schemas import Segment

# Знаки конца предложения (включая закрывающие кавычки после знака)
_SENTENCE_END = re.compile(r'[.!?…]["»]?\s*$')


def regroup_by_sentences(
    segments: list[Segment],
    max_slot: float = 8.0,
) -> list[Segment]:
    """Объединить Whisper-фрагменты в сегменты уровня предложения.

    Алгоритм:
    1. Накапливаем сегменты в буфер.
    2. При достижении границы предложения (.!?…) — сбрасываем буфер
       в один новый сегмент.
    3. При превышении max_slot — принудительный сброс (предложение
       само по себе слишком длинное).
    4. Остаток в конце → последний сегмент.

    Аргументы:
        segments:  исходные сегменты от Whisper.
        max_slot:  максимальная длительность объединённого слота (сек).

    Возвращает:
        Новый список сегментов с границами по предложениям.
    """
    if not segments:
        return []

    result: list[Segment] = []
    buffer: list[Segment] = []

    for seg in segments:
        # Добавляем в буфер
        buffer.append(seg)

        # Текущая длительность буфера
        buf_duration = buffer[-1].end - buffer[0].start

        # Проверяем: заканчивается ли накопленный текст на границу предложения
        accumulated_text = " ".join(s.source_text.strip() for s in buffer)
        ends_sentence = bool(_SENTENCE_END.search(accumulated_text))

        # Сброс если: граница предложения ИЛИ превысили max_slot
        if ends_sentence or buf_duration >= max_slot:
            result.append(_flush(buffer))
            buffer = []

    # Остаток в конце — сбрасываем всегда
    if buffer:
        result.append(_flush(buffer))

    return result


def _flush(buffer: list[Segment]) -> Segment:
    """Объединить буфер сегментов в один сегмент.

    start = start первого, end = end последнего,
    source_text = тексты через пробел.
    Остальные поля берутся от первого сегмента.
    """
    first = buffer[0]
    last = buffer[-1]
    merged_text = " ".join(s.source_text.strip() for s in buffer)
    return Segment(
        start=first.start,
        end=last.end,
        source_text=merged_text,
        speaker_id=first.speaker_id,
        confidence=first.confidence,
    )
