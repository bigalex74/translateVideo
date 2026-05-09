# Release Notes v1.98.8 — Раунд 15 (2026-05-09)

## Что нового

### 🎯 UX — Пагинация Dashboard (И1)
**Для кого:** Алексей (50+ проектов), Мария (10-20 проектов), Дмитрий
- Dashboard теперь загружает страницами по 20 проектов
- Controls: ← Назад | 2 / 5 | Вперёд → (только если >20 проектов)
- Счётчик "Показано 20 из 47" / "Всего проектов: 8"
- Сброс на стр.1 при смене сортировки или поиска

### 🏗️ Архитектура — ADR-001 Фаза 2 (И2)
- `projects.py` сокращён: 2753 → ~2640 строк
- Новый `segments.py`: PUT /segments, PUT /config, GET /devlog, GET /stats

### 💬 UX — Понятные ошибки (И3)
**До:** `422 Unprocessable Entity`
**После:** `Ошибка валидации данных. Проверьте формат файла или параметры.`
Маппинг для HTTP 400/401/403/404/422/429/500/502/503

### 🔍 DevOps — Health/Detailed (И4)
**GET /api/health/detailed** — для Prometheus/Grafana/мониторинга:
```json
{
  "status": "ok",
  "components": {
    "filesystem": {"status": "ok", "writable": true},
    "disk": {"status": "ok", "free_gb": 138.08},
    "queue": {"running_projects": 0},
    "memory": {"rss_mb": 156.2}
  }
}
```

### 📦 API — Batch Upload (И5)
**POST /api/v1/projects/batch/upload** — загрузка до 10 файлов одним запросом:
- `multipart/form-data`: files[] + auto_run
- 207 Multi-Status: {results, total, created, errors}
- Форматы: mp4/avi/mov/mkv/webm/mp3/wav/m4a/aac/ogg

## Технические показатели
- Версия: 1.98.8
- Тестов: 981 (OK, skipped=2)
- Коммитов: 5 (И1-И5)
