# Деплой translateVideo на video.bigalexn8n.ru

## Архитектура

```
GitHub repo
    │
    │  git pull / git checkout
    ▼
/home/user/translateVideo/   ← рабочая копия
    │
    │  docker compose build
    ▼
Docker image  (multi-stage)
    ├── Stage 1: node:20-alpine
    │       npm ci + npm run build  →  ui/dist/
    └── Stage 2: python:3.11-slim
            pip install -e .
            COPY . .
            COPY --from=stage1 ui/dist → /app/ui/dist
    │
    │  docker compose up -d
    ▼
Container: video-translator  (port 8002)
    │
Caddy reverse proxy
    │
https://video.bigalexn8n.ru
```

> **Ключевое правило**: `ui/dist/` **копируется в Docker-образ** при сборке.  
> Изменения в коде (Python или TypeScript) **не видны** на сайте, пока не выполнен `docker compose build`.

---

## Быстрый деплой

### Вариант 1 — скрипт (рекомендуется)

```bash
cd /home/user/translateVideo

# Задеплоить текущую ветку
./deploy.sh

# Задеплоить конкретную ветку (например, master)
./deploy.sh master
```

Скрипт выполняет: `git pull` → тесты → `docker build` → `docker up` → health check.

### Вариант 2 — Makefile

```bash
cd /home/user/translateVideo

make deploy    # пересобрать образ и перезапустить
make restart   # только перезапустить (без пересборки, если код не менялся)
make logs      # следить за логами
make status    # статус контейнера + версия API
make test      # запустить Python тесты
make help      # список всех команд
```

### Вариант 3 — вручную

```bash
cd /home/user/translateVideo
docker compose build      # пересборка (занимает ~1-2 мин)
docker compose up -d      # перезапуск контейнера
curl http://localhost:8002/api/health  # проверка
```

---

## Рабочий процесс разработки

### Типичный цикл фичи

```bash
# 1. Создать ветку
git checkout -b TVIDEO-XXX-feature-name

# 2. Разработка (локально)
make test        # запустить тесты
make ui-dev      # Vite dev-сервер на localhost:5173 (с прокси на localhost:8002)

# 3. Собрать UI локально (проверка перед PR)
make ui-build    # или: cd ui && npm run build

# 4. Запустить тесты + проверку типов
make test lint

# 5. Коммит и пуш
git add -A
git commit -m "feat: описание изменения"
git push -u origin TVIDEO-XXX-feature-name

# 6. Смерджить в master и задеплоить
git checkout master
git merge --no-ff TVIDEO-XXX-feature-name
./deploy.sh
```

### Только изменения UI

Если менялся только TypeScript/CSS — собирать backend заново не нужно,
но Docker-образ всё равно нужно пересобрать, т.к. `ui/dist/` в нём:

```bash
make deploy   # быстрее, чем кажется: Python-слой кешируется Docker
```

### Только изменения Backend

Аналогично — Python-код внутри образа, нужен `make deploy`.

---

## Переменные окружения

В `docker-compose.yml`:

| Переменная | Значение по умолчанию | Описание |
|-----------|----------------------|----------|
| `WORK_ROOT` | `/app/runs` | Папка для рабочих файлов проектов |
| `ALLOWED_ORIGINS` | *(не задана)* | CORS origins (дефолт: только localhost) |

Для production задайте `ALLOWED_ORIGINS` в `docker-compose.yml`:

```yaml
environment:
  - WORK_ROOT=/app/runs
  - ALLOWED_ORIGINS=https://video.bigalexn8n.ru
```

---

## Отладка

### Контейнер не запускается

```bash
docker compose logs video-translator
docker compose ps
```

### Сайт открывается, но изменения не видны

```bash
# 1. Убедиться что образ пересобран
curl http://localhost:8002/api/health   # проверить версию

# 2. Сбросить кэш браузера
# Ctrl+Shift+R (hard reload)

# 3. Проверить какой JS отдаётся
curl -s http://localhost:8002/ | grep -o 'assets/index-[^"]*\.js'
# Должен совпадать с: ls ui/dist/assets/
```

### Тесты упали при деплое

```bash
make test           # запустить тесты локально
make lint           # проверить типы TypeScript
```

---

## Мониторинг

| Что | Команда |
|-----|---------|
| Логи в реальном времени | `make logs` |
| Статус контейнера | `make status` |
| Health-check API | `curl http://localhost:8002/api/health` |
| Версия на сайте | `curl https://video.bigalexn8n.ru/api/health` |
