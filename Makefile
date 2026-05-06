.PHONY: help build deploy restart logs status test test\:unit test\:ui test\:e2e test\:e2e-fullstack test\:load test\:all test\:coverage test\:release release\:fix release\:finish lint ui-build ui-dev visual-check visual-check-ci css-guard

# Цвета для вывода
CYAN  := \033[0;36m
GREEN := \033[0;32m
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

## test:release: Полный release gate перед merge в master
# Запускать ПЕРЕД каждым merge develop→master.
# Если падают → НЕ пушить master, создать release-fix ветку (make release:fix).
test\:release:
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

