"""deep-translator адаптер перевода сегментов.

Стратегия "Единый текст":
1. Объединить source_text всех сегментов в один связный параграф.
2. Перевести одним запросом — переводчик видит полный контекст.
3. Выровнять переведённый текст обратно по сегментам через
   жадный алгоритм по предложениям.
4. Fallback на поштучный перевод при любой ошибке выравнивания.
"""

from __future__ import annotations

import re

from translate_video.core.schemas import Segment

# Максимальная длина одного запроса (Google Translate ~5000 символов).
_MAX_CHARS = 4500

# Знаки конца предложения для разбивки переведённого текста.
_SENTENCE_END = re.compile(r'(?<=[.!?…])\s+')


class GoogleSegmentTranslator:
    """Переводит сегменты через `deep-translator` GoogleTranslator.

    Алгоритм единого контекстного перевода:
    1. Объединяем все source_text через пробел в единый текст.
    2. Переводим одним запросом — контекст сохраняется.
    3. Разбиваем результат на предложения.
    4. Жадно распределяем предложения по сегментам пропорционально
       длине исходного текста.
    5. Fallback на поштучный перевод при несовпадении.
    """

    def __init__(self, translator_factory=None) -> None:
        self.translator_factory = translator_factory or _google_translator

    def translate(self, segments: list[Segment], config) -> list[Segment]:
        """Перевести сегменты на целевой язык проекта."""

        if not segments:
            return []

        translator = self.translator_factory(
            source=config.source_language,
            target=config.target_language,
        )

        # Разделяем на батчи по длине символов
        batches = _make_batches(segments)
        translated_texts: list[str] = []

        for batch in batches:
            batch_result = _translate_batch(batch, translator)
            translated_texts.extend(batch_result)

        return _apply_translations(segments, translated_texts)


# ─── Батчинг ────────────────────────────────────────────────────────────────

def _make_batches(segments: list[Segment]) -> list[list[Segment]]:
    """Разбить сегменты на батчи ≤ MAX_CHARS символов."""
    batches: list[list[Segment]] = []
    current: list[Segment] = []
    current_len = 0

    for seg in segments:
        text_len = len(seg.source_text) + 1  # +1 на пробел-разделитель
        if current and current_len + text_len > _MAX_CHARS:
            batches.append(current)
            current = []
            current_len = 0
        current.append(seg)
        current_len += text_len

    if current:
        batches.append(current)

    return batches


# ─── Перевод батча ───────────────────────────────────────────────────────────

def _translate_batch(segments: list[Segment], translator) -> list[str]:
    """Перевести батч единым текстом с выравниванием по сегментам.

    При любой ошибке — fallback поштучно.
    """
    if len(segments) == 1:
        text = segments[0].source_text.strip()
        try:
            result = translator.translate(text) if text else ""
        except Exception:  # noqa: BLE001
            result = text
        return [result or ""]

    # Объединяем в единый текст
    combined = " ".join(seg.source_text.strip() for seg in segments)

    try:
        translated = translator.translate(combined) or ""
    except Exception:  # noqa: BLE001
        return _translate_one_by_one(segments, translator)

    if not translated.strip():
        return _translate_one_by_one(segments, translator)

    # Выравниваем переведённый текст по сегментам
    result = _align_translation(translated, segments)
    if result is not None:
        return result

    return _translate_one_by_one(segments, translator)


# ─── Выравнивание ────────────────────────────────────────────────────────────

def _align_translation(translated: str, segments: list[Segment]) -> list[str] | None:
    """Распределить переведённый текст по сегментам жадным алгоритмом.

    Алгоритм:
    1. Разбить переведённый текст на предложения.
    2. Вычислить целевую длину текста для каждого сегмента пропорционально
       длине исходника.
    3. Жадно добавлять предложения в сегмент пока не достигнем целевой длины.
    """
    sentences = _split_sentences(translated)
    if not sentences:
        return None

    n = len(segments)
    total_source_len = sum(len(s.source_text) for s in segments)
    if total_source_len == 0:
        return None

    total_translated_len = len(translated)

    result = []
    sent_idx = 0

    for seg_idx, seg in enumerate(segments):
        # Последний сегмент берёт все оставшиеся предложения
        if seg_idx == n - 1:
            result.append(" ".join(sentences[sent_idx:]).strip())
            break

        # Целевая длина текста для этого сегмента (пропорционально)
        target_len = (len(seg.source_text) / total_source_len) * total_translated_len

        seg_text_parts = []
        accumulated = 0

        while sent_idx < len(sentences):
            s = sentences[sent_idx]
            seg_text_parts.append(s)
            accumulated += len(s) + 1
            sent_idx += 1
            # Берём хотя бы одно предложение и останавливаемся когда достигли цели
            if accumulated >= target_len * 0.7:
                break

        result.append(" ".join(seg_text_parts).strip())

    # Если что-то пошло не так
    if len(result) != n:
        return None

    return result


def _split_sentences(text: str) -> list[str]:
    """Разбить текст на предложения по знакам препинания."""
    parts = _SENTENCE_END.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


# ─── Поштучный fallback ──────────────────────────────────────────────────────

def _translate_one_by_one(segments: list[Segment], translator) -> list[str]:
    """Поштучный перевод (fallback)."""
    results = []
    for seg in segments:
        text = seg.source_text.strip()
        try:
            translated = translator.translate(text) if text else ""
        except Exception:  # noqa: BLE001
            translated = text
        results.append(translated or "")
    return results


# ─── Apply ───────────────────────────────────────────────────────────────────

def _apply_translations(segments: list[Segment], texts: list[str]) -> list[Segment]:
    """Применить переведённые тексты к сегментам."""
    result = []
    for seg, translated_text in zip(segments, texts):
        qa_flags = list(seg.qa_flags)
        source = seg.source_text.strip()
        translated = translated_text.strip()
        if not translated:
            qa_flags.append("translation_empty")
        elif source and translated == source:
            qa_flags.append("translation_fallback_source")
        result.append(
            Segment(
                id=seg.id,
                start=seg.start,
                end=seg.end,
                source_text=seg.source_text,
                translated_text=translated_text,
                speaker_id=seg.speaker_id,
                confidence=seg.confidence,
                qa_flags=qa_flags,
            )
        )
    return result


def _google_translator(*args, **kwargs):
    """Лениво импортировать `deep-translator`."""

    from deep_translator import GoogleTranslator

    return GoogleTranslator(*args, **kwargs)
