"""Общие помощники для промптов перевода и адаптации текста."""

from __future__ import annotations

from pathlib import Path

from translate_video.core.config import AdaptationLevel, PipelineConfig, TranslationStyle
from translate_video.core.schemas import Segment


_LANGUAGE_LABELS = {
    "auto": "автоопределение",
    "ru": "русский",
    "en": "английский",
    "de": "немецкий",
    "es": "испанский",
    "fr": "французский",
    "it": "итальянский",
    "pt": "португальский",
    "zh": "китайский",
    "ja": "японский",
    "ko": "корейский",
}

_STYLE_LABELS = {
    TranslationStyle.NEUTRAL: "нейтральный, естественный, без отсебятины",
    TranslationStyle.BUSINESS: "деловой, точный, без разговорных упрощений",
    TranslationStyle.CASUAL: "живой разговорный, но без потери смысла",
    TranslationStyle.HUMOROUS: "с лёгким юмором там, где он не ломает смысл",
    TranslationStyle.EDUCATIONAL: "объясняющий, ясный, удобный для обучения",
    TranslationStyle.CINEMATIC: "кинематографичный, выразительный, но точный",
    TranslationStyle.CHILD_FRIENDLY: "понятный детям, мягкий и безопасный",
}

_ADAPTATION_LABELS = {
    AdaptationLevel.LITERAL: "держаться ближе к буквальному переводу",
    AdaptationLevel.NATURAL: "делать естественную речь на целевом языке",
    AdaptationLevel.LOCALIZED: "локализовать формулировки под целевую аудиторию",
    AdaptationLevel.SHORTENED_FOR_TIMING: "сокращать фразы, если это помогает таймингу",
}


def language_label(code: str) -> str:
    """Вернуть человекочитаемое название языка по коду."""

    normalized = (code or "").strip().lower()
    return _LANGUAGE_LABELS.get(normalized, normalized or "не указан")


def style_label(style: TranslationStyle | str) -> str:
    """Вернуть текстовое описание стиля перевода для промпта."""

    try:
        normalized = TranslationStyle(style)
    except ValueError:
        return str(style)
    return _STYLE_LABELS[normalized]


def adaptation_label(level: AdaptationLevel | str) -> str:
    """Вернуть описание допустимой степени адаптации."""

    try:
        normalized = AdaptationLevel(level)
    except ValueError:
        return str(level)
    return _ADAPTATION_LABELS[normalized]


_PROFANITY_LABELS = {
    "keep": "сохранять нецензурную и грубую лексику без изменений",
    "remove": "заменять нецензурные слова нейтральными эквивалентами",
    "asterisk": "заменять нецензурные слова звёздочками (****)",
}


def profanity_label(policy: str) -> str:
    """Вернуть описание политики нецензурной лексики для промпта."""
    return _PROFANITY_LABELS.get((policy or "").strip().lower(), f"политика: {policy}")


def build_project_directives(config: PipelineConfig) -> str:
    """Собрать проектные требования: языки, стиль, аудитория и термины.

    Для профессионального режима включает полные директивы по стилю,
    адаптации, ненормативной лексике и аудитории.
    Для любительского режима — только языки и список «не переводить»,
    чтобы не перегружать промпт бесплатных моделей лишними инструкциями.
    """

    source = language_label(config.source_language)
    target = language_label(config.target_language)
    lines = [
        f"- Исходный язык: {source}.",
        f"- Целевой язык: {target}.",
    ]

    is_professional = getattr(config, "translation_quality", "amateur") == "professional"

    if is_professional:
        lines += [
            f"- Стиль: {style_label(config.translation_style)}.",
            f"- Адаптация: {adaptation_label(config.adaptation_level)}.",
            f"- Предметная область: {config.terminology_domain}.",
            f"- Целевая аудитория: {config.target_audience}.",
            f"- Ненормативная лексика: {profanity_label(config.profanity_policy)}.",
            f"- Единицы измерения: {config.units_policy}.",
        ]
        if config.preserve_names:
            lines.append("- Имена людей и персонажей сохранять без искажений.")
        if config.preserve_brand_names:
            lines.append("- Названия брендов и продуктов сохранять без искажений.")
    else:
        # Amateur: минимальные директивы — только языки и термины
        lines.append("- Переводи точно, сохраняй смысл и естественность речи.")

    if config.do_not_translate:
        terms = ", ".join(config.do_not_translate)
        lines.append(f"- Не переводить эти термины и имена: {terms}.")

    return "\n".join(lines)


def read_glossary(config: PipelineConfig, *, max_chars: int = 2000) -> str:
    """Прочитать глоссарий проекта, если путь задан и файл доступен."""

    if config.glossary_path is None:
        return ""
    path = Path(config.glossary_path)
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n... [глоссарий обрезан по лимиту промпта]"


def build_glossary_block(config: PipelineConfig) -> str:
    """Вернуть блок глоссария для промпта или явное указание, что его нет."""

    glossary = read_glossary(config)
    if not glossary:
        return "Глоссарий не задан."
    return glossary


def build_context_block(
    *,
    before: list[Segment] | None = None,
    current: Segment | None = None,
    after: list[Segment] | None = None,
    include_translations: bool = True,
) -> str:
    """Сформировать компактный блок соседних сегментов для модели."""

    rows: list[str] = []
    for label, items in (
        ("предыдущий", before or []),
        ("текущий", [current] if current is not None else []),
        ("следующий", after or []),
    ):
        for segment in items:
            rows.append(_format_segment_row(label, segment, include_translations))
    if not rows:
        return "Контекст соседних сегментов отсутствует."
    return "\n".join(rows)


def context_window(segments: list[Segment], index: int, *, size: int = 2) -> tuple[list[Segment], list[Segment]]:
    """Вернуть `size` предыдущих и следующих сегментов вокруг индекса."""

    start = max(0, index - size)
    end = min(len(segments), index + size + 1)
    return segments[start:index], segments[index + 1:end]


def _format_segment_row(label: str, segment: Segment, include_translations: bool) -> str:
    """Отформатировать один сегмент для контекстного блока."""

    timing = f"{segment.start:.2f}-{segment.end:.2f}s"
    source = _compact_line(segment.source_text)
    row = f"- [{label} | {timing}] source: {source}"
    if include_translations and segment.translated_text:
        row += f" | translation: {_compact_line(segment.translated_text)}"
    return row


def _compact_line(text: str, *, limit: int = 280) -> str:
    """Сжать многострочный текст до одной строки для промпта."""

    compacted = " ".join((text or "").split())
    if len(compacted) <= limit:
        return compacted
    return compacted[:limit].rstrip() + "..."
