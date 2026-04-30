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

# Копируем все исходники
COPY . .

EXPOSE 8000

# Запускаем API-сервер
CMD ["translate-video", "server", "--host", "0.0.0.0", "--port", "8000"]
