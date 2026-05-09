# 🧠 LESSONS — Дистиллированные уроки агентов

> Обновлено Skill Modernizer | 2026-05-09 v1.98.8 | Тестов: 981

> JS=127,3 KB | /health=0.002828s | utcnow=0 shell=True=0


## Критические правила (читать ВСЕГДА)

- **Тестов:** 981 — не снижать никогда
- **D-RULE-02:** после `make deploy` → chown -R appuser:appuser /app/runs/
- **Правило #11:** новый роутер = тесты В ТОЙ ЖЕ итерации
- **FBA:** каждый раунд минимум 5 персон → R{N}-survey.md → блокирует round-close
- **ИДЕМПОТЕНТНОСТЬ:** проверяй EXISTS перед INSERT везде

## 🔍 QA
- [1.98.8] Порог тестов: 981. Любой PR не должен снижать этот счётчик
- [1.98.8] Smoke test новых endpoints после каждого деплоя: curl -s http://localhost:8002/api/health + все новые пути

## 🚀 DevOps
- [1.98.8] D-RULE-02: после make deploy → docker exec --user root video-translator chown -R appuser:appuser /app/runs/

## 🏗️ CTO/Arch
- [1.98.8] Архитектурный принцип: новый роутер = новый файл = ADR запись. Монолитный projects.py (>1500 строк) — красный флаг

## ⚡ Performance
- [1.98.8] Bundle: JS=127,3 KB gzip, CSS=20,7 KB gzip. Порог: JS < 200 KB. /health: 0.002828s

## R15 — Уроки | 2026-05-09

### [R15-L01] listProjects: возвращать {projects, pagination}, а не просто массив
**Проблема:** При >20 проектах UI загружал ВСЁ сразу — медленно, непонятно сколько.
**Решение:** API возвращает `{projects: [...], pagination: {page, pages, total, page_size}}`.
**Правило:** Любой list-endpoint — добавлять `pagination` объект в ответ.

### [R15-L02] readError() должен скрывать технические HTTP-ошибки
**Проблема:** Пользователи видели "422 Unprocessable Entity" — непонятно что делать.
**Решение:** HTTP_ERROR_MESSAGES маппинг + детект "технических" строк (isTechnical).
**Правило:** FastAPI errors (Unprocessable/Internal Server) → заменять на русский текст.

### [R15-L03] ADR-001: декомпозиция монолита пошаговая — не всё сразу
**Факт:** projects.py (2753 строки) → Фаза 1 export.py → Фаза 2 segments.py.
**Правило:** Выносить по тематической группе (export/segments/etc), не раздробляя случайно.

### [R15-L04] /api/health/detailed — write-probe проверяет writable FS
**Решение:** `test_file.write_text("ok"); test_file.unlink()` — реальная проверка записи.
**Правило:** health check для FS = не просто exists(), а реальный I/O probe.

### [R15-L05] batch/upload — ALLOWED_EXTENSIONS + 207 Multi-Status
**Правило:** Batch endpoints всегда возвращают 207 с {results, total, created, errors}.
Каждый item имеет свой {status: "created"|"error"} — никогда не fail-fast весь batch.
