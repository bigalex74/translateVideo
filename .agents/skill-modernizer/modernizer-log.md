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

---

## [SKILL-MODERNIZER] Round 9 → Обновление CI Skill v3.5

**Дата:** 2026-05-06T22:00  
**Режим:** B (пост-раундовый полный анализ)

### 📊 Статистика раунда:
- Итераций выполнено: 5 (И1-И5)
- Тикетов: TVIDEO-214/215/216/217/218
- Тестов: было 868 → стало **887** (+19)
- Coverage: был 79% → стал **80%** (QA Monitor исправил post-merge)
- Новые фичи: SW v3 offline-first, AI Hints + LRU cache, Share Links, Analytics Dashboard, QA Gate
- Деплоев: 1 (push develop)

### 🔧 Изменения в скиллах:

**continuous-improvement/SKILL.md (v3.3 → v3.5):**
- Обновлён порог тестов: 832 → 887
- Добавлено правило #11: новый endpoint → тесты в той же итерации
- Добавлено правило #12: Designer grep LS_KEY перед проверкой
- Добавлено правило #13: агенты ДО merge в develop
- Добавлены антипаттерны Round 8 и Round 9 (R9-AP-01/02/03/04)

**Designer AGENT.md (обновление):**
- Добавлено [D-RULE-01]: обязательный grep LS_KEY в начале каждой визуальной проверки

### ⚠️ Выявленные проблемы процесса:

| # | Проблема | Причина | Решение в скилле |
|---|---------|---------|-----------------|
| R9-AP-01 | Merge без апрува агентов | Не было привычки/правила | Правило #13 |
| R9-AP-02 | Designer: ложная проверка (LS_KEY) | Угадывал ключ localStorage | Правило #12 + D-RULE-01 |
| R9-AP-03 | analytics.py без тестов при создании | Coverage проверялась только в И5 | Правило #11 |
| R9-AP-04 | Порог тестов устарел в SKILL.md | SM не обновлял после каждого раунда | Немедленное обновление |

### 📌 Рекомендации для Round 10:
1. **Перед каждым merge** — явно запускать команды из WORKFLOW.md Правило 2 (все 4 агента)
2. **При создании нового routes/*.py** — сразу создавать `tests/test_<module>.py`
3. **Designer всегда начинает** с `grep -n 'LS_KEY' ui/src/components/OnboardingTour.tsx`
4. **Skill Modernizer порог тестов** — обновлять сразу как тесты выросли (не в конце раунда)

### Self-Evolution вопросы (Режим самоанализа):
1. Анализ достаточно глубокий? — Да, выявлено 4 антипаттерна с конкретными правилами
2. Нашёл ВСЕ антипаттерны? — Возможно пропущен: Skill Modernizer сам не запускался в И1-И5
3. Правильно определён ответственный агент? — Да (Designer→R9-AP-02, QA→R9-AP-03, процесс→R9-AP-01)
4. Отчёт CEO информативен? — Да, конкретные правила с номерами
5. Алгоритм Режим A/B можно улучшить? — Режим A должен явно включать проверку что агенты запустятся ДО следующего merge

**Подпись:** Skill Modernizer | 2026-05-06T22:00

---

## [SKILL-MODERNIZER] v1.93-1.94 Audit
**Дата:** 2026-05-07 08:35  
**Режим:** B (пост-итерационный аудит)

### Проверено:
- [x] make iteration выполнен (тесты + деплой + верификация)
- [x] Ветка TVIDEO-219-221 создана и слита через --no-ff
- [x] 2 новых тестов для segment actions ветвей (coverage gap fix)
- [x] 8 новых тестов для client.ts (Share Links, Hints, Analytics)
- [x] SW sync branch покрыт тестами
- [x] Path traversal защита в _reset_segment_tts корректна
- [x] doctor.py coverage: 88%

### SKILL.md изменения: нет (v3.5 актуален)

### Подпись: Skill Modernizer | 2026-05-07 08:35

---
## [SKILL-MODERNIZER] И1 v1.95.0
**Режим:** B | **Дата:** 2026-05-07 22:57
- with_retry применён корректно: speechkit (_synth/_synth_plain), cloud.py (_post_json/_attempt), webhook (_send_sync)
- HTTP 4xx (кроме 429) — non-retryable: корректно ✅
- HTTP 429 — min_sleep=5.0s: корректно ✅
- Тесты: 12 штук, все зелёные ✅
- SKILL.md: добавить правило «При добавлении HTTP-вызова — обернуть в with_retry немедленно» в следующей итерации обновления навыка
### Подпись: Skill Modernizer | 2026-05-07 22:57

---
## [SKILL-MODERNIZER] И2 v1.95.1
**Режим:** B | **Дата:** 2026-05-07 23:13
- useVisibilityRefresh — правильный паттерн: hook изолирован, enabled-guard, cleanup в return ✅
- requestCompletionNotification — async функция, graceful degradation если Notification API нет ✅
- Contextual permission request (при запуске, не при загрузке) — best practice UX ✅
- SKILL.md UPDATE: добавить «Notification permission запрашивать контекстуально, не при старте приложения»
### Подпись: Skill Modernizer | 2026-05-07 23:13

---
## [SKILL-MODERNIZER] И3 v1.95.2
**Режим:** B | **Дата:** 2026-05-07 23:21
- CSS-only: mobile breakpoints корректны, viewport meta присутствует ✅
- pointer:coarse для touch targets — правильный подход (лучше чем max-width) ✅
- SKILL.md UPDATE: «Всегда добавлять pointer:coarse блок для touch target ≥44px»
### Подпись: Skill Modernizer | 2026-05-07 23:21

---
## [SKILL-MODERNIZER] И4 v1.95.3
**Режим:** B | **Дата:** 2026-05-07 23:29
- showKey паттерн (toggle visibility) — правильное использование local state ✅
- Destructive action pattern: всегда window.confirm() перед localStorage clear ✅
- SKILL.md UPDATE: «Деструктивные действия (clear, delete, reset) требуют confirm()»
### Подпись: Skill Modernizer | 2026-05-07 23:29

---
## [SKILL-MODERNIZER] И5 v1.95.4
**Режим:** B | **Дата:** 2026-05-07 23:38
- calcQualityScore() — чистая функция вне компонента (good separation) ✅
- 4-tier threshold design (ok/warn/danger/critical) — правильный UX паттерн ✅
- SKILL.md UPDATE: «Используй 3-4 tier threshold для метрик качества (ok/warn/danger/critical)»
### Подпись: Skill Modernizer | 2026-05-07 23:38
