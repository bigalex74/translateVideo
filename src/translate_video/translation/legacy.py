"""deep-translator адаптер перевода сегментов (TVIDEO-040a).

Стратегия «Единый контекст»:
1. Объединить все сегменты через ||| в ОДИН запрос — переводчик
   видит весь ролик целиком → связная, естественная речь.
2. Если текст не влезает (> MAX_CHARS) — разбить на смысловые чанки
   по CHUNK_SENTENCES предложений, а не по числу символов.
   Это сохраняет локальный контекст внутри каждого чанка.
3. Разбить результат обратно по ||| → гарантируем 1:1.
4. Fallback на поштучный перевод при потере маркера.

Разница с TVIDEO-038 (старый батчинг по символам):
- БЫЛО: батч = «набери 4500 символов» → резало по середине темы
- СТАЛО: сначала пробуем весь текст, потом чанки по N предложений
"""

from __future__ import annotations

import logging
import re

from translate_video.core.schemas import Segment

logger = logging.getLogger(__name__)

# Жёсткий лимит Google Translate (символов с учётом разделителей).
_MAX_CHARS = 4500

# Размер чанка при превышении лимита (в предложениях/сегментах).
# 12 предложений ≈ 1-2 минуты видео — достаточно для контекста.
_CHUNK_SENTENCES = 12

# Разделитель между сегментами. Google Translate сохраняет |||.
_SEP = " ||| "

# Паттерн для нормализации разделителя после перевода.
_SEP_RE = re.compile(r"\s*\|{2,3}\s*")


class GoogleSegmentTranslator:
    """Переводит сегменты через `deep-translator` GoogleTranslator.

    Алгоритм единого контекста (TVIDEO-040a):
    1. Если весь текст ≤ MAX_CHARS → один запрос, максимальный контекст.
    2. Иначе → чанки по CHUNK_SENTENCES предложений.
    3. Результат разбивается по ||| → 1:1 с сегментами.
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

        # Считаем суммарную длину с разделителями
        total_len = sum(len(s.source_text) + len(_SEP) for s in segments)

        if total_len <= _MAX_CHARS:
            # Весь текст в один запрос — максимальный контекст
            logger.info(
                "Перевод всего текста целиком: %d сегм., %d симв.",
                len(segments), total_len,
            )
            texts = _translate_batch(segments, translator)
        else:
            # Разбиваем по числу предложений, сохраняем локальный контекст
            chunks = _make_sentence_chunks(segments, _CHUNK_SENTENCES)
            logger.info(
                "Текст большой (%d симв.) → %d чанков по ~%d предложений",
                total_len, len(chunks), _CHUNK_SENTENCES,
            )
            texts = []
            for chunk in chunks:
                texts.extend(_translate_batch(chunk, translator))

        return _apply_translations(segments, texts)


# ─── Чанкинг по предложениям ─────────────────────────────────────────────────

def _make_sentence_chunks(
    segments: list[Segment],
    chunk_size: int,
) -> list[list[Segment]]:
    """Разбить сегменты на чанки по chunk_size предложений.

    В отличие от батчинга по символам — не режет по середине темы.
    """
    return [
        segments[i : i + chunk_size]
        for i in range(0, len(segments), chunk_size)
    ]


# ─── Перевод батча ───────────────────────────────────────────────────────────

def _translate_batch(segments: list[Segment], translator) -> list[str]:
    """Перевести группу сегментов через маркер ||| с fallback на поштучный.

    Гарантирует len(result) == len(segments).
    """
    if len(segments) == 1:
        text = segments[0].source_text.strip()
        try:
            result = translator.translate(text) if text else ""
        except Exception:  # noqa: BLE001
            result = text
        return [result or ""]

    combined = _SEP.join(seg.source_text.strip() for seg in segments)

    try:
        translated = translator.translate(combined) or ""
    except Exception:  # noqa: BLE001
        logger.warning("Google Translate упал → поштучный fallback (%d сегм.)", len(segments))
        return _translate_one_by_one(segments, translator)

    if not translated.strip():
        return _translate_one_by_one(segments, translator)

    parts = _split_by_separator(translated, expected=len(segments))
    if parts is not None:
        return parts

    logger.warning(
        "Маркер ||| не сохранился → поштучный fallback (%d сегм.)",
        len(segments),
    )
    return _translate_one_by_one(segments, translator)


def _split_by_separator(translated: str, expected: int) -> list[str] | None:
    """Разбить переведённый текст по маркеру ||| и проверить количество.

    Возвращает список из `expected` строк или None если не получилось.
    Пустые части сохраняются — они могут быть законными пустыми переводами.
    """
    parts = [p.strip() for p in _SEP_RE.split(translated)]
    while parts and not parts[0]:
        parts.pop(0)
    while parts and not parts[-1]:
        parts.pop()

    if len(parts) == expected:
        return parts

    alt = [p.strip() for p in translated.split("|||")]
    while alt and not alt[0]:
        alt.pop(0)
    while alt and not alt[-1]:
        alt.pop()

    if len(alt) == expected:
        return alt

    logger.debug(
        "Разделитель: ожидали %d частей, получили %d (alt: %d). Текст: %r…",
        expected, len(parts), len(alt), translated[:80],
    )
    return None


# ─── Поштучный fallback ──────────────────────────────────────────────────────

def _translate_one_by_one(segments: list[Segment], translator) -> list[str]:
    """Поштучный перевод (fallback при потере маркера)."""
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
