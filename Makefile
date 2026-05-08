.PHONY: help build deploy restart logs status test test\:unit test\:ui test\:e2e test\:e2e-fullstack test\:load test\:all test\:coverage test\:metadata test\:release ci\:quick release\:checklist release\:fix release\:finish lint ui-build ui-dev visual-check visual-check-ci css-guard

# Цвета для вывода
CYAN  := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED   := \033[0;31m
RESET := \033[0m

## help: Показать все доступные команды
help:
	@echo ""
	@echo "  $(CYAN)translateVideo — команды управления$(RESET)"
	@echo ""
	@grep -E '^## ' Makefile | sed 's/## /  /' | column -t -s ':'
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
	@echo "$(GREEN)✔ Готово. Версия:$(RESET)"
	@sleep 2 && curl -s http://localhost:8002/api/health

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


## round-close: Чеклист закрытия раунда — проверяет готовность ВСЕХ 4 агентов к push
## Запускать ПЕРЕД каждым merge в develop и git push.
round-close:
	@echo "$(CYAN)╔══════════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(CYAN)║         ROUND CLOSE CHECKLIST — WORKFLOW.md Правило 2        ║$(RESET)"
	@echo "$(CYAN)║         v2.1 — механические проверки реальных артефактов     ║$(RESET)"
	@echo "$(CYAN)╚══════════════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@FAIL=0; \
	TODAY=$$(date +%Y-%m-%d); \
	YESTERDAY=$$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || echo "0000-00-00"); \
	echo "$(CYAN)━━━ [1/4] DESIGNER — скриншоты браузера ━━━$(RESET)"; \
	SCREENSHOTS_ALL=$$(find .agents/designer/screenshots -name "*.png" 2>/dev/null | wc -l); \
	DESIGN_LOG_DATE=$$(grep -c "$$TODAY\|$$YESTERDAY" .agents/designer/design-log.md 2>/dev/null || echo 0); \
	DESIGN_APPROVED=$$(grep -c "АПРУV\|APPROVED" .agents/designer/design-log.md 2>/dev/null || echo 0); \
	if [ "$$SCREENSHOTS_ALL" -gt 0 ] && [ "$$DESIGN_LOG_DATE" -gt 0 ] && [ "$$DESIGN_APPROVED" -gt 0 ]; then \
	  echo "$(GREEN)  ✅ Designer: апруv + $${SCREENSHOTS_ALL} скриншотов (design-log обновлён)$(RESET)"; \
	else \
	  echo "$(RED)  ❌ Designer: требуется реальная визуальная проверка$(RESET)"; \
	  echo "$(YELLOW)     Скриншотов: $${SCREENSHOTS_ALL} | Апруv за сегодня/вчера: $${DESIGN_LOG_DATE}$(RESET)"; \
	  echo "$(YELLOW)     → Инструмент: Chrome DevTools MCP, take_screenshot() → .agents/designer/screenshots/$(RESET)"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "$(CYAN)━━━ [2/4] QA MONITOR — реальные тесты ━━━$(RESET)"; \
	QA_DATE=$$(grep -c "$$TODAY\|$$YESTERDAY" .agents/qa-monitor/qa-report.md 2>/dev/null || echo 0); \
	QA_APPROVED=$$(grep -c "АПРУV\|APPROVED" .agents/qa-monitor/qa-report.md 2>/dev/null || echo 0); \
	PY_TESTS=$$(PYTHONPATH=src python3 -m unittest discover -s tests -q 2>&1 | tail -1); \
	echo "  Python тесты сейчас: $$PY_TESTS"; \
	if echo "$$PY_TESTS" | grep -q "OK"; then PY_OK=1; else PY_OK=0; fi; \
	if [ "$$QA_APPROVED" -gt 0 ] && [ "$$QA_DATE" -gt 0 ] && [ "$$PY_OK" -eq 1 ]; then \
	  echo "$(GREEN)  ✅ QA Monitor: тесты зелёные, апруv за сегодня/вчера$(RESET)"; \
	else \
	  echo "$(RED)  ❌ QA Monitor: тесты провалились или апруv отсутствует$(RESET)"; \
	  echo "$(YELLOW)     → python3 -m unittest discover -s tests -q$(RESET)"; \
	  echo "$(YELLOW)     → cd ui && npm test && python3 -m coverage report --fail-under=80$(RESET)"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "$(CYAN)━━━ [3/4] TECH WRITER — документация ━━━$(RESET)"; \
	TW_DATE=$$(grep -c "$$TODAY\|$$YESTERDAY" .agents/tech-writer/user-stories.md 2>/dev/null || echo 0); \
	TW_APPROVED=$$(grep -c "АПРУV\|APPROVED" .agents/tech-writer/user-stories.md 2>/dev/null || echo 0); \
	RELEASE_NOTES=$$(find .agents/tech-writer -name "RELEASE_NOTES*.md" 2>/dev/null | wc -l); \
	if [ "$$TW_APPROVED" -gt 0 ] && [ "$$TW_DATE" -gt 0 ] && [ "$$RELEASE_NOTES" -gt 0 ]; then \
	  echo "$(GREEN)  ✅ Tech Writer: апруv + $${RELEASE_NOTES} RELEASE_NOTES файл(ов)$(RESET)"; \
	else \
	  echo "$(RED)  ❌ Tech Writer: апруv или RELEASE_NOTES отсутствует$(RESET)"; \
	  echo "$(YELLOW)     RELEASE_NOTES: $${RELEASE_NOTES} | Апруv за сегодня/вчера: $${TW_DATE}$(RESET)"; \
	  echo "$(YELLOW)     → Создай: .agents/tech-writer/RELEASE_NOTES_vX.Y.md$(RESET)"; \
	  echo "$(YELLOW)     → grep \"^## \" change.log | head -10 — проверь формат$(RESET)"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	echo "$(CYAN)━━━ [4/4] SKILL MODERNIZER — обновление скиллов ━━━$(RESET)"; \
	SM_DATE=$$(grep -c "$$TODAY\|$$YESTERDAY" .agents/skill-modernizer/modernizer-log.md 2>/dev/null || echo 0); \
	SM_HAS_CODE=$$(grep -cE "grep|AP-[A-Z]|антипаттерн|Антипаттерн|urlopen|localStorage" .agents/skill-modernizer/modernizer-log.md 2>/dev/null || echo 0); \
	SKILL_AGE=$$(python3 -c "import os,time; s=os.stat('/home/user/.gemini/skills/translate-video/SKILL.md'); print(round((time.time()-s.st_mtime)/86400,1))" 2>/dev/null || echo "99"); \
	if [ "$$SM_DATE" -gt 0 ] && [ "$$SM_HAS_CODE" -gt 0 ]; then \
	  echo "$(GREEN)  ✅ Skill Modernizer: лог обновлён, код проанализирован$(RESET)"; \
	  echo "$(CYAN)     translate-video/SKILL.md обновлён: $${SKILL_AGE} дней назад$(RESET)"; \
	else \
	  echo "$(RED)  ❌ Skill Modernizer: нет реального анализа кода в логе$(RESET)"; \
	  echo "$(YELLOW)     → grep -rn 'requests\\.' src/ | grep -v 'with_retry'$(RESET)"; \
	  echo "$(YELLOW)     → Обнови /home/user/.gemini/skills/translate-video/SKILL.md$(RESET)"; \
	  FAIL=1; \
	fi; \
	echo ""; \
	if [ $$FAIL -eq 0 ]; then \
	  echo "$(GREEN)╔══════════════════════════════════════════════════════════════╗$(RESET)"; \
	  echo "$(GREEN)║  ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — можно делать git push           ║$(RESET)"; \
	  echo "$(GREEN)╚══════════════════════════════════════════════════════════════╝$(RESET)"; \
	else \
	  echo "$(RED)╔══════════════════════════════════════════════════════════════╗$(RESET)"; \
	  echo "$(RED)║  ❌ ROUND CLOSE FAILED — устрани замечания выше              ║$(RESET)"; \
	  echo "$(RED)║  Агенты работают РЕАЛЬНО: браузер + grep + файлы             ║$(RESET)"; \
	  echo "$(RED)╚══════════════════════════════════════════════════════════════╝$(RESET)"; \
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
iteration:
	@echo "$(CYAN)╔══════════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(CYAN)║          ITERATION GATE — полный цикл итерации               ║$(RESET)"
	@echo "$(CYAN)╚══════════════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "$(CYAN)Шаг 1/3: Тесты + coverage...$(RESET)"
	@$(MAKE) test:all
	@$(MAKE) test:coverage
	@echo ""
	@echo "$(CYAN)Шаг 2/3: Деплой...$(RESET)"
	@$(MAKE) deploy
	@echo ""
	@echo "$(CYAN)Шаг 3/3: Верификация деплоя...$(RESET)"
	@$(MAKE) verify:deployed
	@echo ""
	@echo "$(GREEN)╔══════════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(GREEN)║  ✅ ITERATION COMPLETE — прод обновлён, версии совпадают    ║$(RESET)"
	@echo "$(GREEN)║  Теперь: запроси агентов и выполни make round-close         ║$(RESET)"
	@echo "$(GREEN)╚══════════════════════════════════════════════════════════════╝$(RESET)"

