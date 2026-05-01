"""deep-translator адаптер перевода сегментов (TVIDEO-038).

Стратегия «Маркер-разделитель»:
1. Объединить source_text сегментов через разделитель |||.
2. Перевести одним запросом — переводчик видит весь контекст.
3. Разбить результат обратно по ||| → ровно 1 перевод на 1 сегмент.
4. Проверить количество частей: len(parts) == len(segments).
5. Fallback на поштучный перевод при любом несоответствии.

Преимущество перед старым «единым текстом»:
Маркер сохраняется при переводе, поэтому результат всегда
точно соответствует количеству сегментов — нет рассинхрона.
"""

from __future__ import annotations

import logging
import re

from translate_video.core.schemas import Segment

logger = logging.getLogger(__name__)

# Максимальная длина одного запроса (Google Translate ~5000 символов).
_MAX_CHARS = 4500

# Разделитель между сегментами. Google Translate сохраняет |||.
# Пробелы вокруг важны — без них переводчик может слить слова.
_SEP = " ||| "

# Паттерн для нормализации разделителя после перевода:
# Переводчик может вернуть | || |, |||, || |, |  |  | и т.п.
_SEP_RE = re.compile(r"\s*\|{2,3}\s*")


class GoogleSegmentTranslator:
    """Переводит сегменты через `deep-translator` GoogleTranslator.

    Алгоритм маркера-разделителя:
    1. Группируем сегменты в батчи по _MAX_CHARS.
    2. Внутри батча объединяем через |||.
    3. Переводим одним запросом.
    4. Разбиваем по ||| обратно — гарантируем 1:1.
    5. При несоответствии — fallback поштучно для этого батча.
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

        batches = _make_batches(segments)
        translated_texts: list[str] = []

        for batch in batches:
            batch_result = _translate_batch(batch, translator)
            translated_texts.extend(batch_result)

        return _apply_translations(segments, translated_texts)


# ─── Батчинг ────────────────────────────────────────────────────────────────

def _make_batches(segments: list[Segment]) -> list[list[Segment]]:
    """Разбить сегменты на батчи ≤ MAX_CHARS символов.

    Учитывает длину разделителя при подсчёте.
    """
    batches: list[list[Segment]] = []
    current: list[Segment] = []
    current_len = 0

    for seg in segments:
        # +len(_SEP) на разделитель между сегментами
        text_len = len(seg.source_text) + len(_SEP)
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
    """Перевести батч через маркер ||| с fallback на поштучный.

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

    # Маркер потерян или количество не совпало → fallback
    logger.warning(
        "Маркер ||| не сохранился после перевода → поштучный fallback (%d сегм.)",
        len(segments),
    )
    return _translate_one_by_one(segments, translator)


def _split_by_separator(translated: str, expected: int) -> list[str] | None:
    """Разбить переведённый текст по маркеру ||| и проверить количество.

    Возвращает список из `expected` строк или None если не получилось.
    Пустые части сохраняются — они могут быть законными пустыми переводами.
    """
    parts = [p.strip() for p in _SEP_RE.split(translated)]
    # Убираем пустые артефакты только в начале и конце
    while parts and not parts[0]:
        parts.pop(0)
    while parts and not parts[-1]:
        parts.pop()

    if len(parts) == expected:
        return parts

    # Иногда переводчик добавляет/убирает один разделитель
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
