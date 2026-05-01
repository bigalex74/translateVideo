#!/usr/bin/env python3
"""Анализатор JSON-логов пайплайна translateVideo.

Использование:
    docker logs video-translator 2>&1 | python3 scripts/log_analyze.py
    python3 scripts/log_analyze.py /path/to/app.log
    python3 scripts/log_analyze.py --project my_project  # только один проект
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from typing import Any


def _load_events(source) -> list[dict[str, Any]]:
    """Читать JSON-строки из stdin или файла, пропуская не-JSON."""
    events = []
    for line in source:
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _fmt_s(val: float | None) -> str:
    if val is None:
        return "  —"
    if val < 60:
        return f"{val:6.1f}s"
    return f"{val/60:5.1f}m"


def _bar(ratio: float, width: int = 20) -> str:
    filled = min(int(ratio * width), width)
    return "█" * filled + "░" * (width - filled)


def analyze(events: list[dict], project_filter: str | None = None) -> None:
    # Фильтр по проекту
    if project_filter:
        events = [e for e in events if e.get("project") == project_filter]
        if not events:
            print(f"❌ Нет событий для проекта '{project_filter}'")
            return

    # ── Статистика по этапам ──────────────────────────────────────────────────
    stage_times: dict[str, list[float]] = defaultdict(list)
    stage_fails: dict[str, int] = defaultdict(int)
    pipeline_total: list[float] = []
    pipeline_status: list[str] = []

    for e in events:
        msg = e.get("msg", "")
        if msg == "stage.done" and "elapsed_s" in e:
            stage_times[e["stage"]].append(float(e["elapsed_s"]))
        if msg == "stage.fail":
            stage_fails[e.get("stage", "?")] += 1
        if msg == "pipeline.done" and "total_elapsed_s" in e:
            pipeline_total.append(float(e["total_elapsed_s"]))
            pipeline_status.append(e.get("status", "?"))
        if msg == "api.pipeline_done" and "total_elapsed_s" in e:
            pipeline_total.append(float(e["total_elapsed_s"]))

    print("\n" + "═" * 60)
    print("  📊 АНАЛИЗ ПАЙПЛАЙНА translateVideo")
    print("═" * 60)

    if pipeline_total:
        avg_total = statistics.mean(pipeline_total)
        print(f"\n  Всего запусков: {len(pipeline_total)}")
        print(f"  Среднее время:  {_fmt_s(avg_total)}")
        if len(pipeline_total) > 1:
            print(f"  Мин / Макс:     {_fmt_s(min(pipeline_total))} / {_fmt_s(max(pipeline_total))}")

    if stage_times:
        max_time = max(statistics.mean(v) for v in stage_times.values()) or 1
        order = ["extract_audio", "transcribe", "translate", "timing_fit", "tts", "render"]
        all_stages = list(stage_times.keys())
        sorted_stages = [s for s in order if s in all_stages] + \
                        [s for s in all_stages if s not in order]

        print(f"\n  {'ЭТАП':<20} {'СРЕДНЕЕ':>8}  {'МИН':>7}  {'МАКС':>7}  ОШИБКИ  ГИСТОГРАММА")
        print("  " + "─" * 56)
        for stage in sorted_stages:
            times = stage_times[stage]
            avg = statistics.mean(times)
            fails = stage_fails.get(stage, 0)
            bar = _bar(avg / max_time)
            fail_str = f"  ⚠{fails}" if fails else "     "
            print(f"  {stage:<20} {_fmt_s(avg)} {_fmt_s(min(times))} {_fmt_s(max(times))} {fail_str}  {bar}")

    # ── Cloud rewriter ────────────────────────────────────────────────────────
    rewriter_events = [e for e in events if e.get("msg", "").startswith("rewriter.")]
    if rewriter_events:
        responses = [e for e in rewriter_events if e.get("msg") == "rewriter.response"]
        fallbacks = [e for e in rewriter_events if e.get("msg") == "rewriter.fallback"]
        fails = [e for e in rewriter_events if e.get("msg") == "rewriter.provider_fail"]
        all_fail = [e for e in rewriter_events if e.get("msg") == "rewriter.all_failed"]

        provider_times: dict[str, list[float]] = defaultdict(list)
        provider_fits: dict[str, int] = defaultdict(int)
        provider_count: dict[str, int] = defaultdict(int)
        for e in responses:
            p = e.get("provider", "?")
            provider_times[p].append(float(e.get("elapsed_s", 0)))
            provider_count[p] += 1
            if e.get("fits"):
                provider_fits[p] += 1

        print(f"\n  {'REWRITER ПРОВАЙДЕР':<24} {'ВЫЗОВОВ':>8}  {'СРЕДНЕЕ':>8}  {'УЛОЖИЛИСЬ':>10}")
        print("  " + "─" * 56)
        for p, times in sorted(provider_times.items(), key=lambda x: -len(x[1])):
            avg = statistics.mean(times)
            total = provider_count[p]
            fits = provider_fits[p]
            pct = 100 * fits // total if total else 0
            print(f"  {p:<24} {total:>8}  {_fmt_s(avg)}  {fits:>5}/{total} ({pct}%)")

        if fallbacks:
            print(f"\n  ⚠  Fallback-переключений:  {len(fallbacks)}")
        if all_fail:
            print(f"  🔴 Все провайдеры упали:   {len(all_fail)} раз")
        if fails:
            print(f"  🔴 Ошибки провайдеров:     {len(fails)}")

    # ── TTS overflow ──────────────────────────────────────────────────────────
    tts_overflow = [e for e in events if e.get("msg") == "tts.overflow"]
    tts_segs = [e for e in events if e.get("msg") == "tts.segment"]
    if tts_segs or tts_overflow:
        total_segs = len(tts_segs)
        adapted = sum(1 for e in tts_segs if e.get("adapted"))
        overflows = len(tts_overflow)
        print(f"\n  TTS: {total_segs} сегм. | {adapted} адаптированы | {overflows} переполнений")

    # ── Whisper ───────────────────────────────────────────────────────────────
    slow = [e for e in events if e.get("msg") == "transcribe.slow"]
    done = [e for e in events if e.get("msg") == "transcribe.done"]
    if done:
        for e in done[-3:]:  # последние 3 запуска
            lang = e.get("language", "?")
            dur = e.get("audio_duration_s")
            elapsed = e.get("elapsed_s")
            ratio = round(elapsed / dur, 1) if dur and elapsed else "?"
            print(f"\n  Whisper: {_fmt_s(elapsed)} для {_fmt_s(dur)} аудио  "
                  f"(x{ratio})  lang={lang}")
    if slow:
        print(f"  ⚠  Медленная транскрипция: {len(slow)} раз (нет GPU?)")

    print("\n" + "═" * 60 + "\n")


def main() -> None:
    project_filter: str | None = None
    args = sys.argv[1:]

    if "--project" in args:
        idx = args.index("--project")
        project_filter = args[idx + 1] if idx + 1 < len(args) else None
        args = [a for i, a in enumerate(args) if i != idx and i != idx + 1]

    if args:
        with open(args[0], encoding="utf-8") as f:
            events = _load_events(f)
    else:
        events = _load_events(sys.stdin)

    if not events:
        print("Нет JSON-событий. Убедитесь что LOG_FORMAT=json и передайте логи через stdin.")
        sys.exit(1)

    analyze(events, project_filter)


if __name__ == "__main__":
    main()
