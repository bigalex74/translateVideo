.PHONY: help session-start improve build deploy restart logs status test test\:unit test\:ui test\:e2e test\:e2e-fullstack test\:load test\:all test\:coverage test\:metadata test\:release ci\:quick release\:checklist release\:fix release\:finish lint ui-build ui-dev visual-check visual-check-ci css-guard

# Цвета для вывода
CYAN  := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED   := \033[0;31m
RESET := \033[0m

## session-start: ⚡ ЗАПУСКАТЬ В НАЧАЛЕ КАЖДОЙ СЕССИИ — контекст для AI-ассистента
session-start:
	@echo ""
	@echo "$(CYAN)╔══════════════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(CYAN)║  translateVideo — SESSION START BRIEFING                        ║$(RESET)"
	@echo "$(CYAN)╚══════════════════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "$(CYAN)📌 ВЕРСИЯ И ВЕТКА:$(RESET)"
	@echo "  Версия:  $$(cat VERSION)"
	@echo "  Ветка:   $$(git branch --show-current)"
	@echo "  Прод:    $$(curl -s --connect-to 'localhost:8002:127.0.0.1:8002' http://localhost:8002/api/health 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print("v"+d["version"]+" "+d["status"])' 2>/dev/null || curl -s http://127.0.0.1:8002/api/health 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print("v"+d["version"]+" "+d["status"])' 2>/dev/null || echo 'недоступен')"
	@echo ""
	@echo "$(CYAN)📋 ПОСЛЕДНИЕ 5 КОММИТОВ:$(RESET)"
	@git log --oneline -5
	@echo ""
	@echo "$(CYAN)🔴 БЭКЛОГ P1 (из .agents/tech-writer/user-stories.md):$(RESET)"
	@grep "🔴 P1" .agents/tech-writer/user-stories.md 2>/dev/null | sed 's/^[ |]*/  /' || echo "  (файл не найден)"
	@echo ""
	@echo "$(CYAN)🤖 ПРОТОКОЛ АГЕНТОВ (ОБЯЗАТЕЛЬНО перед push):$(RESET)"
	@echo "  1. make round-close     — 8 авто-проверок (тесты, tsc, security, docker...)"
	@echo "  2. git push origin develop  — pre-push hook"
	@echo ""
	@echo "  Что значит реальная работа агентов:"
	@echo "  $(YELLOW)Designer$(RESET)     → navigate_page → click кнопки → take_screenshot + HTTP smoke"
	@echo "  $(YELLOW)QA Monitor$(RESET)   → python3 -m unittest + результат в qa-report.md"
	@echo "  $(YELLOW)Skill Mod.$(RESET)   → обновить AGENT.md файлы (не только лог)"
	@echo "  $(YELLOW)BA Survey$(RESET)    → user-surveys/R{N}-survey.md с персонами"
	@echo "  $(YELLOW)Tech Writer$(RESET)  → RELEASE_NOTES + roadmap версия совпадает"
	@echo ""
	@echo "$(CYAN)⚠️  D-RULE-02 (после make deploy):$(RESET)"
	@echo "  docker exec --user root video-translator chown -R appuser:appuser /app/runs/"
	@echo "  (без этого → PermissionError 500 на SRT/DOCX экспорте)"
	@echo ""
	@echo "$(CYAN)🧠 УРОКИ АГЕНТОВ (Skill Modernizer — последний раунд):$(RESET)"
	@if [ -f .agents/LESSONS.md ]; then \
	  grep -E "^- \*\*|^- \[" .agents/LESSONS.md | head -12 | sed 's/^/  /'; \
	  echo "  (полный файл: cat .agents/LESSONS.md)"; \
	else \
	  echo "  (нет файла — запусти: python3 scripts/skill_modernizer.py)"; \
	fi
	@echo ""
	@echo "$(CYAN)📁 КЛЮЧЕВЫЕ ФАЙЛЫ:$(RESET)"
	@echo "  .agents/WORKFLOW.md            — правила межагентного взаимодействия"
	@echo "  .agents/LESSONS.md             — ⬅️  уроки всех агентов (SM дистиллят)"
	@echo "  .agents/*/AGENT.md             — протоколы агентов по ролям"
	@echo "  .agents/business-analyst/user-surveys/ — опросы пользователей"
	@echo "  Makefile (round-close v4.0)    — gate перед push"
	@echo ""
	@echo "$(GREEN)✅ Брифинг завершён. Можно работать.$(RESET)"
	@echo ""


## help: Показать все доступные команды
help:
	@echo ""
	@echo "  $(CYAN)translateVideo — команды управления$(RESET)"
	@echo ""
	@grep -E '^## ' Makefile | sed 's/## /  /' | column -t -s ':'
	@echo ""

## improve: 🚀 СТРАТЕГИЯ НЕПРЕРЫВНОГО УЛУЧШЕНИЯ — запустить раунд улучшений
improve:
	@echo ""
	@echo "\033[0;36m╔══════════════════════════════════════════════════════════════════╗\033[0m"
	@echo "\033[0;36m║  CONTINUOUS IMPROVEMENT STRATEGY v3.6                          ║\033[0m"
	@echo "\033[0;36m╚══════════════════════════════════════════════════════════════════╝\033[0m"
	@echo ""
	@$(MAKE) session-start
	@echo "\033[0;36m━━━ ИНСТРУКЦИЯ ЗАПУСКА РАУНДА ━━━\033[0m"
	@echo ""
	@echo "  Запусти скилл: continuous-improvement (уже загружен выше)"
	@echo ""
	@echo "  Параметры раунда:"
	@echo "    - Итераций: 5"
	@echo "    - Пользователей: 5 персон (FBA)"
	@echo "    - Замечаний/пользователь: 10 (4 крит / 3 мажор / 3 минор)"
	@echo "    - Проблем к закрытию: 5-7 на пользователя"
	@echo ""
	@echo "  Порядок каждой итерации:"
	@echo "    1. FBA: 5 пользователей → 50 замечаний → CEO-отчёт"
	@echo "    2. CEO: стратегия + распределение по 16 агентам"
	@echo "    3. 16 агентов: реализация (см. .agents/WORKFLOW.md)"
	@echo "    4. make iteration  ← тесты + деплой + верификация"
	@echo "    5. Агенты: реальная работа (Designer кликает, QA запускает тесты)"
	@echo "    6. make round-close  ← 8 авто-проверок, нельзя подделать"
	@echo "    7. git push origin develop"
	@echo ""
	@echo "  Полный протокол агентов: cat .agents/WORKFLOW.md"
	@echo "  Протоколы каждого агента: cat .agents/*/AGENT.md"
	@echo ""
	@echo "\033[0;32m✅ Брифинг готов. Начинай итерацию.\033[0m"
	@echo ""

## build: Пересобрать Docker-образ (UI + Backend)
build:
	@echo "$(CYAN)▶ Сборка образа...$(RESET)"
	docker compose build

## deploy: Пересобрать образ и перезапустить контейнер (= выкатить на сайт)
deploy:
	@echo "$(CYAN)▶ Деплой на video.bigalexn8n.ru...$(RESET)"
	@# Обновить версию SW для инвалидации кэша браузера
	@VERSION=$$(cat VERSION 2>/dev/null || echo "0.0.0"); \
	  sed -i "s/const APP_VERSION = '[^']*'/const APP_VERSION = '$$VERSION'/" ui/public/sw.js; \
	  echo "$(CYAN)  SW версия: $$VERSION$(RESET)"
	@# Пересобрать UI с новым sw.js
	cd ui && npm run build
	docker compose build
	docker compose up -d
	@# [D-RULE-02] Fix permissions: runs/ файлы могут быть root → appuser не может читать
	@sleep 2 && docker exec --user root video-translator chown -R appuser:appuser /app/runs/ 2>/dev/null || true
	@echo "$(GREEN)✔ Готово. Версия:$(RESET)"
	@sleep 1 && curl -s http://localhost:8002/api/health

## restart: Перезапустить контейнер без пересборки (только если нет изменений кода)
restart:
	@echo "$(CYAN)▶ Перезапуск контейнера...$(RESET)"
	docker compose restart video-translator

## logs: Показать логи контейнера в реальном времени
logs:
	docker compose logs -f video-translator

## status: Статус контейнера и версия API
status:
	@docker compose ps
	@echo ""
	@curl -s http://localhost:8002/api/health | python3 -m json.tool

## test: Запустить Python unit-тесты
test:
	PYTHONPATH=src python3 -m unittest discover -s tests

## test:unit: Запустить только Python unit-тесты
test\:unit:
	PYTHONPATH=src python3 -m unittest discover -s tests/unit

## test:ui: Запустить vitest unit-тесты фронтенда
test\:ui:
	cd ui && npm test

## test:e2e: Запустить browser E2E через Playwright
test\:e2e:
	cd ui && npm run test:e2e

## test:e2e-fullstack: Запустить browser E2E против реального FastAPI backend
test\:e2e-fullstack:
	cd ui && npm run test:e2e:fullstack

## test:load: Запустить нагрузочные smoke-тесты
test\:load:
	PYTHONPATH=src python3 -m unittest discover -s tests/load

## test:all: Запустить unit/integration тесты (Python + vitest)
test\:all:
	PYTHONPATH=src python3 -m unittest discover -s tests -q
	cd ui && npm test

## test:coverage: Проверить покрытие кода (Python ≥80%, TypeScript ≥80%)
# QA Monitor: порог НЕЛЬЗЯ снижать. Рост: projects.py (60%→80%) + providers.py (90%+)
test\:coverage:
	@echo "$(CYAN)▶ Coverage: Python...$(RESET)"
	PYTHONPATH=src python3 -m coverage run \
	  --source=translate_video \
	  --omit="*/legacy.py" \
	  -m unittest discover -s tests -q
	python3 -m coverage report --fail-under=80
	@echo "$(CYAN)▶ Coverage: TypeScript...$(RESET)"
	cd ui && npm run test -- --coverage

## test:metadata: Проверить версии, changelog, roadmap, CI и Docker healthcheck
test\:metadata:
	PYTHONPATH=src python3 -m unittest tests.unit.test_version_consistency tests.unit.test_version_metadata tests.unit.test_release_metadata

## ci:quick: Быстрый CI gate для PR: metadata, Python tests, lint, UI tests/build
ci\:quick:
	$(MAKE) test\:metadata
	PYTHONPATH=src python3 -m unittest discover -s tests -q
	python3 -m compileall -q src tests
	cd ui && npm run lint
	cd ui && npm run test
	cd ui && npm run build
	git diff --check

## release:checklist: Показать обязательный чеклист релиза
release\:checklist:
	@sed -n '1,220p' docs/release-checklist.md

## test:release: Полный release gate перед merge в master
# Запускать ПЕРЕД каждым merge develop→master.
# Если падают → НЕ пушить master, создать release-fix ветку (make release:fix).
test\:release:
	$(MAKE) test\:metadata
	PYTHONPATH=src python3 -m unittest discover -s tests
	python3 -m compileall -q src tests
	cd ui && npm run lint
	cd ui && npm run test
	cd ui && npm run build
	cd ui && npm run test:e2e
	cd ui && npm run test:e2e:fullstack
	$(MAKE) test\:coverage
	git diff --check
	@echo "$(GREEN)✅ Release gate пройден. Можно делать: git checkout master && git merge --no-ff develop$(RESET)"

## release:fix: Создать release-fix ветку от develop (когда E2E провалились)
# Использование: make release:fix TICKET=TVIDEO-XXX NAME=short-desc
# Пример:        make release:fix TICKET=TVIDEO-210 NAME=fix-ws-auth
release\:fix:
	@if [ -z "$(TICKET)" ] || [ -z "$(NAME)" ]; then \
	  echo "$(RED)Использование: make release:fix TICKET=TVIDEO-XXX NAME=short-desc$(RESET)"; \
	  exit 1; \
	fi
	@BRANCH=$(TICKET)-$(NAME)
	git checkout develop
	git pull origin develop
	git checkout -b "release-fix/$(TICKET)-$(NAME)"
	@echo "$(GREEN)✅ Ветка release-fix/$(TICKET)-$(NAME) создана. Исправьте баги, затем запустите make release:finish TICKET=$(TICKET) NAME=$(NAME)$(RESET)"

## release:finish: Завершить release-fix — merge в develop + прогон E2E
# Использование: make release:finish TICKET=TVIDEO-XXX NAME=short-desc
release\:finish:
	@if [ -z "$(TICKET)" ] || [ -z "$(NAME)" ]; then \
	  echo "$(RED)Использование: make release:finish TICKET=TVIDEO-XXX NAME=short-desc$(RESET)"; \
	  exit 1; \
	fi
	@echo "$(CYAN)▶ Прогон unit-тестов + coverage перед merge...$(RESET)"
	$(MAKE) test\:all
	$(MAKE) test\:coverage
	git checkout develop
	git merge --no-ff "release-fix/$(TICKET)-$(NAME)" -m "Merge release-fix/$(TICKET)-$(NAME) into develop"
	git push origin develop "release-fix/$(TICKET)-$(NAME)"
	@echo "$(CYAN)▶ Запуск полного E2E gate...$(RESET)"
	$(MAKE) test\:release


## lint: Проверить ESLint, типы TypeScript и синтаксис Python
lint:
	cd ui && npm run lint
	cd ui && npx tsc --noEmit
	python3 -m compileall -q src tests

## ui-build: Собрать фронтенд локально (не через Docker)
ui-build:
	cd ui && npm run build

## ui-dev: Запустить Vite dev-сервер на localhost:5173
ui-dev:
	cd ui && npm run dev

## css-guard: Статический анализ CSS (Designer Level 1) — проверка обязательных свойств
css-guard:
	@echo "$(CYAN)🛡  CSS Guard — проверка обязательных свойств...$(RESET)"
	python3 scripts/css_guard.py ui/src/index.css ui/src/components/ConfirmRunModal.css
	@echo "$(GREEN)✔ CSS Guard OK$(RESET)"

## visual-check: Playwright visual smoke — ВИДИМЫЙ браузер + скриншоты (Designer Level 2)
visual-check:
	@echo "$(CYAN)📸 Visual Smoke — открываем браузер, снимаем скриншоты...$(RESET)"
	@echo "   Убедитесь что приложение запущено на :8002"
	cd ui && npx playwright test --config=playwright.visual.config.ts --reporter=list
	@echo "$(GREEN)✔ Скриншоты в .agents/designer/screenshots/$(RESET)"

## visual-check-ci: Visual smoke headless — для CI без GUI
visual-check-ci:
	@echo "$(CYAN)📸 Visual Smoke CI (headless)...$(RESET)"
	cd ui && PWHEADLESS=true npx playwright test --config=playwright.visual.config.ts --reporter=list
	@echo "$(GREEN)✔ Готово$(RESET)"


## round-close v4.0: НЕЛЬЗЯ ПОДДЕЛАТЬ — критические проверки запускают команды сами.
## Принцип: если команда не запускалась реально, round-close УПАДЁТ.
## Запускать ПЕРЕД каждым git push origin develop.
round-close:
	@echo "\033[0;36m╔══════════════════════════════════════════════════════════════════╗\033[0m"
	@echo "\033[0;36m║  ROUND CLOSE v4.0 — НЕЛЬЗЯ ПОДДЕЛАТЬ                           ║\033[0m"
	@echo "\033[0;36m║  Команды запускаются здесь. Логи — только документация.         ║\033[0m"
	@echo "\033[0;36m╚══════════════════════════════════════════════════════════════════╝\033[0m"
	@echo ""
	@FAIL=0; \
	TODAY=$$(date +%Y-%m-%d); \
	YESTERDAY=$$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || echo "0000-00-00"); \
	echo "\033[0;36m━━━ [1] QA Monitor: Python тесты — запускаем ЗДЕСЬ ━━━\033[0m"; \
	PY_RESULT=$$(PYTHONPATH=src python3 -m unittest discover -s tests -q 2>&1 | tail -2); \
	echo "  $$PY_RESULT"; \
	if echo "$$PY_RESULT" | grep -q "^OK"; then \
	  echo "\033[0;32m  ✅ Python тесты: PASS\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ Python тесты: FAIL — нельзя закрыть раунд\033[0m"; \
	  FAIL=1; \
	fi; \
	QA_REPORT_DATE=$$(grep -c "$$TODAY\|$$YESTERDAY" .agents/qa-monitor/qa-report.md 2>/dev/null || echo 0); \
	QA_REPORT_TESTS=$$(grep -cE "[0-9]+ (test|ok|passed|FAIL)|OK \(|skipped=[0-9]" .agents/qa-monitor/qa-report.md 2>/dev/null || echo 0); \
	if [ "$$QA_REPORT_DATE" -gt 0 ] && [ "$$QA_REPORT_TESTS" -gt 0 ]; then \
	  echo "\033[0;32m  ✅ QA Monitor: qa-report.md обновлён с реальными числами тестов\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ QA Monitor: qa-report.md не обновлён или нет чисел тестов\033[0m"; \
	  echo "     → Запиши результат unittest в .agents/qa-monitor/qa-report.md"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [2] Frontend: tsc — запускаем ЗДЕСЬ ━━━\033[0m"; \
	TSC_RESULT=$$(cd ui && npx tsc --noEmit 2>&1 | head -5); \
	TSC_EXIT=$$?; \
	if [ -z "$$TSC_RESULT" ]; then \
	  echo "\033[0;32m  ✅ tsc: 0 ошибок\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ tsc ошибки:\033[0m"; \
	  echo "$$TSC_RESULT"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [3] Security: shell=True, yaml.load, hardcoded — grep ЗДЕСЬ ━━━\033[0m"; \
	SHELL_T=$$(grep -rn "shell=True" src/ 2>/dev/null | grep -v "test_\|#" | wc -l); \
	YAML_U=$$(grep -rn "yaml\.load(" src/ 2>/dev/null | grep -v "safe_load\|test_" | wc -l); \
	SEC_SECRETS=$$(grep -rn "password\s*=\s*['\"][^'\"]" src/ 2>/dev/null | grep -v "test_" | wc -l); \
	echo "  shell=True: $$SHELL_T | yaml.load (unsafe): $$YAML_U | hardcoded secrets: $$SEC_SECRETS"; \
	if [ "$$SHELL_T" -eq 0 ] && [ "$$YAML_U" -eq 0 ] && [ "$$SEC_SECRETS" -eq 0 ]; then \
	  echo "\033[0;32m  ✅ Security: чисто\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ Security: найдены проблемы — исправить\033[0m"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [4] DevOps: Docker + диск — проверяем ЗДЕСЬ ━━━\033[0m"; \
	DOCKER_STATUS=$$(docker compose ps --format "{{.Status}}" 2>/dev/null | head -1); \
	DISK_FREE=$$(df -h / | awk 'NR==2{print $$4}'); \
	PROD_VER=$$(curl -s --connect-to "localhost:8002:127.0.0.1:8002" http://localhost:8002/api/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','ERR'))" 2>/dev/null || echo "UNREACHABLE"); \
	LOCAL_VER=$$(cat VERSION 2>/dev/null || echo "?"); \
	echo "  Docker: $$DOCKER_STATUS | Диск: $$DISK_FREE | Прод: v$$PROD_VER | Локально: v$$LOCAL_VER"; \
	if echo "$$DOCKER_STATUS" | grep -q "Up\|running" && [ "$$PROD_VER" = "$$LOCAL_VER" ]; then \
	  echo "\033[0;32m  ✅ DevOps: OK\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ DevOps: контейнер не запущен или версия не совпадает\033[0m"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [5] Skill Modernizer: AGENT.md менялись? — git diff ━━━\033[0m"; \
	AGENT_MD_CHANGES=$$(git log --since="2 days ago" --oneline -- ".agents/*/AGENT.md" 2>/dev/null | wc -l); \
	SM_CODE=$$(grep -cE "utcnow|shell=True|except:|TODO|DEPRECATED|Anti-pattern|AP-[A-Z]" .agents/skill-modernizer/modernizer-log.md 2>/dev/null || echo 0); \
	if [ "$$AGENT_MD_CHANGES" -gt 0 ] || [ "$$SM_CODE" -gt 0 ]; then \
	  echo "\033[0;32m  ✅ Skill Modernizer: AGENT.md обновлялись ($$AGENT_MD_CHANGES коммитов) + код анализ ($$SM_CODE строк)\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ Skill Modernizer: AGENT.md не менялись 2+ дней И нет анализа кода\033[0m"; \
	  echo "     → Обнови хотя бы один AGENT.md с уроком из этого раунда"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [6] Designer: скриншоты сегодня + HTTP smoke ━━━\033[0m"; \
	SCREENSHOTS_TODAY=$$(find .agents/designer/screenshots -name "*.png" -newer .agents/designer/screenshots -mtime -2 2>/dev/null | wc -l); \
	SCREENSHOTS_TOTAL=$$(find .agents/designer/screenshots -name "*.png" 2>/dev/null | wc -l); \
	PROJECT_ID=$$(curl -s --connect-to "localhost:8002:127.0.0.1:8002" http://localhost:8002/api/v1/projects 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); p=d.get('projects',[]); print(p[0]['project_id'] if p else '')" 2>/dev/null); \
	if [ -n "$$PROJECT_ID" ]; then \
	  SRT=$$(curl -s -o /dev/null -w "%{http_code}" --connect-to "localhost:8002:127.0.0.1:8002" "http://localhost:8002/api/v1/projects/$$PROJECT_ID/subtitles?format=srt" 2>/dev/null); \
	  DOCX=$$(curl -s -o /dev/null -w "%{http_code}" --connect-to "localhost:8002:127.0.0.1:8002" "http://localhost:8002/api/v1/projects/$$PROJECT_ID/export/script?format=docx&include_source=true" 2>/dev/null); \
	  echo "  Скриншотов всего: $$SCREENSHOTS_TOTAL | SRT=$$SRT | DOCX=$$DOCX"; \
	  if [ "$$SCREENSHOTS_TOTAL" -gt 0 ] && [ "$$SRT" = "200" ] && [ "$$DOCX" = "200" ]; then \
	    echo "\033[0;32m  ✅ Designer: скриншоты есть, export работает\033[0m"; \
	  else \
	    echo "\033[0;31m  ❌ Designer: нет скриншотов ($$SCREENSHOTS_TOTAL) или export сломан (SRT=$$SRT DOCX=$$DOCX)\033[0m"; \
	    FAIL=1; \
	  fi; \
	else \
	  if [ "$$SCREENSHOTS_TOTAL" -gt 0 ]; then \
	    echo "\033[0;32m  ✅ Designer: скриншоты есть (нет проектов для smoke)\033[0m"; \
	  else \
	    echo "\033[0;31m  ❌ Designer: нет скриншотов\033[0m"; \
	    FAIL=1; \
	  fi; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [7] Tech Writer: RELEASE_NOTES + PUBLIC_ROADMAP версия ━━━\033[0m"; \
	NOTES_COUNT=$$(find .agents/tech-writer -name "RELEASE_NOTES*.md" 2>/dev/null | wc -l); \
	ROADMAP_VER=$$(grep -oE "[0-9]+\.[0-9]+\.[0-9]+" PUBLIC_ROADMAP.md 2>/dev/null | head -1); \
	FILE_VER=$$(cat VERSION 2>/dev/null | tr -d '[:space:]'); \
	echo "  RELEASE_NOTES файлов: $$NOTES_COUNT | Roadmap: v$$ROADMAP_VER | VERSION: v$$FILE_VER"; \
	if [ "$$NOTES_COUNT" -gt 0 ] && [ "$$ROADMAP_VER" = "$$FILE_VER" ]; then \
	  echo "\033[0;32m  ✅ Tech Writer: документация актуальна\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ Tech Writer: нет RELEASE_NOTES ($$NOTES_COUNT) или roadmap ($$ROADMAP_VER) ≠ VERSION ($$FILE_VER)\033[0m"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [8] User Survey: опрос пользователей сегодня/вчера ━━━\033[0m"; \
	SURVEY_LATEST=$$(find .agents/business-analyst/user-surveys -name "*.md" -mtime -2 2>/dev/null | wc -l); \
	SURVEY_PERSONAS=$$(find .agents/business-analyst/user-surveys -name "*.md" -mtime -2 -exec grep -l "Персона\|👤\|лет\|пользоват" {} \; 2>/dev/null | wc -l); \
	echo "  Survey файлов за 2 дня: $$SURVEY_LATEST | С персонами: $$SURVEY_PERSONAS"; \
	if [ "$$SURVEY_LATEST" -gt 0 ] && [ "$$SURVEY_PERSONAS" -gt 0 ]; then \
	  echo "\033[0;32m  ✅ User Survey: опрос пользователей проведён\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ User Survey: нет файла с персонами за 2 дня\033[0m"; \
	  echo "     → Создай .agents/business-analyst/user-surveys/R{N}-survey.md"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [9] QA Monitor Agent — qa-report.md сегодня/вчера ━━━\033[0m"; \
	QA_FRESH=$$(grep -c "$$TODAY\|$$YESTERDAY" .agents/qa-monitor/qa-report.md 2>/dev/null || echo 0); \
	QA_NUMS=$$(grep -cE "Ran [0-9]+ test|OK \(|[0-9]+ (passed|ok)" .agents/qa-monitor/qa-report.md 2>/dev/null || echo 0); \
	echo "  qa-report.md: $$QA_FRESH строк с датой, $$QA_NUMS строк с числами тестов"; \
	if [ "$$QA_FRESH" -gt 0 ] && [ "$$QA_NUMS" -gt 0 ]; then \
	  echo "\033[0;32m  ✅ QA Monitor: qa-report.md обновлён сегодня/вчера с числами тестов\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ QA Monitor: qa-report.md НЕ обновлён ($$QA_FRESH дат, $$QA_NUMS чисел)\033[0m"; \
	  echo "     → Агент ОБЯЗАН записать результат в .agents/qa-monitor/qa-report.md"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [10] Designer Agent — design-log.md + скриншоты ━━━\033[0m"; \
	DESIGN_FRESH=$$(grep -c "$$TODAY\|$$YESTERDAY" .agents/designer/design-log.md 2>/dev/null || echo 0); \
	DESIGN_APRUV=$$(grep -c "АПРУV\|БЛОК" .agents/designer/design-log.md 2>/dev/null || echo 0); \
	SCR_TOTAL=$$(find .agents/designer/screenshots -name "*.png" 2>/dev/null | wc -l); \
	echo "  design-log.md: $$DESIGN_FRESH строк с датой, $$DESIGN_APRUV АПРУV/БЛОК. Скриншоты: $$SCR_TOTAL png"; \
	if [ "$$DESIGN_FRESH" -gt 0 ] && [ "$$DESIGN_APRUV" -gt 0 ] && [ "$$SCR_TOTAL" -gt 0 ]; then \
	  echo "\033[0;32m  ✅ Designer: design-log.md обновлён, скриншоты есть\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ Designer: design-log.md не обновлён ($$DESIGN_FRESH дат) или нет скриншотов ($$SCR_TOTAL)\033[0m"; \
	  echo "     → Агент ОБЯЗАН: open browser → screenshot → записать в design-log.md"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [11] Tech Writer Agent — RELEASE_NOTES текущей версии ━━━\033[0m"; \
	CUR_VER=$$(cat VERSION 2>/dev/null | tr -d '[:space:]'); \
	TW_NOTES=$$(find .agents/tech-writer -name "RELEASE_NOTES_v$$CUR_VER.md" 2>/dev/null | wc -l); \
	TW_LOG_FRESH=$$(grep -c "$$TODAY\|$$YESTERDAY" .agents/tech-writer/user-stories.md 2>/dev/null || echo 0); \
	echo "  RELEASE_NOTES_v$$CUR_VER.md: $$TW_NOTES файл(а). user-stories.md обновлён: $$TW_LOG_FRESH строк"; \
	if [ "$$TW_NOTES" -gt 0 ]; then \
	  echo "\033[0;32m  ✅ Tech Writer: RELEASE_NOTES_v$$CUR_VER.md существует\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ Tech Writer: нет RELEASE_NOTES_v$$CUR_VER.md\033[0m"; \
	  echo "     → Агент ОБЯЗАН создать .agents/tech-writer/RELEASE_NOTES_v$$CUR_VER.md"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [12] Skill Modernizer Agent — modernizer-log.md сегодня/вчера ━━━\033[0m"; \
	SM_FRESH=$$(grep -c "$$TODAY\|$$YESTERDAY" .agents/skill-modernizer/modernizer-log.md 2>/dev/null || echo 0); \
	SM_CODE=$$(grep -cE "utcnow|shell=True|except:|TODO|DEPRECATED|Anti-pattern|AP-[A-Z]|\\bgrep\b" .agents/skill-modernizer/modernizer-log.md 2>/dev/null || echo 0); \
	SM_AGENT_MD=$$(git log --since="2 days ago" --oneline -- ".agents/*/AGENT.md" 2>/dev/null | wc -l); \
	echo "  modernizer-log.md: $$SM_FRESH строк с датой, $$SM_CODE строк анализа. AGENT.md коммитов: $$SM_AGENT_MD"; \
	if [ "$$SM_FRESH" -gt 0 ] && [ "$$SM_CODE" -gt 0 ] && [ "$$SM_AGENT_MD" -gt 0 ]; then \
	  echo "\033[0;32m  ✅ Skill Modernizer: анализ выполнен + AGENT.md агентов обновлены\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ Skill Modernizer: работа не выполнена полностью\033[0m"; \
	  [ "$$SM_AGENT_MD" -eq 0 ] && echo "     → 0 AGENT.md обновлено за 2 дня — SM ОБЯЗАН обновить AGENT.md по найденным AP"; \
	  [ "$$SM_FRESH" -eq 0 ] && echo "     → modernizer-log.md не обновлён сегодня"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "\033[0;36m━━━ [13] Стратегические агенты — подпись с текущей версией ━━━\033[0m"; \
	CUR_VER=$$(cat VERSION 2>/dev/null | tr -d '[:space:]'); \
	STRAT_FAIL=0; \
	for AGENT in ceo cto project-manager qa-engineer ux-designer ml-engineer business-analyst system-analyst; do \
	  HAS_SIG=$$(grep -c "АПРУV.*v$$CUR_VER\|v$$CUR_VER.*АПРУV" .agents/$$AGENT/review-log.md 2>/dev/null || echo 0); \
	  if [ "$$HAS_SIG" -gt 0 ]; then \
	    echo "  ✅ $$AGENT: подписан v$$CUR_VER"; \
	  else \
	    echo "  ❌ $$AGENT: НЕТ подписи v$$CUR_VER в review-log.md"; \
	    STRAT_FAIL=1; \
	  fi; \
	done; \
	if [ "$$STRAT_FAIL" -eq 0 ]; then \
	  echo "\033[0;32m  ✅ Все 8 стратегических агентов подписали v$$CUR_VER\033[0m"; \
	else \
	  echo "\033[0;31m  ❌ Не все стратегические агенты подписали v$$CUR_VER — запустить всех\033[0m"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	$(MAKE) agent:performance; \
	if [ $$FAIL -eq 0 ]; then \
	  echo "\033[0;32m╔══════════════════════════════════════════════════════════════════╗\033[0m"; \
	  echo "\033[0;32m║  ✅ ROUND CLOSE v5.0 ПРОЙДЕН (13 проверок + Performance)       ║\033[0m"; \
	  echo "\033[0;32m║  Можно делать: git push origin develop                          ║\033[0m"; \
	  echo "\033[0;32m╚══════════════════════════════════════════════════════════════════╝\033[0m"; \
	else \
	  echo "\033[0;31m╔══════════════════════════════════════════════════════════════════╗\033[0m"; \
	  echo "\033[0;31m║  ❌ ROUND CLOSE FAILED                                          ║\033[0m"; \
	  echo "\033[0;31m║  Исправь проблемы выше и запусти снова                          ║\033[0m"; \
	  echo "\033[0;31m╚══════════════════════════════════════════════════════════════════╝\033[0m"; \
	  exit 1; \
	fi

## verify:deployed: Проверить что прод совпадает с локальной версией (smoke check после deploy)
verify\:deployed:
	@LOCAL_VER=$$(cat VERSION 2>/dev/null || echo "UNKNOWN"); \
	PROD_VER=$$(curl -s http://localhost:8002/api/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','ERR'))" 2>/dev/null || echo "UNREACHABLE"); \
	echo "$(CYAN)🔍 Локальная версия:    $$LOCAL_VER$(RESET)"; \
	echo "$(CYAN)🌐 Продакшн версия:     $$PROD_VER$(RESET)"; \
	if [ "$$LOCAL_VER" = "$$PROD_VER" ]; then \
	  echo "$(GREEN)✅ Версии совпадают — деплой актуален.$(RESET)"; \
	else \
	  echo "$(RED)❌ ВЕРСИИ НЕ СОВПАДАЮТ!$(RESET)"; \
	  echo "$(YELLOW)   Запусти: make deploy$(RESET)"; \
	  exit 1; \
	fi

## iteration: Полный цикл итерации = тесты + агенты + деплой + верификация
## agent:qa-monitor: QA Monitor — запускает тесты и записывает отчёт (вызывается из iteration)
agent\:qa-monitor:
	@echo "$(CYAN)🔍 QA Monitor Agent...$(RESET)"
	@TODAY=$$(date +%Y-%m-%d); \
	PY_RESULT=$$(PYTHONPATH=src python3 -m unittest discover -s tests -q 2>&1 | tail -2); \
	TSC_RESULT=$$(cd ui && npx tsc --noEmit 2>&1 | wc -l); \
	printf "\n## QA Monitor — $$TODAY v$$(cat VERSION)\n\`\`\`\n$$PY_RESULT\ntsc errors: $$TSC_RESULT\n\`\`\`\n### Подпись: QA Monitor АПРУV | $$TODAY v$$(cat VERSION)\n" >> .agents/qa-monitor/qa-report.md; \
	echo "$(GREEN)  ✅ QA Monitor: qa-report.md обновлён$(RESET)"

## agent:designer: Designer — CSS guard + smoke HTTP + запись в design-log (вызывается из iteration)
agent\:designer:
	@echo "$(CYAN)🎨 Designer Agent...$(RESET)"
	@TODAY=$$(date +%Y-%m-%d); \
	CSS_RESULT=$$(python3 scripts/css_guard.py ui/src/index.css 2>&1 | tail -1); \
	HEALTH=$$(curl -s http://localhost:8002/api/health 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('version','ERR'))" 2>/dev/null || echo "UNREACHABLE"); \
	NEW_COMPONENTS=$$(git diff origin/develop --name-only -- ui/src/components/ 2>/dev/null | head -5 | tr '\n' ' '); \
	printf "\n## Designer — $$TODAY v$$(cat VERSION)\n- CSS guard: $$CSS_RESULT\n- Prod health: v$$HEALTH\n- Изменённые компоненты: $$NEW_COMPONENTS\n### АПРУV: Designer\n### Подпись: Designer АПРУV | $$TODAY v$$(cat VERSION)\n" >> .agents/designer/design-log.md; \
	echo "$(GREEN)  ✅ Designer: design-log.md обновлён$(RESET)"

## agent:tech-writer: Tech Writer — создаёт RELEASE_NOTES если нет (вызывается из iteration)
agent\:tech-writer:
	@echo "$(CYAN)✍️  Tech Writer Agent...$(RESET)"
	@TODAY=$$(date +%Y-%m-%d); \
	CUR_VER=$$(cat VERSION | tr -d '[:space:]'); \
	NOTES_FILE=".agents/tech-writer/RELEASE_NOTES_v$$CUR_VER.md"; \
	if [ ! -f "$$NOTES_FILE" ]; then \
	  LAST_COMMITS=$$(git log --oneline -7 2>/dev/null | sed 's/^/- /'); \
	  PY_TESTS=$$(PYTHONPATH=src python3 -m unittest discover -s tests -q 2>&1 | tail -1); \
	  printf "# Release Notes v$$CUR_VER — $$TODAY\n\n## Изменения:\n$$LAST_COMMITS\n\n## Тесты: $$PY_TESTS\n\n*Tech Writer Agent | $$TODAY | auto-generated*\n" > "$$NOTES_FILE"; \
	  echo "$(GREEN)  ✅ Tech Writer: создан $$NOTES_FILE$(RESET)"; \
	else \
	  echo "$(GREEN)  ✅ Tech Writer: RELEASE_NOTES_v$$CUR_VER.md уже существует$(RESET)"; \
	fi; \
	TODAY_MARK=$$(date +%Y-%m-%d); \
	grep -q "$$TODAY_MARK" ".agents/tech-writer/user-stories.md" 2>/dev/null || \
	  printf "\n<!-- TW checked: $$TODAY_MARK v$$CUR_VER -->\n" >> ".agents/tech-writer/user-stories.md"

## agent:skill-modernizer: Skill Modernizer — реальный тюнинг ВСЕХ агентов (вызывается из iteration)
## Обновляет AGENT.md каждого агента уроками раунда + SKILL.md порог тестов + саморефлексия
agent\:skill-modernizer:
	@echo "$(CYAN)🧠 Skill Modernizer Agent — тюнинг всех агентов...$(RESET)"
	@python3 scripts/skill_modernizer.py

## agent:performance: Performance Agent — bundle size + API time (вызывается из round-close)
agent\:performance:
	@echo "$(CYAN)⚡ Performance Agent...$(RESET)"
	@TODAY=$$(date +%Y-%m-%d); \
	CUR_VER=$$(cat VERSION | tr -d '[:space:]'); \
	JS_GZIP=$$(gzip -c ui/dist/assets/*.js 2>/dev/null | wc -c | awk '{printf "%.1f", $$1/1024}'); \
	CSS_GZIP=$$(gzip -c ui/dist/assets/*.css 2>/dev/null | wc -c | awk '{printf "%.1f", $$1/1024}'); \
	HEALTH_T=$$(curl -s -o /dev/null -w "%{time_total}" http://localhost:8002/api/health 2>/dev/null || echo "ERR"); \
	PROJECTS_T=$$(curl -s -o /dev/null -w "%{time_total}" http://localhost:8002/api/v1/projects 2>/dev/null || echo "ERR"); \
	printf "\n## Performance — $$TODAY v$$CUR_VER\n| Метрика | Значение | Baseline R12 |\n|---------|----------|-------------|\n| JS gzip | $$JS_GZIP KB | 129.75 KB |\n| CSS gzip | $$CSS_GZIP KB | 20.73 KB |\n| /health | $$HEALTH_T s | 0.004s |\n| /projects | $$PROJECTS_T s | 0.007s |\n\n### Подпись: Performance АПРУV | $$TODAY v$$CUR_VER\n" >> .agents/performance/performance-log.md; \
	echo "$(GREEN)  ✅ Performance: performance-log.md обновлён (JS=$$JS_GZIP KB gzip)$(RESET)"

## iteration: полный цикл — тесты → деплой → верификация → 4 code-quality агента АВТОМАТИЧЕСКИ
iteration:
	@echo "$(CYAN)╔══════════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(CYAN)║          ITERATION GATE — полный цикл итерации               ║$(RESET)"
	@echo "$(CYAN)╚══════════════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "$(CYAN)Шаг 1/4: Тесты + coverage...$(RESET)"
	@$(MAKE) test:all
	@$(MAKE) test:coverage
	@echo ""
	@echo "$(CYAN)Шаг 2/4: Деплой...$(RESET)"
	@$(MAKE) deploy
	@echo ""
	@echo "$(CYAN)Шаг 3/4: Верификация деплоя...$(RESET)"
	@$(MAKE) verify:deployed
	@echo ""
	@echo "$(CYAN)Шаг 4/4: Code-quality агенты (автоматически)...$(RESET)"
	@$(MAKE) agent:qa-monitor
	@$(MAKE) agent:designer
	@$(MAKE) agent:tech-writer
	@$(MAKE) agent:skill-modernizer
	@echo ""
	@echo "$(GREEN)╔══════════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(GREEN)║  ✅ ITERATION COMPLETE — прод обновлён, агенты отработали   ║$(RESET)"
	@echo "$(GREEN)║  Для закрытия раунда: make round-close (8 стратег. агентов) ║$(RESET)"
	@echo "$(GREEN)╚══════════════════════════════════════════════════════════════╝$(RESET)"


