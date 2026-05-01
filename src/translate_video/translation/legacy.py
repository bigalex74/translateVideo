"""deep-translator адаптер перевода сегментов.

Стратегия: объединить все source_text в один запрос (bulk translate)
для сохранения контекста и согласованности перевода.
Fallback: поштучный перевод при несовпадении числа кусков.
"""

from __future__ import annotations

import re

from translate_video.core.schemas import Segment

# Разделитель между сегментами в bulk-запросе.
# Используем числовые маркеры [N] — Google Translate их сохраняет.
_SEG_OPEN = "["
_SEG_CLOSE = "]"

# Максимальная длина одного bulk-запроса (Google Translate ~5000 символов).
_MAX_BULK_CHARS = 4500


class GoogleSegmentTranslator:
    """Переводит сегменты через `deep-translator` GoogleTranslator.

    Алгоритм:
    1. Объединяет все source_text в один запрос с числовыми маркерами [N].
    2. Переводит одним вызовом API → переводчик видит весь контекст.
    3. Разбивает результат обратно по маркерам.
    4. Если разбивка не совпадает — fallback: поштучный перевод.
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

        # Разделяем длинные тексты на батчи ≤ MAX_BULK_CHARS
        batches = _make_batches(segments)

        translated_texts: list[str] = []
        for batch in batches:
            batch_result = _translate_batch(batch, translator)
            translated_texts.extend(batch_result)

        # Если что-то пошло не так — длина не совпадает, уже разрулено внутри
        return _apply_translations(segments, translated_texts)


# ─── Вспомогательные функции ────────────────────────────────────────────────

def _make_batches(segments: list[Segment]) -> list[list[Segment]]:
    """Разбить сегменты на батчи, не превышающие MAX_BULK_CHARS."""
    batches: list[list[Segment]] = []
    current: list[Segment] = []
    current_len = 0

    for seg in segments:
        text_len = len(seg.source_text) + 10  # +10 на маркер [N]
        if current and current_len + text_len > _MAX_BULK_CHARS:
            batches.append(current)
            current = []
            current_len = 0
        current.append(seg)
        current_len += text_len

    if current:
        batches.append(current)

    return batches


def _build_bulk_text(segments: list[Segment]) -> str:
    """Собрать bulk-строку: [1]текст[2]текст..."""
    parts = []
    for i, seg in enumerate(segments, start=1):
        text = seg.source_text.strip()
        parts.append(f"[{i}]{text}")
    return "".join(parts)


def _split_bulk_result(raw: str, n: int) -> list[str] | None:
    """Разбить результат перевода обратно по маркерам [N].

    Возвращает список из n строк или None если разбивка не удалась.
    """
    # Ищем паттерн [число] — Google иногда добавляет пробел: [ 1 ]
    pattern = r"\[\s*\d+\s*\]"
    parts = re.split(pattern, raw)
    # Первый элемент до [1] — обычно пустая строка
    texts = [p.strip() for p in parts if p.strip()]

    if len(texts) == n:
        return texts

    return None


def _translate_batch(segments: list[Segment], translator) -> list[str]:
    """Перевести батч сегментов как один запрос.

    При ошибке разбивки — поштучный fallback.
    """
    if len(segments) == 1:
        # Нет смысла в bulk для одного сегмента
        text = segments[0].source_text.strip()
        result = translator.translate(text) if text else ""
        return [result or ""]

    bulk_text = _build_bulk_text(segments)

    try:
        raw_translation = translator.translate(bulk_text) or ""
    except Exception:  # noqa: BLE001
        # Сеть недоступна или ошибка API — fallback
        return _translate_one_by_one(segments, translator)

    texts = _split_bulk_result(raw_translation, len(segments))

    if texts is not None:
        return texts

    # Fallback: разбивка не удалась — переводим по одному
    return _translate_one_by_one(segments, translator)


def _translate_one_by_one(segments: list[Segment], translator) -> list[str]:
    """Поштучный перевод (fallback)."""
    results = []
    for seg in segments:
        text = seg.source_text.strip()
        try:
            translated = translator.translate(text) if text else ""
        except Exception:  # noqa: BLE001
            translated = text  # В крайнем случае — оставить исходный
        results.append(translated or "")
    return results


def _apply_translations(segments: list[Segment], texts: list[str]) -> list[Segment]:
    """Применить переведённые тексты к сегментам."""
    result = []
    for seg, translated_text in zip(segments, texts):
        result.append(
            Segment(
                id=seg.id,
                start=seg.start,
                end=seg.end,
                source_text=seg.source_text,
                translated_text=translated_text,
                speaker_id=seg.speaker_id,
                confidence=seg.confidence,
            )
        )
    return result


def _google_translator(*args, **kwargs):
    """Лениво импортировать `deep-translator`."""

    from deep_translator import GoogleTranslator

    return GoogleTranslator(*args, **kwargs)
