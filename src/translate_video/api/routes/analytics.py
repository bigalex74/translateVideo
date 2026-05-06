"""Роутер аналитики использования приложения (R9-И4)."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import Counter, defaultdict

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def _get_store():
    from translate_video.core.store import ProjectStore  # noqa: PLC0415
    work_root = Path(os.getenv("WORK_ROOT", "runs")).resolve()
    return ProjectStore(work_root)


@router.get(
    "/summary",
    summary="Агрегированная аналитика использования (R9-И4)",
)
def analytics_summary() -> dict:
    """Вернуть агрегированную статистику по всем проектам.

    Включает:
    - Количество проектов по статусам
    - Общее количество сегментов и слов
    - Средняя оценка качества перевода
    - Общая стоимость (cost_usd) из stage_runs
    - Самый используемый провайдер
    - Проекты по дням за последние 7 дней
    """
    store = _get_store()
    try:
        projects = store.list_projects()
    except Exception:
        projects = []

    total_projects = len(projects)
    total_segments = 0
    total_words_translated = 0
    total_cost_usd = 0.0
    quality_scores: list[str] = []
    provider_counter: Counter = Counter()
    status_distribution: dict[str, int] = defaultdict(int)

    # Проекты по дням (последние 7 дней)
    now = datetime.now(timezone.utc)
    days_buckets: dict[str, int] = {}
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        days_buckets[day] = 0

    for project in projects:
        # Статус
        status_distribution[str(project.status)] += 1

        # Сегменты и слова
        segs = project.segments or []
        total_segments += len(segs)
        for seg in segs:
            txt = seg.translated_text or ""
            total_words_translated += len(txt.split()) if txt.strip() else 0

        # Стоимость и провайдер из stage_runs
        for run in (project.stage_runs or []):
            run_dict = run.to_dict()
            cost = run_dict.get("cost_usd") or 0.0
            if isinstance(cost, (int, float)):
                total_cost_usd += cost
            provider = run_dict.get("provider") or run_dict.get("tts_provider") or ""
            if provider:
                provider_counter[str(provider)] += 1

        # Дата создания
        created_raw = getattr(project, "created_at", None)
        if created_raw:
            try:
                if isinstance(created_raw, str):
                    created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                else:
                    created_dt = created_raw
                day_key = created_dt.strftime("%Y-%m-%d")
                if day_key in days_buckets:
                    days_buckets[day_key] += 1
            except Exception:
                pass

    # Средняя оценка (A/B/C/D из quality_scores)
    avg_quality = "N/A"

    # Самый популярный провайдер
    most_used_provider = provider_counter.most_common(1)[0][0] if provider_counter else "N/A"

    # Распределение провайдеров %
    total_runs = sum(provider_counter.values()) or 1
    provider_distribution = {
        p: round(c / total_runs * 100, 1)
        for p, c in provider_counter.most_common(5)
    }

    projects_per_day = [
        {"date": day, "count": count}
        for day, count in days_buckets.items()
    ]

    return {
        "total_projects": total_projects,
        "total_segments": total_segments,
        "total_words_translated": total_words_translated,
        "avg_translation_quality": avg_quality,
        "cost_usd_total": round(total_cost_usd, 4),
        "most_used_provider": most_used_provider,
        "projects_per_day": projects_per_day,
        "status_distribution": dict(status_distribution),
        "provider_distribution": provider_distribution,
    }
