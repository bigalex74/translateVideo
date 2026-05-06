"""Подгонка текста под естественную скорость речи без ускорения аудио."""

from __future__ import annotations

import re

from translate_video.core.log import Timer, get_logger
from translate_video.core.prompting import context_window
from translate_video.core.schemas import Segment, VideoProject
from translate_video.timing.base import TimingProgressCallback, TimingRewriter

_log = get_logger(__name__)


class NaturalVoiceTimingFitter:
    """Сокращает перевод до TTS, не меняя скорость будущей озвучки."""

    def __init__(self, rewriter: TimingRewriter | None = None) -> None:
        self.rewriter = rewriter

    def fit(
        self,
        project: VideoProject,
        segments: list[Segment],
        progress_callback: TimingProgressCallback | None = None,
    ) -> list[Segment]:
        """Подготовить `tts_text` и при необходимости сократить `translated_text`.

        Реальный облачный rewriter будет подключён тем же контрактом. Сейчас
        используется безопасный rule-based слой: он удаляет очевидные вводные
        слова и заменяет длинные обороты, но не делает жёсткую обрезку.
        `progress_callback` вызывается после каждого сегмента, чтобы UI мог
        показывать прогресс долгой облачной подгонки.
        """

        cfg = project.config
        rewriter = self.rewriter or _build_default_rewriter(cfg)
        target_cps = max(1.0, float(cfg.target_chars_per_second))
        tts_speed = _effective_tts_speed(cfg)
        # Скорость речи напрямую определяет сколько символов влезает в таймслот:
        # effective_cps = target_cps * tts_speed
        # При speed=1.5 → effective_cps увеличивается на 50%,
        # т.e. в тот же тайминг влезет больше текста и сокращать нужно меньше.
        effective_cps = max(1.0, target_cps * tts_speed)
        max_attempts = max(0, int(cfg.timing_fit_max_rewrites))
        total_segments = len(segments)
        needs_rewrite = 0
        rewritten_count = 0
        failed_count = 0

        _log.info(
            "timing_fit.start",
            project=project.id,
            segments=total_segments,
            target_cps=target_cps,
            tts_speed=tts_speed,
            effective_cps=effective_cps,
            max_attempts=max_attempts,
            cloud_enabled=bool(getattr(cfg, "use_cloud_timing_rewriter", True)),
        )
        _emit_progress(progress_callback, 0, total_segments, "Подготовка сегментов")

        with Timer() as timer:
            for index, segment in enumerate(segments, start=1):
                _emit_progress(
                    progress_callback,
                    index - 1,
                    total_segments,
                    f"Сегмент {index}/{total_segments}",
                )
                was_rewritten, failed = self._fit_segment(
                    segment,
                    rewriter=rewriter,
                    target_cps=effective_cps,  # ← уже скорректированный на скорость TTS
                    max_attempts=max_attempts,
                    index=index,
                    total_segments=total_segments,
                    project_id=project.id,
                    segments=segments,
                    config=cfg,
                )
                if was_rewritten or failed:
                    needs_rewrite += 1
                if was_rewritten:
                    rewritten_count += 1
                if failed:
                    failed_count += 1
                _emit_progress(
                    progress_callback,
                    index,
                    total_segments,
                    f"Готово {index}/{total_segments}",
                )

        _log.info(
            "timing_fit.done",
            project=project.id,
            elapsed_s=timer.elapsed,
            segments=total_segments,
            touched_segments=needs_rewrite,
            rewritten_segments=rewritten_count,
            failed_segments=failed_count,
        )
        return segments

    def _fit_segment(
        self,
        segment: Segment,
        *,
        rewriter: TimingRewriter,
        target_cps: float,
        max_attempts: int,
        index: int,
        total_segments: int,
        project_id: str,
        segments: list[Segment],
        config,
    ) -> tuple[bool, bool]:
        """Подогнать один сегмент и вернуть признаки изменения/неудачи."""

        text = segment.translated_text.strip()
        segment.tts_text = text
        if not text:
            return False, False
        if segment.duration <= 0:
            _add_qa_flag(segment, "timing_fit_invalid_slot")
            return False, True

        max_chars = max(1, int(segment.duration * target_cps))
        if len(text) <= max_chars:
            return False, False

        _log.info(
            "timing_fit.segment_start",
            project=project_id,
            segment=segment.id,
            index=index,
            total=total_segments,
            chars=len(text),
            max_chars=max_chars,
            duration_s=round(segment.duration, 3),
        )

        candidate = text
        context_before, context_after = context_window(segments, index - 1, size=2)
        for attempt in range(1, max_attempts + 1):
            with Timer() as rewrite_timer:
                rewritten = rewriter.rewrite(
                    candidate,
                    source_text=segment.source_text,
                    max_chars=max_chars,
                    attempt=attempt,
                    segment=segment,
                    context_before=context_before,
                    context_after=context_after,
                    config=config,
                ).strip()
            _log.info(
                "timing_fit.rewrite_attempt",
                project=project_id,
                segment=segment.id,
                attempt=attempt,
                elapsed_s=rewrite_timer.elapsed,
                in_chars=len(candidate),
                out_chars=len(rewritten),
                fits=len(rewritten) <= max_chars if rewritten else False,
            )
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
            _log.warning(
                "timing_fit.segment_failed",
                project=project_id,
                segment=segment.id,
                chars=len(candidate),
                max_chars=max_chars,
            )
            return candidate != text, True

        return candidate != text, False


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
        segment: Segment | None = None,
        context_before: list[Segment] | None = None,
        context_after: list[Segment] | None = None,
        config=None,
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


def _effective_tts_speed(config) -> float:
    """Вернуть эффективный мультипликатор скорости TTS для timing_fit.

    Для режима single/per_speaker — просто speed_1.
    Для two_voices — минимальная из двух скоростей (консервативная оценка —
    оба голоса должны влазать, даже более медленный).

    Для Edge TTS (нет профессионального TTS) скорость = 1.0.
    """
    # Внешний (Edge/бесплатный) провайдер не поддерживает speed-хинт
    provider = getattr(config, "professional_tts_provider", "").strip().lower()
    if provider != "yandex":
        return 1.0

    speed_1 = max(0.1, float(getattr(config, "professional_tts_speed",   1.0)))
    strategy = getattr(config, "voice_strategy", "single")
    if strategy == "two_voices":
        speed_2 = max(0.1, float(getattr(config, "professional_tts_speed_2", 1.0)))
        return min(speed_1, speed_2)  # консервативно: берём минимум
    return speed_1


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


def _emit_progress(
    callback: TimingProgressCallback | None,
    current: int,
    total: int,
    message: str,
) -> None:
    """Безопасно отправить прогресс этапа без остановки пайплайна."""

    if callback is None:
        return
    try:
        callback(current, total, message)
    except Exception as exc:  # noqa: BLE001 - прогресс не должен валить перевод.
        _log.warning("timing_fit.progress_failed", error=str(exc))


def _build_default_rewriter(config) -> TimingRewriter:
    """Собрать дефолтный rewriter с облачным роутером или rule-based fallback."""

    if getattr(config, "use_cloud_timing_rewriter", True):
        # Ленивая загрузка избегает циклического импорта с timing.cloud.
        from translate_video.timing.cloud import CloudFallbackTimingRewriter

        return CloudFallbackTimingRewriter.from_config(config)
    return RuleBasedTimingRewriter()
