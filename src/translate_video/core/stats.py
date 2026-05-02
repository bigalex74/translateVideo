"""Вычисление статистики проекта для панели Stats.

Все расчёты ведутся по уже сохранённым данным VideoProject:
сегментам, stage_runs и конфигурации. Не делает сетевых запросов.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from translate_video.core.schemas import JobStatus, VideoProject


def _words(text: str) -> int:
    """Посчитать слова (юникод, разделитель — пробелы/знаки)."""
    return len(re.findall(r"\S+", text or ""))


def _elapsed(started_at: str | None, finished_at: str | None) -> float | None:
    """Вернуть elapsed_s из ISO-строк или None."""
    if not started_at or not finished_at:
        return None
    try:
        fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
        try:
            s = datetime.strptime(started_at, fmt)
            e = datetime.strptime(finished_at, fmt)
        except ValueError:
            fmt2 = "%Y-%m-%dT%H:%M:%S%z"
            s = datetime.strptime(started_at, fmt2)
            e = datetime.strptime(finished_at, fmt2)
        return round((e - s).total_seconds(), 3)
    except (ValueError, TypeError):
        return None


def compute_project_stats(project: VideoProject) -> dict[str, Any]:
    """Вернуть полную статистику проекта.

    Returns:
        dict со структурой:
        {
          "timing": {...},
          "segments": {...},
          "quality": {...},
          "tts": {...},
          "summary": {...},
        }
    """
    segs = project.segments or []
    runs = project.stage_runs or []

    # ── Временны́е метрики ────────────────────────────────────────────────────
    stage_times: dict[str, float] = {}
    for run in runs:
        if run.status in (JobStatus.COMPLETED, "completed"):
            t = _elapsed(run.started_at, run.finished_at)
            if t is not None:
                stage_times[run.stage if isinstance(run.stage, str) else run.stage.value] = t

    total_elapsed = sum(stage_times.values()) if stage_times else None

    # Находим самый медленный этап
    slowest_stage = max(stage_times, key=stage_times.get) if stage_times else None

    # Среднее время перевода на сегмент
    translate_time = stage_times.get("translate")
    translate_per_seg = (
        round(translate_time / len(segs), 3)
        if translate_time and segs
        else None
    )

    timing = {
        "total_elapsed_s": round(total_elapsed, 1) if total_elapsed else None,
        "stage_times": stage_times,
        "slowest_stage": slowest_stage,
        "translate_per_segment_avg_s": translate_per_seg,
    }

    # ── Сегментная аналитика ─────────────────────────────────────────────────
    source_words = sum(_words(s.source_text) for s in segs)
    target_words = sum(_words(s.translated_text) for s in segs)
    source_chars = sum(len(s.source_text or "") for s in segs)
    target_chars = sum(len(s.translated_text or "") for s in segs)

    durations = [s.duration for s in segs if s.duration > 0]
    avg_duration = round(sum(durations) / len(durations), 2) if durations else None

    compression_ratio = round(target_chars / source_chars, 3) if source_chars > 0 else None

    # Сегменты, у которых tts_text отличается от translated_text (были rewrite)
    segments_rewritten = sum(
        1 for s in segs
        if s.tts_text and s.tts_text.strip() != s.translated_text.strip()
    )

    # Пустые переводы
    empty_translations = sum(1 for s in segs if not (s.translated_text or "").strip())

    segment_stats = {
        "count": len(segs),
        "source_words": source_words,
        "target_words": target_words,
        "source_chars": source_chars,
        "target_chars": target_chars,
        "compression_ratio": compression_ratio,
        "avg_duration_s": avg_duration,
        "total_audio_duration_s": round(sum(durations), 1) if durations else None,
        "segments_rewritten": segments_rewritten,
        "empty_translations": empty_translations,
    }

    # ── Качество перевода ─────────────────────────────────────────────────────
    all_flags: list[str] = []
    for s in segs:
        all_flags.extend(s.qa_flags or [])

    qa_flags_dist = dict(Counter(all_flags).most_common())

    # Сегменты с проблемами (не считаем технические флаги)
    technical_flags = {
        "translation_llm",
        "translation_provider_used",
    }
    problem_flags = {
        k for k in qa_flags_dist
        if not any(k.startswith(p) for p in ("translation_provider_", "translation_llm"))
    }
    segments_with_issues = sum(
        1 for s in segs
        if any(f in problem_flags for f in (s.qa_flags or []))
    )

    # Провайдеры перевода
    provider_usage: dict[str, int] = Counter(
        f.replace("translation_provider_", "")
        for s in segs
        for f in (s.qa_flags or [])
        if f.startswith("translation_provider_") and not f.endswith("_used")
    )

    # Fallback на Google
    google_fallback = sum(
        1 for s in segs
        if "translation_google_fallback" in (s.qa_flags or [])
    )

    # Средний confidence Whisper
    confidences = [s.confidence for s in segs if s.confidence is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else None

    quality = {
        "qa_flags_distribution": qa_flags_dist,
        "segments_with_issues": segments_with_issues,
        "avg_confidence": avg_confidence,
        "provider_usage": dict(provider_usage),
        "google_fallback_count": google_fallback,
        "llm_translation_count": sum(
            1 for s in segs if "translation_llm" in (s.qa_flags or [])
        ),
    }

    # ── TTS метрики ──────────────────────────────────────────────────────────
    tts_segs = [s for s in segs if s.tts_path]
    tts_overflows = sum(
        1 for s in segs
        if "tts_overflow" in (s.qa_flags or [])
        or "timing_overflow" in (s.qa_flags or [])
    )
    tts_durations = [s.duration for s in tts_segs if s.duration > 0]

    tts = {
        "segments_with_audio": len(tts_segs),
        "total_duration_s": round(sum(tts_durations), 1) if tts_durations else None,
        "overflow_count": tts_overflows,
        "overflow_rate": round(tts_overflows / len(segs), 3) if segs else None,
    }

    # ── Итоговая сводка ──────────────────────────────────────────────────────
    status_counts = Counter(
        run.status if isinstance(run.status, str) else run.status.value
        for run in runs
    )
    failed_stages = [
        run.stage if isinstance(run.stage, str) else run.stage.value
        for run in runs
        if run.status in (JobStatus.FAILED, "failed")
    ]

    summary = {
        "project_id": project.id,
        "project_status": (
            project.status if isinstance(project.status, str) else project.status.value
        ),
        "stages_done": status_counts.get("completed", 0),
        "stages_failed": status_counts.get("failed", 0),
        "failed_stages": failed_stages,
        "translation_quality": getattr(project.config, "translation_quality", "amateur"),
        "source_language": getattr(project.config, "source_language", "?"),
        "target_language": getattr(project.config, "target_language", "?"),
        "dev_mode": getattr(project.config, "dev_mode", False),
    }

    return {
        "timing": timing,
        "segments": segment_stats,
        "quality": quality,
        "tts": tts,
        "summary": summary,
        "billing": _compute_billing(project, segment_stats, quality),
    }


# ── Биллинг ────────────────────────────────────────────────────────────────
# Приблизительные цены (USD за 1M токенов, вход / выход).
# Обновляй по актуальным прайс-листам провайдеров.
_PROVIDER_PRICE_USD_PER_1M: dict[str, tuple[float, float]] = {
    "polza":     (0.40, 1.20),   # NeuroAPI / polza, gpt-4o-mini tier
    "neuroapi":  (0.40, 1.20),
    "openrouter": (1.00, 3.00), # средний по popular models
    "aihubmix":  (0.40, 1.20),
    "gemini":    (0.00, 0.00),   # free-tier (Flash)
    "google":    (0.00, 0.00),   # Google Translate — бесплатно
}
# Среднее число символов на токен (смешанный RU/EN текст)
_CHARS_PER_TOKEN = 3.5


def _compute_billing(
    project: "VideoProject",
    segment_stats: dict,
    quality: dict,
) -> dict:
    """Оценить стоимость перевода на основе объёма текста и провайдеров."""

    source_chars: int = segment_stats.get("source_chars", 0)
    target_chars: int = segment_stats.get("target_chars", 0)

    # Оцениваем токены
    input_tokens = int(source_chars / _CHARS_PER_TOKEN)
    output_tokens = int(target_chars / _CHARS_PER_TOKEN)

    # Определяем доминирующего провайдера перевода
    provider_usage: dict = quality.get("provider_usage", {})
    dominant_provider = (
        max(provider_usage, key=provider_usage.get)
        if provider_usage
        else "unknown"
    )
    total_segs: int = segment_stats.get("count", 0) or 1
    google_segs: int = quality.get("google_fallback_count", 0)
    llm_segs: int = total_segs - google_segs

    # Стоимость LLM-перевода (в USD)
    price_in, price_out = _PROVIDER_PRICE_USD_PER_1M.get(
        dominant_provider.lower(), (0.80, 2.40)
    )
    llm_frac = llm_segs / total_segs
    cost_translate = (
        (input_tokens * llm_frac * price_in / 1_000_000)
        + (output_tokens * llm_frac * price_out / 1_000_000)
    )

    # Стоимость timing rewrite (если professional)
    rewrite_cost = 0.0
    rewrite_provider = getattr(project.config, "professional_rewrite_provider", None)
    if rewrite_provider:
        rp_in, rp_out = _PROVIDER_PRICE_USD_PER_1M.get(rewrite_provider.lower(), (0.80, 2.40))
        # rewrite: ~source_chars вход + ~source_chars вывод (shortened)
        rw_in_tok = int(source_chars / _CHARS_PER_TOKEN)
        rw_out_tok = int(source_chars * 0.7 / _CHARS_PER_TOKEN)  # rewrite обычно короче
        rewrite_cost = (
            rw_in_tok * rp_in / 1_000_000
            + rw_out_tok * rp_out / 1_000_000
        )

    total_cost = round(cost_translate + rewrite_cost, 4)

    return {
        "dominant_translation_provider": dominant_provider,
        "rewrite_provider": rewrite_provider,
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "estimated_cost_usd": total_cost,
        "estimated_cost_translate_usd": round(cost_translate, 4),
        "estimated_cost_rewrite_usd": round(rewrite_cost, 4),
        "price_per_1m_in_usd": price_in,
        "price_per_1m_out_usd": price_out,
        "note": "оценка на основе символов/токенов; точные данные недоступны",
    }
