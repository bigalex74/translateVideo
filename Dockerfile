# Этап 1: Сборка Frontend (node:20-alpine — минимальный образ)
FROM node:20-alpine AS frontend-builder
WORKDIR /app/ui

# Копируем только манифесты сначала для кеширования зависимостей
COPY ui/package*.json ./
RUN npm ci --prefer-offline

# Копируем исходники и собираем
COPY ui/ ./
RUN npm run build

# Этап 2: Python-зависимости (отдельный слой для кеша)
FROM python:3.11-slim AS python-deps
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Копируем только манифесты для кеша pip
COPY pyproject.toml requirements.txt ./
COPY src/translate_video/__init__.py src/translate_video/__init__.py

# Устанавливаем зависимости (без исходников — только deps layer)
RUN pip install --no-cache-dir -e . --no-build-isolation || \
    pip install --no-cache-dir -r requirements.txt

# Этап 3: Runtime образ (финальный — минимальный)
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные зависимости (FFmpeg + yt-dlp требует python3)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем установленные пакеты из deps layer
COPY --from=python-deps /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Копируем исходники (только src — без тестов, docs, ui/src)
COPY src/ src/
COPY pyproject.toml requirements.txt ./

# Переустанавливаем только сам пакет (быстро — зависимости уже есть)
RUN pip install --no-cache-dir -e . --no-deps

# Копируем собранный frontend
COPY --from=frontend-builder /app/ui/dist /app/ui/dist

# Создаём директорию для данных
RUN mkdir -p /app/runs

EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/api/health')" || exit 1

# Запускаем API-сервер
CMD ["translate-video", "server", "--host", "0.0.0.0", "--port", "8002"]
