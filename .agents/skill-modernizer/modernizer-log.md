# 🧠 Skill Modernizer — Журнал антипаттернов и улучшений

> Ведёт: Skill Modernizer Agent | Обновляется после каждого раунда

---

## Round 7 (2026-05-06)

### Выявленные антипаттерны

#### [R7-AP-01] `data-theme` без `[data-theme]` CSS-селектора
- **Где:** `ui/src/store/settings.ts` → `applyTheme()` + `ui/src/index.css`
- **Симптом:** Ручное переключение тёмной темы не работало — тема игнорировалась
- **Причина:** JS устанавливал `data-theme="dark"` на `<html>`, но CSS имел только `@media (prefers-color-scheme: dark)`, без `[data-theme="dark"]` блока
- **Исправление:** Добавлены `[data-theme="dark"]` и `[data-theme="light"]` в index.css (R7-И1)
- **Правило в SKILL.md:** ✅ Добавлено в раздел «Антипаттерны Round 7»

#### [R7-AP-02] Агенты без выходных файлов
- **Где:** `.agents/*/AGENT.md` — только инструкции, нет артефактов
- **Симптом:** Пользователь не видит работу агентов — всё происходит «в воздухе»
- **Причина:** AGENT.md описывали роли, но не определяли output-файлы
- **Исправление:** Создана инфраструктура выходных файлов (R7-пост):
  - `.agents/qa-monitor/qa-report.md`
  - `.agents/tech-writer/user-stories.md`
  - `.agents/designer/design-log.md`
  - `.agents/skill-modernizer/modernizer-log.md`
- **Правило:** Каждый агент ОБЯЗАН писать в свой output-файл после каждой итерации

---

### Обновления SKILL.md

| Файл | Изменение | Раунд |
|---|---|---|
| `continuous-improvement/SKILL.md` | Добавлен R7 антипаттерн `data-theme` | R7-И1 |
| `continuous-improvement/SKILL.md` | Версия v3.3 → v3.4 | R7-post |
| `translate-video/SKILL.md` | Правило Docker Hygiene (Правило 7) | R6 |
| `.agents/qa-monitor/AGENT.md` | Таблица порогов диска и Docker cache | R6 |

---

### Рекомендации для AGENT.md файлов

Каждый AGENT.md должен содержать раздел:

```markdown
## 📁 Output-файлы

| Файл | Назначение | Когда обновлять |
|------|------------|-----------------|
| `qa-report.md` | Журнал проверок качества | После каждого деплоя |
```

**Статус обновления AGENT.md:**
- [ ] qa-monitor/AGENT.md — добавить секцию Output-файлы
- [ ] tech-writer/AGENT.md — добавить секцию Output-файлы
- [ ] designer/AGENT.md — добавить секцию Output-файлы
- [ ] skill-modernizer/AGENT.md — добавить секцию Output-файлы

---

### Паттерны найденные в R7 (хорошие)

| Паттерн | Где | Оценка |
|---|---|---|
| `safariSafeDownload()` через fetch+blob | client.ts | ✅ Правильно — нативный download ненадёжен |
| `formatTimecode()` чистая функция вне компонента | Workspace.tsx | ✅ Правильно — легко тестировать |
| `beforeunload` через `useEffect` с cleanup | Workspace.tsx | ✅ Правильно — нет memory leak |
| WebSocket с `asyncio.sleep(2)` loop | projects.py | ✅ OK, но без broadcast — только 1-to-1 |

---

## История версий Skill Modernizer

| Версия | Дата | Ключевые изменения |
|---|---|---|
| v3.4 | 2026-05-06 | R7 антипаттерны, output-файлы агентов |
| v3.3 | 2026-05-05 | Обязательный запуск 4 агентов в каждой итерации |
| v3.2 | 2026-05-05 | Round 5 антипаттерны, порог 832 тестов |
| v3.1 | 2026-05 | Round 4 антипаттерны |
| v3.0 | 2026-04 | Введена система раундов |

*Последнее обновление: 2026-05-06 | v1.80.0 | Skill Modernizer Agent*

---

## Round 8 (2026-05-06)

### Выявленные антипаттерны

#### [R8-AP-01] Inline polling useEffect вместо хука
- **Где:** Workspace.tsx строки 161-198 (до R8)
- **Симптом:** 38 строк inline async polling с setTimeout, сложно тестировать
- **Исправление:** Вынесен в `hooks/useProjectStatus.ts` — WS primary + HTTP fallback
- **Правило:** Любая асинхронная стратегия > 10 строк → выносить в хук

#### [R8-AP-02] Один `client.ts` со смешанными import типами
- **Где:** `src/api/client.ts` импортируется и статически и динамически
- **Симптом:** `[INEFFECTIVE_DYNAMIC_IMPORT]` в каждом build (QA-001)
- **Исправление:** Запланировано R9 — убрать `import('../api/client')` в onDrop/onSubmit, заменить статическими импортами
- **Правило:** Один файл — один тип импорта. Динамический импорт только для code-splitting по маршрутам.

### Хорошие паттерны R8

| Паттерн | Где | Оценка |
|---|---|---|
| `@media (pointer: coarse)` для touch | index.css | ✅ Правильно — не трогает desktop mouse users |
| `aria-hidden="true"` на skeleton cards | Dashboard.tsx | ✅ Accessibility-first |
| Gradient-based shimmer через CSS vars | index.css | ✅ Автоматически темизирован |
| WebSocket + fallback в одном хуке | useProjectStatus.ts | ✅ Надёжно, легко тестировать |

### Обновления SKILL.md

| Действие | Дата |
|---|---|
| Добавлен R8-AP-01 в раздел антипаттернов | 2026-05-06 |
| Добавлен R8-AP-02 (dynamic import) в раздел | 2026-05-06 |

*Обновлено: 2026-05-06 | v1.82.0 | Skill Modernizer Agent*
