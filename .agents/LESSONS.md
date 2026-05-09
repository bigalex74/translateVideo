# 🧠 LESSONS — Дистиллированные уроки агентов

> Обновлено Skill Modernizer | 2026-05-09 v1.98.8 | Тестов: 1017

> JS=127,3 KB | /health=0.002821s | utcnow=0 shell=True=0


## Критические правила (читать ВСЕГДА)

- **Тестов:** 1017 — не снижать никогда
- **D-RULE-02:** после `make deploy` → chown -R appuser:appuser /app/runs/
- **Правило #11:** новый роутер = тесты В ТОЙ ЖЕ итерации
- **FBA:** каждый раунд минимум 5 персон → R{N}-survey.md → блокирует round-close
- **ИДЕМПОТЕНТНОСТЬ:** проверяй EXISTS перед INSERT везде

## 🔍 QA
- [1.98.8] Порог тестов: 1017. Любой PR не должен снижать этот счётчик
- [1.98.8] Smoke test новых endpoints после каждого деплоя: curl -s http://localhost:8002/api/health + все новые пути

## 🚀 DevOps
- [1.98.8] D-RULE-02: после make deploy → docker exec --user root video-translator chown -R appuser:appuser /app/runs/

## 🏗️ CTO/Arch
- [1.98.8] Архитектурный принцип: новый роутер = новый файл = ADR запись. Монолитный projects.py (>1500 строк) — красный флаг

## ⚡ Performance
- [1.98.8] Bundle: JS=127,3 KB gzip, CSS=20,7 KB gzip. Порог: JS < 200 KB. /health: 0.002821s
