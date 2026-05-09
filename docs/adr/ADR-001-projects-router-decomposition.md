# ADR-001: Декомпозиция projects.py router

**Статус:** Принято (R13-И5, 2026-05-09)  
**Автор:** System Analyst + CTO agents  
**Контекст:** `projects.py` содержит 2753 строк и 44 endpoint — нарушение SRP, сложность навигации

## Решение

Постепенная декомпозиция на отдельные sub-routers:

### Фаза 1 (R13-И5): Создать export_router
- `src/translate_video/api/routes/export.py` — export-specific endpoints
- URL prefix: `/api/v1/projects` (без изменения — backward compat)
- Переносим: export/zip, export/subtitles-all, export/script, export-audio
- Старые endpoints в projects.py остаются как deprecated aliases на 2 версии

### Фаза 2 (R14): Создать pipeline_router
- `src/translate_video/api/routes/pipeline_ext.py`
- Переносим: /run, /rebuild/subtitles, /bulk-translate, /segments/actions

### Фаза 3 (R15): Создать analytics_router
- `src/translate_video/api/routes/analytics.py`
- Переносим: /stats, /devlog, /analyze-log, /doctor

## Антипаттерны которых избегаем
- НЕ переименовываем URL (backward compat)
- НЕ меняем логику — только перемещение
- НЕ торопимся — каждый перенос с тестами

## Критерии успеха
- projects.py < 1500 строк после Фазы 2
- 0 сломанных тестов
- Все старые URL продолжают работать
