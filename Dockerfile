# Этап 1: Сборка Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# Этап 2: Сборка Backend
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

# Установка системных зависимостей (FFmpeg необходим для работы со звуком/видео)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем настройки пакета
COPY pyproject.toml requirements.txt ./

# Устанавливаем зависимости
RUN pip install --no-cache-dir -e .

# Копируем все исходники ядра
COPY . .

# Копируем собранный frontend
COPY --from=frontend-builder /app/ui/dist /app/ui/dist

EXPOSE 8002

# Запускаем API-сервер
CMD ["translate-video", "server", "--host", "0.0.0.0", "--port", "8002"]
