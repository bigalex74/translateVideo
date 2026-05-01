"""Подгонка текста под естественную скорость речи без ускорения аудио."""

from __future__ import annotations

import re

from translate_video.core.schemas import Segment, VideoProject
from translate_video.timing.base import TimingRewriter


class NaturalVoiceTimingFitter:
    """Сокращает перевод до TTS, не меняя скорость будущей озвучки."""

    def __init__(self, rewriter: TimingRewriter | None = None) -> None:
        self.rewriter = rewriter

    def fit(self, project: VideoProject, segments: list[Segment]) -> list[Segment]:
        """Подготовить `tts_text` и при необходимости сократить `translated_text`.

        Реальный облачный rewriter будет подключён тем же контрактом. Сейчас
        используется безопасный rule-based слой: он удаляет очевидные вводные
        слова и заменяет длинные обороты, но не делает жёсткую обрезку.
        """

        cfg = project.config
        rewriter = self.rewriter or _build_default_rewriter(cfg)
        target_cps = max(1.0, float(cfg.target_chars_per_second))
        max_attempts = max(0, int(cfg.timing_fit_max_rewrites))

        for segment in segments:
            text = segment.translated_text.strip()
            segment.tts_text = text
            if not text:
                continue
            if segment.duration <= 0:
                _add_qa_flag(segment, "timing_fit_invalid_slot")
                continue

            max_chars = max(1, int(segment.duration * target_cps))
            if len(text) <= max_chars:
                continue

            candidate = text
            for attempt in range(1, max_attempts + 1):
                rewritten = rewriter.rewrite(
                    candidate,
                    source_text=segment.source_text,
                    max_chars=max_chars,
                    attempt=attempt,
                ).strip()
                _apply_rewriter_events(segment, rewriter)
                if not rewritten or rewritten == candidate:
                    break
                candidate = rewritten
                if len(candidate) <= max_chars:
                    break

            if candidate != text:
                segment.translated_text = candidate
                segment.tts_text = candidate
                _add_qa_flag(segment, "translation_rewritten_for_timing")

            if len(candidate) > max_chars:
                _add_qa_flag(segment, "timing_fit_failed")

        return segments


class RuleBasedTimingRewriter:
    """Безопасный базовый rewriter без внешних моделей.

    Он намеренно консервативен: лучше оставить фразу длинной и поставить
    `timing_fit_failed`, чем удалить смысл ради попадания в лимит.
    """

    _PHRASE_REPLACEMENTS = (
        ("на сегодняшний день", "сейчас"),
        ("в настоящее время", "сейчас"),
        ("по той причине, что", "потому что"),
        ("в том случае, если", "если"),
        ("для того чтобы", "чтобы"),
        ("таким образом", "так"),
        ("с точки зрения", "для"),
        ("имеет возможность", "может"),
        ("является важным", "важно"),
        ("необходимо", "нужно"),
    )
    _FILLERS = (
        "собственно",
        "буквально",
        "просто",
        "довольно",
        "действительно",
        "на самом деле",
        "как бы",
    )

    def rewrite(
        self,
        text: str,
        *,
        source_text: str,
        max_chars: int,
        attempt: int,
    ) -> str:
        """Вернуть сокращённый вариант без жёсткой обрезки."""

        candidate = text.strip()
        if attempt >= 1:
            candidate = self._replace_phrases(candidate)
        if attempt >= 2:
            candidate = self._remove_fillers(candidate)
        if attempt >= 3:
            candidate = self._compact_punctuation(candidate)
        return _normalize_spaces(candidate)

    def _replace_phrases(self, text: str) -> str:
        """Заменить длинные устойчивые обороты короткими эквивалентами."""

        result = text
        for source, replacement in self._PHRASE_REPLACEMENTS:
            result = re.sub(source, replacement, result, flags=re.IGNORECASE)
        return result

    def _remove_fillers(self, text: str) -> str:
        """Удалить вводные слова, которые обычно не несут ключевого смысла."""

        result = text
        for filler in self._FILLERS:
            result = re.sub(rf"\b{re.escape(filler)}\b[,]?\s*", "", result, flags=re.IGNORECASE)
        return result

    def _compact_punctuation(self, text: str) -> str:
        """Убрать лишние паузы вокруг пунктуации."""

        return re.sub(r"\s*([,;:])\s*", r"\1 ", text)


def _normalize_spaces(text: str) -> str:
    """Свести повторяющиеся пробелы к одному и поправить пробелы перед знаками."""

    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([,.!?;:])", r"\1", text)


def _add_qa_flag(segment: Segment, flag: str) -> None:
    """Добавить QA-флаг без дублей."""

    if flag not in segment.qa_flags:
        segment.qa_flags.append(flag)


def _apply_rewriter_events(segment: Segment, rewriter: TimingRewriter) -> None:
    """Перенести QA-события rewriter-а в сегмент, если он их поддерживает."""

    consume = getattr(rewriter, "consume_events", None)
    if consume is None:
        return
    for flag in consume():
        _add_qa_flag(segment, flag)


def _build_default_rewriter(config) -> TimingRewriter:
    """Собрать дефолтный rewriter с облачным роутером или rule-based fallback."""

    if getattr(config, "use_cloud_timing_rewriter", True):
        # Ленивая загрузка избегает циклического импорта с timing.cloud.
        from translate_video.timing.cloud import CloudFallbackTimingRewriter

        return CloudFallbackTimingRewriter.from_config(config)
    return RuleBasedTimingRewriter()
