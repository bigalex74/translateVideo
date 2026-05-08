# system-analyst Review Log

> Формат: каждый запуск агента добавляет секцию сверху
> Запуск: make agent:system-analyst или scripts/run-agent.sh system-analyst

---

---
## System Analyst Review — 2026-05-08 v1.95.9

### Команды:
```bash
grep -c "@router\." src/translate_video/api/routes/projects.py  → 44 endpoints
grep -n "VideoProject\|billing_snapshots" src/translate_video/core/schemas.py | head -5
wc -l src/translate_video/api/routes/projects.py → 2700+
```

### Замечания (10):
| # | Замечание | Файл:строка | 🔴/🟡/🟢 |
|---|-----------|-------------|---------|
| 1 | **projects.py**: 44 endpoints в одном файле — нарушение SRP. Нужно: export_router, billing_router, pipeline_router | `routes/projects.py` | 🔴 |
| 2 | **VideoProject schema**: billing_snapshots добавлено правильно — Optional поле с backward compatibility ✅ | `schemas.py` | 🟢 |
| 3 | **DOCX генерация**: встроена в projects.py вместо отдельного сервиса. Тяжело тестировать изолированно | `projects.py:1681` | 🟡 |
| 4 | **Batch queue**: реализована через React state — правильно для текущего масштаба, но нет персистентности | `Dashboard.tsx` | 🟡 |
| 5 | **API versioning**: /api/v1/ — хорошо. Нужна документация breaking changes при переходе к v2 | `routes/` | 🟡 |
| 6 | **sanitize_project_id**: 5 точек ручного вызова — рекомендую FastAPI dependency injection | `projects.py` | 🟡 |
| 7 | **billing_snapshots тип**: Record<string, number> — ключ это модель AI, значение — стоимость. Документировать | `schemas.py` | 🟡 |
| 8 | **44 endpoints на 1 файл**: растёт быстро (R10 добавил export). Архитектурный риск | `projects.py` | 🔴 |
| 9 | **Webhooks**: webhooks.py отдельный файл — правильная изоляция ✅ | `api/webhooks.py` | 🟢 |
| 10 | **Date handling**: 1 вхождение utcnow() deprecated — перейти на timezone-aware datetime | `projects.py:2652` | 🟡 |

### Подпись: System Analyst АПРУV | 2026-05-08 v1.95.9

---
## SYSTEM-ANALYST Review — 2026-05-08 v1.96.0

### Данные из кода R11:
- VERSION: 1.96.0
- Workspace.tsx: 2141 строк (была 2208)
- ExportPanel: новый компонент 115 строк
- textarea auto-resize: добавлен onInput handler
- 920 Python тестов OK

### АПРУV | 2026-05-08 v1.96.0
