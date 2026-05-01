#!/usr/bin/env bash
# deploy.sh — Деплой translateVideo на video.bigalexn8n.ru
#
# Использование:
#   ./deploy.sh            — деплой текущей ветки
#   ./deploy.sh master     — переключиться на master и задеплоить
#
# Что делает:
#   1. (Опционально) git pull / git checkout <branch>
#   2. Запускает тесты Python
#   3. Пересобирает Docker-образ (включая npm run build внутри)
#   4. Перезапускает контейнер video-translator
#   5. Проверяет /api/health

set -euo pipefail

# ── Цвета ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${CYAN}▶ $*${NC}"; }
ok()    { echo -e "${GREEN}✔ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
fail()  { echo -e "${RED}✗ $*${NC}"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 1. Переключение ветки (если передан аргумент) ───────────────────────────
if [[ "${1:-}" != "" ]]; then
  info "Переключаемся на ветку: $1"
  git checkout "$1"
fi

# ── 2. Git pull (обновить из remote) ────────────────────────────────────────
BRANCH=$(git rev-parse --abbrev-ref HEAD)
info "Ветка: $BRANCH — тянем изменения из origin..."
git pull origin "$BRANCH" || warn "git pull не удался — деплоим текущее состояние"

COMMIT=$(git rev-parse --short HEAD)
info "Коммит: $COMMIT"

# ── 3. Python-тесты ─────────────────────────────────────────────────────────
info "Запуск тестов..."
if PYTHONPATH=src python3 -m unittest discover -s tests -q 2>&1; then
  ok "Тесты прошли"
else
  fail "Тесты упали — деплой отменён. Запусти 'make test' для деталей."
fi

# ── 4. Пересборка Docker-образа ──────────────────────────────────────────────
info "Пересборка образа (ui build + backend install)..."
docker compose build

# ── 5. Перезапуск контейнера ─────────────────────────────────────────────────
info "Перезапуск контейнера..."
docker compose up -d

# ── 6. Проверка здоровья ─────────────────────────────────────────────────────
info "Ожидаем запуска сервера (3с)..."
sleep 3

HEALTH=$(curl -sf http://localhost:8002/api/health 2>/dev/null || echo '{}')
VERSION=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','?'))" 2>/dev/null || echo "?")
STATUS=$(echo  "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))"  2>/dev/null || echo "?")

if [[ "$STATUS" == "ok" ]]; then
  ok "Деплой завершён!"
  echo ""
  echo "  🌐 https://video.bigalexn8n.ru"
  echo "  📦 Версия: $VERSION"
  echo "  🔖 Коммит: $COMMIT"
  echo "  🌿 Ветка:  $BRANCH"
else
  fail "Сервер не отвечает после деплоя. Логи: docker compose logs -f video-translator"
fi
