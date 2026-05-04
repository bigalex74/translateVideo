.PHONY: help build deploy restart logs status test test\:unit test\:ui test\:e2e test\:e2e-fullstack test\:load test\:all test\:coverage test\:release lint ui-build ui-dev

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

## test:coverage: Проверить покрытие кода (Python ≥82%, TypeScript ≥80%)
test\:coverage:
	@echo "$(CYAN)▶ Coverage: Python...$(RESET)"
	PYTHONPATH=src python3 -m coverage run \
	  --source=translate_video \
	  --omit="*/legacy.py" \
	  -m unittest discover -s tests -q
	python3 -m coverage report --fail-under=82
	@echo "$(CYAN)▶ Coverage: TypeScript...$(RESET)"
	cd ui && npm run test -- --coverage

## test:release: Полный release gate перед merge в master
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
