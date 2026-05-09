# 📋 WORKFLOW — Протокол межагентного взаимодействия

> Этот файл — единственный источник правды о том, как агенты работают совместно.
> Все агенты ОБЯЗАНЫ следовать этому протоколу без исключений.

---

## 🔴 ПРАВИЛО 1 — Баги фиксятся немедленно, без вопросов

**Любой агент**, обнаруживший баг:

1. **НЕ спрашивает** разрешения у пользователя
2. **НЕ откладывает** на следующий раунд
3. **Немедленно** создаёт ветку и фиксит

```bash
# Шаблон: создать ветку от develop
git checkout develop && git pull origin develop
git checkout -b TVIDEO-XXX-fix-short-desc

# Починить → тесты → коммит
make test:all && make test:coverage
git add -A && git commit -m "fix(TVIDEO-XXX): описание"
```

**Типы багов, требующих немедленного фикса:**

| Кто находит | Тип | Действие |
|---|---|---|
| Любой агент | Падение тестов | Немедленно фиксит |
| Designer | Сломанная вёрстка, overflow, нечитаемый текст | Немедленно фиксит |
| Designer | Светлая/тёмная тема не работает | Немедленно фиксит |
| Designer | Модальный overlay прозрачный | Немедленно фиксит (D-AP-01) |
| QA Monitor | Coverage < порога | Немедленно добавляет тесты |
| QA Monitor | Падение деплоя | Немедленно hotfix |
| Tech Writer | Версия в changelog не совпадает с кодом | Немедленно исправляет |

---

## 🔴 ПРАВИЛО 2 — Двухуровневая система апрувов

### Уровень 1 — pre-push (Agent Gate v4.0) — каждый пуш в develop

Автоматически проверяется при `git push origin develop`.

**8 агентов code-quality:**

| Агент | Что проверяет | Файл апрува |
|---|---|---|
| **Designer** | PNG скриншоты + АПРУV + дата | `design-log.md` |
| **QA Monitor** | Тесты зелёные + АПРУV + дата | `qa-report.md` |
| **Tech Writer** | RELEASE_NOTES + АПРУV + дата | `user-stories.md` |
| **Skill Modernizer** | Grep-фрагменты + АПРУV + дата | `modernizer-log.md` |
| **Backend** | compileall + grep-команды + АПРУV | `review-log.md` |
| **Frontend** | tsc/lint результаты + АПРУV | `review-log.md` |
| **DevOps** | docker/disk данные + git push + АПРУV | `review-log.md` |
| **Security** | shell=True/CORS/yaml.load проверки + АПРУV | `review-log.md` |

### Уровень 2 — make round-close v4.0 — закрытие раунда

Запускается вручную перед push. **8 авто-проверок запускают команды сами — нельзя подделать.**

**8 стратегических агентов:**

| Агент | Что анализирует | Файл апрува |
|---|---|---|
| **CEO** | Бизнес-ценность, монетизация, риски | `review-log.md` |
| **CTO** | Архитектура, техдолг, масштабируемость | `review-log.md` |
| **Project Manager** | Velocity, backlog, процесс | `review-log.md` |
| **QA Engineer** | E2E, нагрузочные, интеграционные тесты | `review-log.md` |
| **UX Designer** | UX паттерны, мобильный, доступность | `review-log.md` |
| **ML Engineer** | Качество моделей, стоимость, accuracy | `review-log.md` |
| **Business Analyst** | Бизнес-требования, user stories | `review-log.md` |
| **System Analyst** | Системная архитектура, API, схемы | `review-log.md` |

### Формат апрува (обязательный):

```markdown
### Подпись: [Имя Агента] АПРУV | YYYY-MM-DD vX.Y.Z
```

---

## 🔴 ПРАВИЛО 3 — Правильный деплой-workflow

```bash
# НЕПРАВИЛЬНО (обходит gate):
make deploy
# Нет, git push не выполняется → агенты не проверяются!

# ПРАВИЛЬНО:
make deploy                   # ← деплой в прод
git push origin develop       # ← запускает pre-push gate (8 агентов)
```

---

## 🔴 ПРАВИЛО 4 — Changelog формат

```
✅ ПРАВИЛЬНО:  ## 1.95.9 — 2026-05-08 — R10-И5: описание
✅ ПРАВИЛЬНО:  ## 1.95.3 - 2026-05-07 - FEAT - TVIDEO-XXX
❌ ЗАПРЕЩЕНО:  ## [1.95.9] — 2026-05-08 — ...
```

Тест `test_latest_changelog_entry_matches_version_file` ищет `## X.Y.Z` (без скобок).

---

## Процедура полного закрытия раунда

```
1. Все итерации раунда завершены
2. make deploy (деплой в прод)
3. D-RULE-02: docker exec --user root video-translator chown -R appuser:appuser /app/runs/
4. Запустить все 16 агентов (каждый выполняет реальные команды, не только пишет текст)
5. make round-close v4.0 → 8 авто-проверок → должно показать: все ✅
6. git push origin develop → pre-push hook → должен пройти
7. Обновить SKILL.md (Skill Modernizer)
```

## Запуск нового раунда

```bash
make improve   # брифинг + инструкция запуска раунда
make session-start   # брифинг без инструкции (начало сессии)
```
