#!/usr/bin/env bash
# run-agent.sh — запуск реального CLI-субагента через gemini -y --prompt
# Модель: gemini-2.5-pro (подписка, OAuth personal)
# Использование: ./scripts/run-agent.sh <agent-name> [--all]
# Примеры:
#   ./scripts/run-agent.sh backend
#   ./scripts/run-agent.sh cto
#   ./scripts/run-agent.sh --all

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; RESET='\033[0m'

AGENTS_DIR=".agents"
VERSION=$(cat VERSION 2>/dev/null || echo "0.0.0")
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M)

# Список всех dev-агентов
ALL_DEV_AGENTS="ceo cto backend frontend qa-engineer devops security project-manager ux-designer ml-engineer system-analyst business-analyst"
# Список process-агентов (у них другой протокол)
PROCESS_AGENTS="designer qa-monitor tech-writer skill-modernizer"

usage() {
  echo -e "${CYAN}Использование: $0 <agent> [опции]${RESET}"
  echo ""
  echo "Dev агенты:      $ALL_DEV_AGENTS"
  echo "Process агенты:  $PROCESS_AGENTS"
  echo ""
  echo "Опции:"
  echo "  --all       Запустить все dev-агенты последовательно"
  echo "  --parallel  Запустить все dev-агенты параллельно (с задержкой 5с между запусками, лимит 60 req/min)"
  echo "  --model MODEL  Выбрать модель (по умолчанию: gemini-2.5-pro)"
  echo ""
  echo "Лимиты подписки: 1500 req/day, 120 req/min (Standard) | 2000 req/day (Enterprise)"
  echo ""
  echo "Примеры:"
  echo "  $0 backend"
  echo "  $0 --all"
  echo "  $0 --parallel"
  exit 0
}

run_agent() {
  local AGENT_NAME="$1"
  local MODEL_OVERRIDE="${2:-}"
  local AGENT_DIR="$AGENTS_DIR/$AGENT_NAME"
  local GEMINI_AGENT_FILE=".gemini/agents/${AGENT_NAME}.md"

  if [ ! -d "$AGENT_DIR" ]; then
    echo -e "${RED}❌ Агент '$AGENT_NAME' не найден: $AGENT_DIR${RESET}"
    exit 1
  fi

  echo -e "${CYAN}━━━ Запуск агента: $AGENT_NAME (v$VERSION, $DATE $TIME) ━━━${RESET}"

  # === Определяем источник конфигурации ===
  # Приоритет: .gemini/agents/<name>.md > .agents/<name>/GEMINI.md > .agents/<name>/AGENT.md
  if [ -f "$GEMINI_AGENT_FILE" ]; then
    # --- Читаем model из frontmatter ---
    AGENT_MODEL=$(grep "^model:" "$GEMINI_AGENT_FILE" | head -1 | sed 's/model: *//')
    [ -z "$AGENT_MODEL" ] && AGENT_MODEL="gemini-2.5-pro"
    # Используем override если передан явно
    [ -n "$MODEL_OVERRIDE" ] && AGENT_MODEL="$MODEL_OVERRIDE"
    # Содержимое без frontmatter (после второго ---)
    SYSTEM_CTX=$(awk 'BEGIN{i=0} /^---/{i++; next} i>=2{print}' "$GEMINI_AGENT_FILE")
    echo -e "${CYAN}  → .gemini/agents/${AGENT_NAME}.md | model: $AGENT_MODEL${RESET}"
  elif [ -f "$AGENT_DIR/GEMINI.md" ]; then
    AGENT_MODEL="${MODEL_OVERRIDE:-gemini-2.5-pro}"
    SYSTEM_CTX=$(cat "$AGENT_DIR/GEMINI.md")
    echo -e "${YELLOW}  → .agents/${AGENT_NAME}/GEMINI.md | model: $AGENT_MODEL${RESET}"
  else
    AGENT_MODEL="${MODEL_OVERRIDE:-gemini-2.5-pro}"
    SYSTEM_CTX=$(cat "$AGENT_DIR/AGENT.md" 2>/dev/null || echo "Ты — $AGENT_NAME агент. Проведи аудит проекта.")
    echo -e "${YELLOW}  → AGENT.md (fallback) | model: $AGENT_MODEL${RESET}"
  fi

  # === Формируем промпт ===
  PROJECT_CONTEXT=$(cat << PEOF
Проект: translateVideo — AI Video Translator
Версия: $VERSION | Дата: $DATE
Корень проекта (pwd): $(pwd)
Git ветка: $(git symbolic-ref --short HEAD 2>/dev/null || echo "unknown")
Последние коммиты:
$(git log --oneline -5 2>/dev/null || echo "N/A")
PEOF
)

  FULL_PROMPT="${SYSTEM_CTX}

---
## Контекст запуска
${PROJECT_CONTEXT}

## Задача
Выполни аудит проекта по своему протоколу. Запусти все обязательные команды.
Составь отчёт из 10 замечаний. Запиши результат в ${AGENT_DIR}/review-log.md."

  echo -e "${YELLOW}  → Запрос к gemini ($AGENT_MODEL)...${RESET}"

  # === Запуск из корня проекта (полный доступ к коду) ===
  OUTPUT=$(gemini -y --model "$AGENT_MODEL" --prompt "$FULL_PROMPT" 2>&1 | grep -v 'Warning:\|YOLO mode\|Ripgrep\|MCP issues\|overriding the built')
  EXIT_CODE=$?

  if [ $EXIT_CODE -ne 0 ]; then
    echo -e "${RED}  ❌ gemini завершился с ошибкой (exit=$EXIT_CODE)${RESET}"
    echo "$OUTPUT" | tail -5
    return 1
  fi

  echo -e "${GREEN}  ✅ Агент $AGENT_NAME завершил работу${RESET}"
  echo ""
  echo "--- Вывод агента ---"
  echo "$OUTPUT" | head -50
  echo "--- конец ---"

  # Записываем в review-log.md если агент не записал сам
  LOG_FILE="$AGENT_DIR/review-log.md"
  if ! grep -q "$DATE" "$LOG_FILE" 2>/dev/null; then
    printf "\n## %s Review — %s %s v%s\n\n%s\n\n---\n" "$AGENT_NAME" "$DATE" "$TIME" "$VERSION" "$OUTPUT" >> "$LOG_FILE"
    echo -e "${CYAN}  → Записано в $LOG_FILE${RESET}"
  fi
}

# Разбор аргументов
if [ $# -eq 0 ]; then
  usage
fi

MODEL="gemini-2.5-pro"
RUN_ALL=false
RUN_PARALLEL=false
AGENTS_TO_RUN=()

while [ $# -gt 0 ]; do
  case "$1" in
    --all)
      RUN_ALL=true
      ;;
    --parallel)
      RUN_ALL=true
      RUN_PARALLEL=true
      ;;
    --model)
      MODEL="$2"
      shift
      ;;
    --help|-h)
      usage
      ;;
    -*)
      echo -e "${RED}Неизвестная опция: $1${RESET}"
      usage
      ;;
    *)
      AGENTS_TO_RUN+=("$1")
      ;;
  esac
  shift
done

if $RUN_ALL; then
  AGENTS_TO_RUN=($ALL_DEV_AGENTS)
fi

if [ ${#AGENTS_TO_RUN[@]} -eq 0 ]; then
  usage
fi

echo -e "${CYAN}╔══════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║  CLI Agent Runner — gemini --prompt (headless)  ║${RESET}"
echo -e "${CYAN}║  Агенты: ${AGENTS_TO_RUN[*]}${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${RESET}"
echo ""

if $RUN_PARALLEL; then
  echo -e "${YELLOW}⚡ Параллельный режим — запуск ${#AGENTS_TO_RUN[@]} агентов (задержка 5с между стартами)...${RESET}"
  echo -e "${YELLOW}  Лимит подписки: 120 req/min — stagger предотвращает rate limit${RESET}"
  PIDS=()
  for agent in "${AGENTS_TO_RUN[@]}"; do
    run_agent "$agent" "$MODEL" > "/tmp/agent-$agent.log" 2>&1 &
    PIDS+=($!)
    echo -e "  → $agent запущен (PID=$!)"
    sleep 5  # stagger: не превышаем 120 req/min при параллельном запуске
  done

  echo ""
  echo -e "${CYAN}Ожидание завершения...${RESET}"
  FAIL=0
  for i in "${!PIDS[@]}"; do
    agent="${AGENTS_TO_RUN[$i]}"
    wait "${PIDS[$i]}"
    code=$?
    if [ $code -eq 0 ]; then
      echo -e "${GREEN}  ✅ $agent завершён${RESET}"
    else
      echo -e "${RED}  ❌ $agent завершился с ошибкой${RESET}"
      cat "/tmp/agent-$agent.log" | tail -5
      FAIL=1
    fi
  done

  if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✅ Все агенты завершены. Отчёты в .agents/*/review-log.md${RESET}"
  else
    echo -e "${RED}❌ Некоторые агенты завершились с ошибкой${RESET}"
    exit 1
  fi
else
  # Последовательный запуск
  for agent in "${AGENTS_TO_RUN[@]}"; do
    run_agent "$agent" "$MODEL"
    echo ""
  done
  echo -e "${GREEN}✅ Готово. Отчёты в .agents/*/review-log.md${RESET}"
fi
